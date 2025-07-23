from review_analysis.crawling.base_crawler import BaseCrawler
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import pandas as pd
import os

class KakaoCrawler(BaseCrawler):
    def __init__(self, output_dir: str):
        super().__init__(output_dir)
        # 명동교자 본점 카카오맵 리뷰 URL
        self.base_url = 'https://place.map.kakao.com/10332413#comment'
        self.values = []
        self.columns = ['date', 'star', 'review']

    def start_browser(self):
        """
        selenium을 이용해 브라우저를 시작하는 메소드

        우선 첫번째 리뷰를 로드 시도하고, 실패할 시 exception을 raise 합니다.
        """
        print("Kakaomap 크롤러입니다")
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) # 옵션 적용
        self.driver.get(self.base_url)
        time.sleep(3) # 페이지 초기 로드를 위한 대기

        # 리뷰 섹션이 로드될 때까지 기다리기


        try:
        
            WebDriverWait(self.driver, 20).until( # 대기 시간을 넉넉하게 20초로 늘립니다.
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.inner_review"))
            )
            print("첫번째 리뷰 로드 성공")
        except Exception as e:
            print(f"리뷰 요소 로드 대기 중 오류 발생 또는 시간 초과: {e}")
            # 오류 발생 시 드라이버 종료
            if self.driver:
                self.driver.quit()
                self.driver = None # 드라이버 객체를 None으로 설정하여 다시 사용할 경우 오류 방지
            raise # 예외를 다시 발생시켜 상위 호출자에게 알립니다.
        

    def scrape_reviews(self):
        """
        리뷰를 수집하는 메서드 (start_browser 이후 실행 필수)

        스크롤을 통해 데이터를 수집합니다.
        각 리뷰의 날짜, 별점, 리뷰 내용을 추출하여 저장합니다.
        """
        last_h = self.driver.execute_script("return document.body.scrollHeight;") # last_h 초기화
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5) # 콘텐츠 로드를 위해 대기 시간 증가

            new_h = self.driver.execute_script("return document.body.scrollHeight;")
            if new_h == last_h: #더이상 스크롤 X
                print("더 이상 스크롤할 수 없습니다. 페이지 하단에 도달했거나 콘텐츠가 더 없습니다.")
                break
            last_h = new_h


        self.values = [] # 새로운 리뷰 데이터를 저장하기 위해 초기화

        # 로드된 페이지 소스에서 리뷰 정보 추출
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        review_blocks = soup.find_all('div', attrs={'class': 'inner_review'})

        print(f"총 {len(review_blocks)}개의 리뷰 블록을 찾았습니다.")

        for i, row in enumerate(review_blocks):
            blank = [] # 날짜, 별점, 리뷰 순서대로 저장

            # 날짜 추출
            date_element = row.find('span', attrs={'class' : 'txt_date'})
            date = date_element.get_text().strip() if date_element else 'None'
            blank.append(date)

            # 별점 추출
            stars_element = row.find('span', attrs={'class': 'starred_grade'})
            if stars_element:
                ratings = stars_element.find_all('span', attrs={'class': 'screen_out'})
                if len(ratings) >= 2:
                    star_rating = ratings[1].get_text().strip()
                    blank.append(star_rating)
                else:
                    blank.append('None')
            else:
                blank.append('None')

            # 리뷰 내용 추출
            review_element = row.find('p', attrs={'class': 'desc_review'})
            review_text = review_element.get_text().strip() if review_element else 'None'
            blank.append(review_text)

            self.values.append(blank)
        print(f"{len(self.values)}개의 리뷰를 수집했습니다.")
        self.driver.quit()
        print("드라이버를 종료하였습니다.")


    def save_to_database(self):
        """
        데이터를 CSV 파일로 저장하는 함수
        output_dir에 'reviews_kakaomap.csv' 파일을 저장합니다.
        """
        self.df = pd.DataFrame(self.values, columns=self.columns) # columns 인자 명시
        output_path = os.path.join(self.output_dir, 'reviews_kakaomap.csv')
        self.df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"리뷰가 {output_path}에 저장되었습니다.")