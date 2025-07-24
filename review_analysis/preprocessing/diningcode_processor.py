from review_analysis.preprocessing.base_processor import BaseDataProcessor
from konlpy.tag import Okt
from gensim import corpora, models
import pyLDAvis.gensim_models as gensimvis
import pyLDAvis

import pandas as pd
import numpy as np
import os

class DiningProcessor(BaseDataProcessor):
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
        self.df=self.df.dropna() 

        #이상치 처리

        mask_star=self.df['score'].between(1,5) #1~5점 벗어난 데이터들 제거
        self.df=self.df.loc[mask_star].copy()


        #텍스트 데이터 전처리

        mask_review=self.df['text'].str.len().between(5,200) #최소 5자 이상 ~ 200자 이하만 추출
        self.df=self.df.loc[mask_review].copy()
        self.df['text']=self.df['text'].str.replace(r'[^0-9A-Za-z가-힣\s\.\,\!\?]', '', regex=True)



        pass
    
    def feature_engineering(self,num_topics=5, num_words=10):

        """
        파생 변수 생성 

        파생 변수: 주말 여부, 요일, 월(제철? 계절?)

        dow: dayofweek 함수를 통해 변환된 0~6 정수값

        dow_name: 0~6을 월~일로 매핑

        is_weekend: 토요일, 일요일 여부

        month: 1~12월, 정수

        텍스트 분석:
        - 명사 기반 토큰 추출 (Okt)
        - BoW 벡터화 및 Gensim 기반 LDA 토픽 모델링
        - pyLDAvis를 이용한 시각화 결과 plots/에 저장

        """

        #요일 생성

        self.df['date']= pd.to_datetime(self.df['date'], errors='coerce')

        self.df['dow']=self.df['date'].dt.dayofweek  #0: 월 ~ 6: 일

        dow_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'} #매핑

        self.df['dow_name']=self.df['dow'].map(dow_map)


        self.df['is_weekend'] = self.df['dow'].isin([5, 6])  #5,6: 토,일

        self.df['month'] = self.df['date'].dt.month  

        print("[INFO] 텍스트 토큰화 및 LDA 분석 중...")
        okt = Okt()
        self.df['tokens'] = self.df['text'].apply(lambda x: [w for w in okt.nouns(x) if len(w) > 1])

        dictionary = corpora.Dictionary(self.df['tokens'])
        corpus = [dictionary.doc2bow(text) for text in self.df['tokens']]
        lda_model = models.LdaModel(corpus=corpus,
                                    id2word=dictionary,
                                    num_topics=num_topics,
                                    random_state=42,
                                    passes=10)

        print("[INFO] 주요 토픽:")
        for idx, topic in lda_model.print_topics(num_topics=num_topics, num_words=num_words):
            print(f"Topic {idx + 1}: {topic}")

        print("[INFO] pyLDAvis 시각화 생성 중...")
        vis = gensimvis.prepare(lda_model, corpus, dictionary)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        plot_dir = os.path.join(base_dir, 'plots')
        os.makedirs(plot_dir, exist_ok=True)

        vis_path = os.path.join(plot_dir, "lda_visualization_dining.html")
        pyLDAvis.save_html(vis, vis_path)
        print(f"[INFO] LDA 시각화가 {vis_path} 에 저장되었습니다.")


    def save_to_database(self):

        """
        데이터베이스에 저장
        """


        output_path = os.path.join(self.output_dir, 'preprocessed_reviews_diningcode.csv')
        self.df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"전처리 결과가 {output_path}에 저장되었습니다.")
