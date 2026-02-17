# -*- coding: utf-8 -*-
"""
SGIS 격자별 인구 수집 - CDP 자동 드래그 테스트 (5개 읍면동)

CDP(Chrome DevTools Protocol) 마우스 이벤트로 드래그 앤 드롭 자동화.
CDP 이벤트는 isTrusted=true이므로 jQuery UI 드래그가 작동합니다.

사용법:
  1. python scrape_sgis_test.py
  2. 브라우저에서 인구 조건 설정 (0~15세, 100m 격자 등)
  3. Enter 입력 → 자동 수집 시작
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
OUTPUT_FILE = os.path.join(BASE_DIR, "sgis_grid_test.csv")
SGIS_URL = "https://sgis.mods.go.kr/view/map/interactiveMap/mainIndexView"

TEST_SIDO = "서울특별시"
TEST_SGG = "송파구"
TEST_LIMIT = 5


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
    """durianMask 로딩 오버레이가 사라질 때까지 대기"""
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
    print("    [경고] durianMask가 여전히 표시 중 (타임아웃)")
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
                btn = driver.find_element(By.ID, "location_mapNavi_1")
                btn.click()
                time.sleep(1)
            else:
                return True
        except Exception as e:
            print(f"    [드롭다운] 시도 {attempt+1} 실패: {e}")
            wait_for_mask_gone(driver, max_wait=5)
            time.sleep(1)
    return False


def click_item(driver, ul_id, text, wait=3):
    for attempt in range(wait):
        links = driver.find_elements(By.CSS_SELECTOR, f"#{ul_id} a")
        items = [l.text.strip() for l in links if l.text.strip()]
        for link in links:
            t = link.text.strip()
            if t == text or text in t:
                link.click()
                print(f"    [{ul_id}] '{t}' 클릭 ({len(items)}개 항목)")
                return t
        time.sleep(1)
    print(f"    [{ul_id}] '{text}' 찾지 못함! 항목: {items[:5]}...")
    return None


def get_emd_list(driver, wait=5):
    for _ in range(wait):
        links = driver.find_elements(By.CSS_SELECTOR, "#admSelect_mapNavi_1 a")
        result = [l.text.strip() for l in links if l.text.strip() and l.text.strip() != "전체"]
        if result:
            return result
        time.sleep(1)
    items = driver.execute_script("""
        var links = document.querySelectorAll('#admSelect_mapNavi_1 a');
        var r = [];
        for (var i = 0; i < links.length; i++) {
            var t = links[i].textContent.trim();
            if (t && t !== '전체') r.push(t);
        }
        return r;
    """)
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


# ──────────────────────────────────────────────────────────
# CDP 드래그 앤 드롭
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
        print(f"    [CDP] 요소를 찾을 수 없음: src={src}, tgt={tgt}")
        return False

    sx, sy = src["x"], src["y"]
    tx, ty = tgt["x"], tgt["y"]

    print(f"    [CDP] ({sx:.0f},{sy:.0f}) → ({tx:.0f},{ty:.0f}), steps={steps}")

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
    """현재 테이블의 격자 ID 집합 반환"""
    data = extract_grid_data(driver)
    return set(d["gid"] for d in data)


def wait_for_new_data(driver, old_gids, max_wait=15):
    """이전 데이터와 다른 새 격자 데이터가 나타날 때까지 대기"""
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
    print("SGIS 격자별 인구 - CDP 자동 드래그 테스트 (5개 읍면동)")
    print("=" * 60)

    # 1. 브라우저 실행
    print("\n[1] 브라우저 실행...")
    driver = setup_driver()
    driver.get(SGIS_URL)
    time.sleep(5)

    # 2. 수동 설정
    print("\n[2] SGIS 수동 설정:")
    print("  1) 인구주택총조사 → 인구조건 → 연령: 0~15세 미만")
    print("  2) 성별: 전체 → 검색조건 생성")
    print("  3) 격자 보기 100m 활성화")
    print()
    input("  >>> 설정 완료 후 Enter <<< ")

    src_info = get_element_center(driver, "dragItem_0")
    tgt_info = get_element_center(driver, "mapRgn_1")
    print(f"\n  드래그 소스(dragItem_0): {src_info}")
    print(f"  드래그 타겟(mapRgn_1):  {tgt_info}")

    if not src_info:
        print("\n  [오류] dragItem_0을 찾을 수 없습니다!")
        print("  검색조건 생성 버튼을 클릭했는지 확인해주세요.")
        input("  Enter로 종료...")
        driver.quit()
        return

    # 3. 읍면동 목록
    print(f"\n[3] {TEST_SGG} 읍면동 목록 로드 중...")
    open_dropdown(driver)
    time.sleep(1)
    click_item(driver, "sidoSelect_mapNavi_1", TEST_SIDO)
    time.sleep(3)
    click_item(driver, "sggSelect_mapNavi_1", TEST_SGG)
    time.sleep(3)

    emd_list = get_emd_list(driver)
    test_emds = emd_list[:TEST_LIMIT]
    print(f"  읍면동 {len(emd_list)}개 발견, 테스트 대상: {test_emds}")

    if not test_emds:
        print("\n  [오류] 읍면동 목록이 비어있습니다!")
        input("  수동으로 시도>시군구 선택 후 Enter...")
        emd_list = get_emd_list(driver)
        test_emds = emd_list[:TEST_LIMIT]
        print(f"  재시도: {test_emds}")

    # 4. 수집
    all_data = []
    seen_gids = set()
    success = 0
    fail = 0

    for i, emd in enumerate(test_emds):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(test_emds)}] {TEST_SGG} > {emd}")
        print("=" * 60)

        # 드래그 전 현재 테이블 gid 기록
        old_gids = get_current_gids(driver)
        print(f"  드래그 전 테이블 격자: {len(old_gids)}개")

        # 읍면동 이동 (mask 대기 포함)
        print("  읍면동 이동 중...")
        navigate_to_emd(driver, TEST_SIDO, TEST_SGG, emd)

        # CDP 드래그 앤 드롭
        print("  CDP 드래그 앤 드롭 시도...")
        drag_ok = cdp_drag_and_drop(driver)
        if not drag_ok:
            print("  [실패] 드래그 요소를 찾을 수 없음")
            fail += 1
            continue

        # 새 데이터 대기 (이전 gid와 다른 데이터가 나올 때까지)
        print("  새 데이터 대기 중...")
        wait_for_mask_gone(driver, max_wait=10)
        data = wait_for_new_data(driver, old_gids, max_wait=15)

        if not data:
            # 재시도: 느린 드래그
            print("  [재시도] 느린 드래그 (steps=40)...")
            cdp_drag_and_drop(driver, steps=40)
            wait_for_mask_gone(driver, max_wait=10)
            data = wait_for_new_data(driver, old_gids, max_wait=10)

        if not data:
            # 재시도 2: 데이터가 없더라도 현재 테이블에서 추출 시도
            print("  [재시도2] 현재 테이블에서 강제 추출...")
            data = extract_grid_data(driver)

        new_count = 0
        for d in data:
            if d["gid"] not in seen_gids:
                seen_gids.add(d["gid"])
                d["sigungu"] = TEST_SGG
                d["emd"] = emd
                all_data.append(d)
                new_count += 1

        if new_count > 0:
            success += 1
            print(f"\n  결과: +{new_count}개 격자 (누적 {len(all_data)}개)")
            print(f"  예시: {data[0]['gid']} = {data[0]['pop']}명")
        else:
            fail += 1
            print(f"\n  결과: +0개 (드래그가 작동하지 않았을 수 있음)")

    # 5. CSV 저장
    print(f"\n{'='*60}")
    print("[5] CSV 저장")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["gid", "pop", "sigungu", "emd"])
        writer.writeheader()
        writer.writerows(all_data)

    print(f"  파일: {OUTPUT_FILE}")
    print(f"  총 격자: {len(all_data)}개")
    print(f"  성공: {success}개, 실패: {fail}개")
    if all_data:
        print(f"\n  상위 5개:")
        for d in all_data[:5]:
            print(f"    {d['gid']}: {d['pop']}명 ({d['emd']})")

    print("\n완료!")
    input("Enter로 종료...")
    driver.quit()


if __name__ == "__main__":
    main()
