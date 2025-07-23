# review_analysis/crawling/diningcode_crawler.py
"""
Diningcode 리뷰 크롤러 (명동교자 본점)
- Selenium으로 페이지 로드 & "더보기" 반복 클릭
- BeautifulSoup으로 파싱해서 CSV 저장
- BaseCrawler 인터페이스를 따름. (start_browser / scrape_reviews / save_to_database)
"""

from __future__ import annotations

import os
import re
import csv
import time
import random
from typing import List, Dict

from .base_crawler import BaseCrawler
from utils.logger import setup_logger

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from bs4 import BeautifulSoup


class DiningcodeCrawler(BaseCrawler):
    """다이닝코드 리뷰 크롤러"""

    def __init__(self, output_dir: str, place_url: str = "https://www.diningcode.com/profile.php?rid=L4miF0diqkcW"):
        """
        :param output_dir: CSV 저장 디렉토리
        :param place_url: 대상 가게 프로필 URL (rid 값만 바꿔주면 다른 가게 가능)
        """
        super().__init__(output_dir)
        self.url = place_url
        self.logger = setup_logger("diningcode")
        self.driver: webdriver.Chrome | None = None
        self._reviews: list[dict[str, str]] = []

    # --------------------------- BaseCrawler 구현부 --------------------------- #
    def start_browser(self) -> None:
        opts = Options()
        #opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
        opts.add_argument("window-size=1280,900")
        # opts.add_argument("--lang=ko-KR")  # 필요 시

        self.driver = webdriver.Chrome(options=opts)
        self.driver.get(self.url)

        # 리뷰 영역 ul 나타날 때까지 대기
        wait = WebDriverWait(self.driver, 15)
        try:
            tab = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[href*='review'], a[href='#review'], a[href='#div_review']")
            ))
            self.driver.execute_script("arguments[0].click();", tab)
        except TimeoutException:
            pass

        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div#div_review > div[id^='div_review_'], p.review_contents")
        ))

    def scrape_reviews(self) -> List[Dict[str, str]]:
        assert self.driver is not None, "start_browser() 먼저 호출하세요"
        d = self.driver

        # --- 1) '더보기' 반복 클릭 ------------------------------------------ #
        prev_cnt = -1
        while True:
            time.sleep(0.8)

            # 현재까지 로드된 리뷰 수 확인
            soup_tmp = BeautifulSoup(d.page_source, "html.parser")
            cur_cnt = len(_select_items(soup_tmp))
            print("현재 리뷰:", cur_cnt)

            try:
                btn = WebDriverWait(d, 2).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "#div_more_review button.More__Review__Button")
                    )
                )
                d.execute_script("arguments[0].click();", btn)
                self.logger.info("더보기 클릭")
                time.sleep(1.2)
                clicked = True
            except TimeoutException:
                clicked = False

            # 종료 조건
            if cur_cnt == prev_cnt and not clicked:
                break
            prev_cnt = cur_cnt

        # --- 2) 최종 파싱 ---------------------------------------------------- #
        soup = BeautifulSoup(d.page_source, "html.parser")
        items = _select_items(soup)
        self.logger.info(f"리뷰 블록 {len(items)}개 감지")

        data: List[Dict[str, str]] = []
        for li in items:
            review = _parse_one_review(li)
            data.append(review)
        self._reviews = [_parse_one_review(li) for li in items]
        self.logger.info(f"파싱 완료: {len(self._reviews)}개")
        return self._reviews

    def save_to_database(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, "reviews_diningcode.csv")
        keys = ["date", "score", "text"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(self._reviews)
        self.logger.info(f"Saved {len(self._reviews)} reviews → {path}")

    # ------------------------------------------------------------------------ #
    def close(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None


# --------------------------- 헬퍼 함수들 --------------------------- #

def _select_items(soup: BeautifulSoup):
    """리뷰 블록 선택자. 사이트가 바뀌면 여기만 수정하면 됨."""
    # div#div_review 내부에서 id가 div_review_ 로 시작하는 div 들
    items = soup.select("#div_review > div[id^='div_review_']")
    if items:
        return items
    # fallback
    return soup.select("#div_review div.latter-graph")

from datetime import datetime
YEAR_FALLBACK = datetime.now().year

def _parse_one_review(li) -> Dict[str, str]:
    """단일 리뷰 블록에서 4개 필드 추출.
    - 본문: p.review_contents.btxt
    - 별점: p.person-grade (★ 문자 수) or p.point-detail
    - 날짜: span.sub_title 중 첫 번째를 사용(필요 시 정규식)
    - 작성자: 프로필 영역의 텍스트 (확인 후 셀렉터 수정 가능)
    """
    # 본문
    text_el = li.select_one("p.review_contents.btxt")
    text = text_el.get_text(" ", strip=True) if text_el else ""

    # 별점
    score_el = li.select_one("span.total_score")
    score = ""
    if score_el:
        score = re.sub(r"[^0-9.]", "", score_el.get_text(strip=True))
        if score and float(score) > 5:
            score = ""

    # 날짜
    date_el = li.select_one("span.date")
    date = ""
    if date_el:
        raw = date_el.get_text(strip=True)
        m = re.search(r"(\d{1,2})월\s*(\d{1,2})일", raw)
        if m:
            mm, dd = int(m.group(1)), int(m.group(2))
            date = f"{YEAR_FALLBACK}-{mm:02d}-{dd:02d}"


    return {"date": date, "score": score, "text": text}


# --------------------------- 단독 실행 --------------------------- #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", required=True, help="output directory (e.g. ./database)")
    parser.add_argument("--url", default="https://www.diningcode.com/profile.php?rid=L4miF0diqkcW",
                        help="Diningcode place URL")
    args = parser.parse_args()

    crawler = DiningcodeCrawler(args.output, place_url=args.url)
    try:
        crawler.start_browser()
        crawler.scrape_reviews()
        crawler.save_to_database()
    finally:
        crawler.close()
