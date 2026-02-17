# -*- coding: utf-8 -*-
"""
SGIS 대화형 통계지도에서 격자별 아동인구(0~15세) 완전 자동 수집

CDP(Chrome DevTools Protocol) 마우스 이벤트로 드래그 앤 드롭을 자동화합니다.
CDP 이벤트는 isTrusted=true이므로 jQuery UI 드래그가 정상 작동합니다.

사용법:
  1. python scrape_sgis_grid_pop.py 실행
  2. 브라우저에서 수동으로 조건 설정:
     - 인구주택총조사 → 인구조건 → 연령: 0~15세 미만 → 성별: 전체
     - 검색조건 생성 버튼 클릭
     - 격자 보기(100m) 활성화
  3. Enter 입력 → 전체 읍면동 자동 순회 수집

출력:
  sgis_grid_child_pop.csv (gid, pop, sigungu, emd)
"""
import os
import json
import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "sgis_grid_child_pop.csv")

TARGETS = [
    {"sido": "경기도", "sgg_keywords": ["성남", "하남", "화성"]},
    {"sido": "서울특별시", "sgg_keywords": ["송파구"]},
]

SGIS_URL = "https://sgis.mods.go.kr/view/map/interactiveMap/mainIndexView"


# ──────────────────────────────────────────────────────────
# 브라우저 설정
# ──────────────────────────────────────────────────────────

def setup_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ──────────────────────────────────────────────────────────
# durianMask 로딩 오버레이 대기
# ──────────────────────────────────────────────────────────

def wait_for_mask_gone(driver, max_wait=15):
    for _ in range(max_wait * 2):
        mask_visible = driver.execute_script("""
            var mask = document.getElementById('durianMask');
            if (!mask) return false;
            var style = window.getComputedStyle(mask);
            return style.display !== 'none' && style.opacity !== '0' && style.visibility !== 'hidden';
        """)
        if not mask_visible:
            return True
        time.sleep(0.5)
    return False


# ──────────────────────────────────────────────────────────
# 드롭다운 네비게이션
# ──────────────────────────────────────────────────────────

def open_dropdown(driver):
    wait_for_mask_gone(driver, max_wait=10)
    for attempt in range(3):
        try:
            content = driver.find_element(By.ID, "content_mapNavi_1")
            style = content.get_attribute("style") or ""
            if "display: none" in style or "display:none" in style:
                driver.find_element(By.ID, "location_mapNavi_1").click()
                time.sleep(1)
            else:
                return True
        except Exception:
            wait_for_mask_gone(driver, max_wait=5)
            time.sleep(1)
    return False


def click_item(driver, ul_id, text, partial=False, wait=3):
    for attempt in range(wait):
        links = driver.find_elements(By.CSS_SELECTOR, f"#{ul_id} a")
        for link in links:
            t = link.text.strip()
            match = (text in t) if partial else (t == text or text in t)
            if match:
                link.click()
                return t
        time.sleep(1)
    return None


def get_list_items(driver, ul_id, wait=5):
    for _ in range(wait):
        links = driver.find_elements(By.CSS_SELECTOR, f"#{ul_id} a")
        items = [l.text.strip() for l in links if l.text.strip() and l.text.strip() != "전체"]
        if items:
            return items
        time.sleep(1)
    items = driver.execute_script("""
        var links = document.querySelectorAll('#' + arguments[0] + ' a');
        var r = [];
        for (var i = 0; i < links.length; i++) {
            var t = links[i].textContent.trim();
            if (t && t !== '전체') r.push(t);
        }
        return r;
    """, ul_id)
    return items or []


def navigate_to_emd(driver, sido, sgg, emd):
    wait_for_mask_gone(driver, max_wait=10)
    open_dropdown(driver)
    time.sleep(0.5)
    click_item(driver, "sidoSelect_mapNavi_1", sido)
    time.sleep(2)
    click_item(driver, "sggSelect_mapNavi_1", sgg)
    time.sleep(2)
    click_item(driver, "admSelect_mapNavi_1", emd)
    time.sleep(0.5)
    try:
        driver.find_element(By.ID, "navi-confirm").click()
    except Exception:
        pass
    time.sleep(2)
    wait_for_mask_gone(driver, max_wait=15)
    time.sleep(1)


def build_queue(driver):
    queue = []
    for target in TARGETS:
        wait_for_mask_gone(driver, max_wait=10)
        open_dropdown(driver)
        time.sleep(1)
        click_item(driver, "sidoSelect_mapNavi_1", target["sido"])
        time.sleep(3)

        all_sgg = get_list_items(driver, "sggSelect_mapNavi_1")
        match_sgg = [s for s in all_sgg if any(kw in s for kw in target["sgg_keywords"])]
        print(f"  [{target['sido']}] 대상 시군구: {', '.join(match_sgg)}")

        for sgg in match_sgg:
            wait_for_mask_gone(driver, max_wait=10)
            open_dropdown(driver)
            time.sleep(0.5)
            click_item(driver, "sidoSelect_mapNavi_1", target["sido"])
            time.sleep(2)
            click_item(driver, "sggSelect_mapNavi_1", sgg)
            time.sleep(3)

            emds = get_list_items(driver, "admSelect_mapNavi_1")
            for emd in emds:
                queue.append({"sido": target["sido"], "sigungu": sgg, "emd": emd})
            print(f"    {sgg}: {len(emds)}개 읍면동")

    return queue


# ──────────────────────────────────────────────────────────
# CDP 드래그 앤 드롭 (isTrusted=true)
# ──────────────────────────────────────────────────────────

def get_element_center(driver, element_id):
    return driver.execute_script("""
        var el = document.getElementById(arguments[0]);
        if (!el) return null;
        var r = el.getBoundingClientRect();
        return {x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height};
    """, element_id)


def cdp_mouse(driver, event_type, x, y):
    driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
        "type": event_type,
        "x": int(x),
        "y": int(y),
        "button": "left",
        "clickCount": 1 if event_type in ("mousePressed", "mouseReleased") else 0,
    })


def cdp_drag_and_drop(driver, source_id="dragItem_0", target_id="mapRgn_1", steps=20):
    src = get_element_center(driver, source_id)
    tgt = get_element_center(driver, target_id)

    if not src or not tgt:
        return False

    sx, sy = src["x"], src["y"]
    tx, ty = tgt["x"], tgt["y"]

    cdp_mouse(driver, "mouseMoved", sx, sy)
    time.sleep(0.05)
    cdp_mouse(driver, "mousePressed", sx, sy)
    time.sleep(0.1)

    for i in range(1, steps + 1):
        ratio = i / steps
        cx = sx + (tx - sx) * ratio
        cy = sy + (ty - sy) * ratio
        cdp_mouse(driver, "mouseMoved", cx, cy)
        time.sleep(0.02)

    time.sleep(0.15)
    cdp_mouse(driver, "mouseReleased", tx, ty)
    time.sleep(0.1)

    return True


# ──────────────────────────────────────────────────────────
# JavaScript 테이블 추출
# ──────────────────────────────────────────────────────────

def extract_grid_data(driver):
    js = """
    var seen = {};
    var data = [];
    var rows = document.querySelectorAll('table tr');
    for (var i = 0; i < rows.length; i++) {
        var cells = rows[i].querySelectorAll('td');
        if (cells.length >= 3) {
            var gid = cells[1].textContent.trim();
            var pop = cells[2].textContent.trim();
            if (gid && !seen[gid] && gid.length >= 4) {
                var fc = gid.charCodeAt(0);
                if (fc >= 0xAC00 && fc <= 0xD7A3) {
                    seen[gid] = true;
                    data.push({gid: gid, pop: pop});
                }
            }
        }
    }
    return JSON.stringify(data);
    """
    result = driver.execute_script(js)
    return json.loads(result)


def get_current_gids(driver):
    data = extract_grid_data(driver)
    return set(d["gid"] for d in data)


def wait_for_new_data(driver, old_gids, max_wait=15):
    for _ in range(max_wait * 2):
        data = extract_grid_data(driver)
        if data:
            current_gids = set(d["gid"] for d in data)
            if current_gids != old_gids:
                return data
        time.sleep(0.5)
    return []


# ──────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("SGIS 격자별 아동인구 완전 자동 수집기 (CDP)")
    print("=" * 60)

    # 1. 브라우저 실행
    print("\n[1단계] 브라우저 실행...")
    driver = setup_driver()
    driver.get(SGIS_URL)
    time.sleep(5)

    # 2. 수동 설정
    print("\n[2단계] SGIS 수동 설정:")
    print("  1) 인구주택총조사 → 인구조건 → 연령: 0~15세 미만")
    print("  2) 성별: 전체 → 검색조건 생성")
    print("  3) 격자 보기 100m 활성화")
    print()
    input("  >>> 설정 완료 후 Enter <<< ")

    src = get_element_center(driver, "dragItem_0")
    if not src:
        print("\n  [오류] dragItem_0을 찾을 수 없습니다!")
        print("  검색조건 생성 버튼을 클릭했는지 확인해주세요.")
        input("  Enter로 종료...")
        driver.quit()
        return
    print(f"  드래그 소스 확인: ({src['x']:.0f}, {src['y']:.0f})")

    # 3. 읍면동 큐 구축
    print("\n[3단계] 읍면동 목록 구축...")
    queue = build_queue(driver)
    total = len(queue)
    print(f"\n  총 {total}개 읍면동 수집 예정")

    if total == 0:
        print("  수집할 읍면동이 없습니다.")
        driver.quit()
        return

    # 4. 순회 수집
    print(f"\n[4단계] 데이터 수집 시작!")
    print("-" * 60)

    all_data = []
    seen_gids = set()
    success_count = 0
    fail_count = 0
    start_time = time.time()

    for idx, item in enumerate(queue):
        label = f"[{idx+1}/{total}] {item['sigungu']} > {item['emd']}"

        try:
            # 드래그 전 현재 테이블 gid 기록
            old_gids = get_current_gids(driver)

            # 읍면동 이동 (mask 대기 포함)
            navigate_to_emd(driver, item["sido"], item["sigungu"], item["emd"])

            # CDP 드래그 앤 드롭
            drag_ok = cdp_drag_and_drop(driver)
            if not drag_ok:
                print(f"  {label}: 드래그 요소 없음 - 스킵")
                fail_count += 1
                continue

            # 새 데이터 대기 (이전과 다른 gid가 나올 때까지)
            wait_for_mask_gone(driver, max_wait=10)
            data = wait_for_new_data(driver, old_gids, max_wait=15)

            # 재시도: 느린 드래그
            if not data:
                cdp_drag_and_drop(driver, steps=40)
                wait_for_mask_gone(driver, max_wait=10)
                data = wait_for_new_data(driver, old_gids, max_wait=10)

            # 재시도 2: 현재 테이블 강제 추출
            if not data:
                data = extract_grid_data(driver)

            # 중복 제거 후 저장
            new_count = 0
            for d in data:
                if d["gid"] not in seen_gids:
                    seen_gids.add(d["gid"])
                    d["sigungu"] = item["sigungu"]
                    d["emd"] = item["emd"]
                    all_data.append(d)
                    new_count += 1

            if new_count > 0:
                success_count += 1
            else:
                fail_count += 1

            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed * 60 if elapsed > 0 else 0
            remain = (total - idx - 1) / rate if rate > 0 else 0

            print(f"  {label}: +{new_count}개 (누적 {len(all_data)}개) "
                  f"[{rate:.1f}개/분, ~{remain:.0f}분 남음]")

        except Exception as e:
            print(f"  {label}: 에러 - {str(e)[:60]}")
            fail_count += 1

        # 중간 저장 (20개마다)
        if (idx + 1) % 20 == 0 and all_data:
            backup = OUTPUT_FILE.replace(".csv", "_backup.csv")
            with open(backup, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["gid", "pop", "sigungu", "emd"])
                writer.writeheader()
                writer.writerows(all_data)
            print(f"    [중간저장] {len(all_data)}개")

    # 5. CSV 저장
    elapsed_total = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"[5단계] CSV 저장")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["gid", "pop", "sigungu", "emd"])
        writer.writeheader()
        writer.writerows(all_data)

    print(f"  파일: {OUTPUT_FILE}")
    print(f"  총 격자: {len(all_data)}개")
    print(f"  성공: {success_count}개 / 실패: {fail_count}개 읍면동")
    print(f"  소요시간: {elapsed_total/60:.1f}분")

    print("\n브라우저를 닫겠습니까? (y/n): ", end="")
    ans = input().strip().lower()
    if ans == "y":
        driver.quit()
    else:
        print("브라우저를 열어둡니다.")

    print("\n완료!")


if __name__ == "__main__":
    main()
