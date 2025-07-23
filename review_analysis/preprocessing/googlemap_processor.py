from review_analysis.preprocessing.base_processor import BaseDataProcessor
from dateutil.relativedelta import relativedelta

import pandas as pd
import numpy as np
import os


class GoogleProcessor(BaseDataProcessor):
    def __init__(self, input_path: str, output_path: str):
        super().__init__(input_path, output_path)
        self.df=pd.read_csv(input_path) #파일 열기

    def preprocess(self):

        """
        전처리 과정

        결측치 제거
        이상치 처리
        텍스트 데이터 전처리

        """

        #결측치 제거
        self.df=self.df.dropna() # 결측치 포함 행 완전 제거

        #이상치 처리

        mask_star=self.df['rating'].between(1,5) #1~5점 벗어난 데이터들 제거
        self.df=self.df.loc[mask_star].copy()


        #텍스트 데이터 전처리

        mask_review=self.df['content'].str.len().between(5,200) #최소 5자 이상 ~ 200자 이하만 추출
        self.df=self.df.loc[mask_review].copy()
        self.df['content']=self.df['content'].str.replace(r'[^0-9A-Za-z가-힣\s\.\,\!\?]', '', regex=True)
    
    def feature_engineering(self):
        """
        파생 변수 생성:
        - 상대 날짜(date) → 절대 날짜 추정 (date_est)
        - est_year / est_month
        - 추정 요일 dow (0=월, ..., 6=일)
        - dow_name: 요일 한글명
        - is_weekend: 토/일 여부
        """

        if 'date' not in self.df.columns:
            raise KeyError("'date' 컬럼이 없습니다. 입력 CSV에 date가 포함되어야 합니다.")

        df = self.df  # 직접 수정

        now = pd.Timestamp.now(tz='Asia/Seoul')
        s = df['date'].astype(str).str.strip()

        # 숫자 + 단위 추출 (년, 달, 개월 등)
        m = s.str.extract(r'(?P<num>\d+)\s*(?P<unit>년|개월|달)\s*전')
        num = pd.to_numeric(m['num'], errors='coerce')
        unit = m['unit']

        # 개월 수 계산
        months = pd.Series(np.nan, index=df.index, dtype='float')
        months.loc[unit.isin(['달', '개월'])] = num.loc[unit.isin(['달', '개월'])]
        months.loc[unit == '년'] = num.loc[unit == '년'] * 12.0

        # 추정 날짜 계산
        def _rel_months_to_date(m):
            if pd.isna(m):
                return pd.NaT
            return now - relativedelta(months=int(m))

        df['date_est'] = months.apply(_rel_months_to_date)

        # 파생 변수: 연 / 월
        df['est_year'] = df['date_est'].dt.year
        df['est_month'] = df['date_est'].dt.month

        # 다시 self.df에 저장
        self.df = df



    def save_to_database(self):
        """
        database 폴더에 저장

        """

        output_path = os.path.join(self.output_dir, 'preprocessed_reviews_googlemap.csv')
        self.df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"전처리 결과가 {output_path}에 저장되었습니다.")
