# -*- coding: utf-8 -*-
"""
SGIS 대화형 통계지도에서 격자별 아동인구(0~14세) 자동 수집

사용법:
  1. python scrape_sgis_grid_pop.py 실행
  2. 브라우저가 열리면 SGIS에서 수동으로 조건 설정:
     - 인구주택총조사 → 인구조건 → 연령: 0세 ~ 15세 미만 → 성별: 전체
     - 격자 보기(100m) 활성화
     - 검색조건 생성 버튼 클릭
  3. 준비 완료 후 콘솔에서 Enter 입력
  4. 스크립트가 자동으로 모든 읍면동 순회하며 데이터 수집

출력:
  sgis_grid_child_pop.csv (gid, pop, sigungu, emd)
"""
import os
import sys
import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "sgis_grid_child_pop.csv")

# 대상 지역 정의
TARGETS = [
    {"sido": "서울특별시", "sgg_keywords": ["송파구"]},
    {"sido": "경기도", "sgg_keywords": ["성남", "하남", "화성"]},
]

SGIS_URL = "https://sgis.mods.go.kr/view/map/interactiveMap/mainIndexView"


def setup_driver():
    """Chrome 브라우저 실행 (수동 설정을 위해 GUI 모드)"""
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


def wait_and_click(driver, css_selector, timeout=10):
    """요소가 클릭 가능할 때까지 대기 후 클릭"""
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
    )
    el.click()
    return el


def open_dropdown(driver):
    """지역 선택 드롭다운 열기"""
    content = driver.find_element(By.ID, "content_mapNavi_1")
    if content.get_attribute("style") and "display: none" in content.get_attribute("style"):
        driver.find_element(By.ID, "location_mapNavi_1").click()
        time.sleep(0.5)


def click_item_in_list(driver, ul_id, text, partial=False):
    """드롭다운 목록에서 텍스트 매칭하여 클릭"""
    links = driver.find_elements(By.CSS_SELECTOR, f"#{ul_id} a")
    for link in links:
        link_text = link.text.strip()
        if partial:
            if text in link_text:
                link.click()
                return link_text
        else:
            if link_text == text:
                link.click()
                return link_text
    return None


def get_list_items(driver, ul_id):
    """드롭다운 목록의 텍스트 목록 가져오기"""
    links = driver.find_elements(By.CSS_SELECTOR, f"#{ul_id} a")
    items = []
    for link in links:
        t = link.text.strip()
        if t and t != "전체":
            items.append(t)
    return items


def do_drag_and_drop(driver):
    """선택항목을 지도에 드래그 앤 드롭 (Selenium ActionChains)"""
    try:
        source = driver.find_element(By.ID, "dragItem_0")
        target = driver.find_element(By.ID, "mapRgn_1")

        actions = ActionChains(driver)
        actions.click_and_hold(source)
        actions.pause(0.2)
        actions.move_to_element(target)
        actions.pause(0.3)
        actions.release()
        actions.perform()
        return True
    except Exception as e:
        print(f"    드래그 앤 드롭 실패: {e}")
        return False


def extract_table_data(driver):
    """데이터보드 테이블에서 격자 ID + 인구 추출"""
    data = []
    seen = set()
    rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) >= 3:
            gid = cells[1].text.strip()
            pop = cells[2].text.strip()
            if gid and gid not in seen:
                seen.add(gid)
                data.append({"gid": gid, "pop": pop})
    return data


def wait_for_table_data(driver, max_wait=15):
    """테이블에 데이터가 나타날 때까지 대기"""
    for _ in range(max_wait * 2):
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr td")
        if len(rows) >= 3:
            return True
        time.sleep(0.5)
    return False


def build_queue(driver):
    """모든 대상 읍면동 목록 구축"""
    queue = []

    for target in TARGETS:
        open_dropdown(driver)
        time.sleep(0.5)
        click_item_in_list(driver, "sidoSelect_mapNavi_1", target["sido"])
        time.sleep(2)

        # 매칭되는 시군구 찾기
        all_sgg = get_list_items(driver, "sggSelect_mapNavi_1")
        match_sgg = [
            s for s in all_sgg
            if any(kw in s for kw in target["sgg_keywords"])
        ]
        print(f"[{target['sido']}] 대상 시군구: {', '.join(match_sgg)}")

        for sgg in match_sgg:
            open_dropdown(driver)
            time.sleep(0.3)
            click_item_in_list(driver, "sidoSelect_mapNavi_1", target["sido"])
            time.sleep(1)
            click_item_in_list(driver, "sggSelect_mapNavi_1", sgg)
            time.sleep(2)

            emds = get_list_items(driver, "admSelect_mapNavi_1")
            for emd in emds:
                queue.append({
                    "sido": target["sido"],
                    "sigungu": sgg,
                    "emd": emd,
                })
            print(f"  {sgg}: {len(emds)}개 읍면동")

    return queue


def navigate_to_emd(driver, item):
    """특정 읍면동으로 이동하고 확인 버튼 클릭"""
    open_dropdown(driver)
    time.sleep(0.3)
    click_item_in_list(driver, "sidoSelect_mapNavi_1", item["sido"])
    time.sleep(1)
    click_item_in_list(driver, "sggSelect_mapNavi_1", item["sigungu"])
    time.sleep(1.5)
    click_item_in_list(driver, "admSelect_mapNavi_1", item["emd"])
    time.sleep(0.3)
    driver.find_element(By.ID, "navi-confirm").click()
    time.sleep(2)


def main():
    print("=" * 60)
    print("SGIS 격자별 아동인구 자동 수집기")
    print("=" * 60)

    # 1. 브라우저 실행
    print("\n[1단계] 브라우저 실행 중...")
    driver = setup_driver()
    driver.get(SGIS_URL)
    time.sleep(3)

    # 2. 사용자에게 수동 설정 요청
    print("\n[2단계] SGIS 페이지에서 다음을 수동으로 설정해주세요:")
    print("  1) 좌측 메뉴 → 인구주택총조사 → 인구조건")
    print("  2) 연령: 0세 ~ 15세 미만 (또는 원하는 범위)")
    print("  3) 성별: 전체")
    print("  4) 검색조건 생성 버튼 클릭")
    print("  5) 격자 보기 (100m) 활성화")
    print("  6) 아무 읍면동이나 선택 후 선택항목을 드래그하여 작동 확인")
    print()
    input("  >>> 설정 완료 후 여기서 Enter를 누르세요 <<< ")

    # 3. 읍면동 목록 구축
    print("\n[3단계] 읍면동 목록 구축 중...")
    queue = build_queue(driver)
    total = len(queue)
    print(f"\n  총 {total}개 읍면동 수집 예정")

    # 4. 순회 수집
    print("\n[4단계] 데이터 수집 시작!")
    print("-" * 60)

    all_data = []
    seen_gids = set()
    success_count = 0
    fail_count = 0

    for idx, item in enumerate(queue):
        label = f"[{idx + 1}/{total}] {item['sigungu']} > {item['emd']}"

        try:
            # 읍면동 이동
            navigate_to_emd(driver, item)

            # 드래그 앤 드롭
            drag_ok = do_drag_and_drop(driver)
            if not drag_ok:
                print(f"  {label}: 드래그 실패 - 건너뜀")
                fail_count += 1
                continue

            # 테이블 로드 대기
            time.sleep(4)
            has_data = wait_for_table_data(driver, max_wait=10)

            if not has_data:
                print(f"  {label}: 테이블 데이터 없음 - 건너뜀")
                fail_count += 1
                continue

            # 테이블 추출
            data = extract_table_data(driver)
            new_count = 0
            for d in data:
                if d["gid"] not in seen_gids:
                    seen_gids.add(d["gid"])
                    d["sigungu"] = item["sigungu"]
                    d["emd"] = item["emd"]
                    all_data.append(d)
                    new_count += 1

            success_count += 1
            print(f"  {label}: +{new_count}개 격자 (누적 {len(all_data)}개)")

        except Exception as e:
            print(f"  {label}: 에러 - {str(e)[:50]}")
            fail_count += 1
            continue

    # 5. CSV 저장
    print("\n" + "=" * 60)
    print("[5단계] CSV 저장")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["gid", "pop", "sigungu", "emd"])
        writer.writeheader()
        writer.writerows(all_data)

    print(f"  저장 완료: {OUTPUT_FILE}")
    print(f"  총 격자: {len(all_data)}개")
    print(f"  성공: {success_count}개 읍면동")
    print(f"  실패: {fail_count}개 읍면동")

    # 6. 종료
    print("\n브라우저를 닫으시겠습니까? (y/n): ", end="")
    if input().strip().lower() == "y":
        driver.quit()
    else:
        print("브라우저를 열어둡니다. 수동으로 닫아주세요.")

    print("\n완료!")


if __name__ == "__main__":
    main()
