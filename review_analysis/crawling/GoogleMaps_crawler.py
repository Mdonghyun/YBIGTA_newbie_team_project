from .base_crawler import BaseCrawler
from utils.logger import setup_logger
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import pandas as pd
import time
import os


class GoogleMapsCrawler(BaseCrawler):
    """
    명동교자 본점에 대한 Google Maps 리뷰 크롤러입니다.
    BaseCrawler를 상속받아 start_browser, scrape_reviews, save_to_database를 구현합니다.
    """

    SCROLL_PAUSE_SEC = 1.2
    MAX_SCROLLS = 100
    MIN_REVIEWS = 500

    def __init__(self, output_dir: str, timeout: int = 20):
        # 로깅 설정 (콘솔 + 파일)
        setup_logger()
        super().__init__(output_dir)
        self.logger = logging.getLogger()
        self.driver = None
        self.reviews = []
        self.timeout = timeout

    def start_browser(self):
        try:
            options = Options()
            options.add_experimental_option("detach", True)
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            self.driver = webdriver.Chrome(options=options)
            self.logger.info("브라우저를 성공적으로 시작했습니다.")
        except WebDriverException as e:
            self.logger.error(f"브라우저 시작 실패: {e}")
            raise

    def scrape_reviews(self):
        # 1) driver 자동 초기화
        if not self.driver:
            self.logger.info("driver가 초기화되지 않아 start_browser() 자동 호출")
            self.start_browser()

        self.logger.info("명동교자 본점 Google Maps 리뷰 수집을 시작합니다.")
        self.driver.get(
            "https://www.google.com/maps/place/명동교자+본점/"
            "data=!4m8!3m7!1s0x357ca2f00d41b15b:0x7d50d5b6b0623a1d!"
            "8m2!3d37.5625266!4d126.985609!9m1!1b1!16s%2Fg%2F11csqxcpw1"
            "?entry=ttu&g_ep=EgoyMDI1MDcxNi4wIKXMDSoASAFQAw%3D%3D"
        )

        # 2) 리뷰 탭 열기 (JS 클릭)
        try:
            review_tab = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "button[role='tab'][aria-label$='리뷰']"
                ))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});",
                review_tab
            )
            self.driver.execute_script("arguments[0].click();", review_tab)
            time.sleep(1.5)
            self.logger.info("리뷰 탭 클릭 완료 (JS 클릭)")
        except Exception as e:
            self.logger.warning(f"리뷰 탭 클릭 실패: {e}")

        # 3) 첫 리뷰 카드 로딩 대기
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium"))
            )
        except TimeoutException:
            self.logger.error("리뷰 카드가 로딩되지 않았습니다.")
            return

        # 4) 스크롤 컨테이너 찾기
        scrollbox = self.driver.execute_script("""
        function findContainer(el) {
        while (el) {
            if (el.scrollHeight > el.clientHeight &&
                el.querySelectorAll('div.jftiEf.fontBodyMedium').length >= 3) {
            return el;
            }
            el = el.parentElement;
        }
        return null;
        }
        return findContainer(
        document.querySelector('div.jftiEf.fontBodyMedium')
        );
        """)
        if not scrollbox:
            self.logger.error("스크롤 컨테이너를 찾지 못했습니다.")
            return

        self.logger.info(
            f"Scroll container found: tag={scrollbox.tag_name}, "
            f"classes={scrollbox.get_attribute('class')}"
        )

        # 5) 무한 스크롤: MIN_REVIEWS개 이상 로드될 때까지
        prev_count = len(scrollbox.find_elements(By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium"))
        for i in range(self.MAX_SCROLLS):
            # 스크롤
            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight;", scrollbox
            )

            # 로딩된 카드 개수 증가 대기
            try:
                WebDriverWait(self.driver, self.timeout).until(
                    lambda drv: len(scrollbox.find_elements(
                        By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium"
                    )) > prev_count
                )
                new_count = len(scrollbox.find_elements(By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium"))
                self.logger.info(f"스크롤 {i+1}: 리뷰 {prev_count} → {new_count}개 로드됨")
                prev_count = new_count

                if prev_count >= self.MIN_REVIEWS:
                    self.logger.info(f"{self.MIN_REVIEWS}개 이상 리뷰 로드 완료.")
                    break

            except TimeoutException:
                self.logger.info("더 이상 로드할 내용이 없습니다.")
                break
        else:
            self.logger.info(f"최대 {self.MAX_SCROLLS}회 스크롤 완료.")

        # 6) 리뷰 파싱
        cards = scrollbox.find_elements(By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium")
        self.logger.info(f"최종 리뷰 카드 개수: {len(cards)}")

        for idx, card in enumerate(cards, 1):
            try:
                # 별점
                star_label = card.find_element(
                    By.CSS_SELECTOR,
                    "span[role='img'][aria-label*='별표']"
                ).get_attribute("aria-label")
                rating = int(''.join(filter(str.isdigit, star_label))) if star_label else None

                # 날짜
                date = card.find_element(
                    By.CSS_SELECTOR,
                    "span.rsqaWe, span[aria-label*='전']"
                ).text

                # 본문
                content = card.find_element(
                    By.CSS_SELECTOR,
                    "div.MyEned span.wiI7pd"
                ).text.strip()

                if content:
                    self.reviews.append({
                        "rating": rating,
                        "date": date,
                        "content": content
                    })
            except Exception as e:
                self.logger.warning(f"{idx}번째 리뷰 파싱 실패: {e}")


    def save_to_database(self):
        try:
            if not self.reviews:
                self.logger.warning("저장할 리뷰가 없습니다.")
                return
            count = len(self.reviews)
            if count < self.MIN_REVIEWS:
                self.logger.warning(f"수집된 리뷰 수 {count}개는 최소 {self.MIN_REVIEWS}개 미만입니다.")
            df = pd.DataFrame(self.reviews)
            os.makedirs(self.output_dir, exist_ok=True)
            output_path = os.path.join(self.output_dir, "reviews_googlemaps.csv")
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            self.logger.info(f"{count}개의 리뷰를 저장했습니다 → {output_path}")
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("브라우저를 종료했습니다.")
