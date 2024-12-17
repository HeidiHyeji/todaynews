import requests
import streamlit as st
import json
from datetime import datetime, timedelta
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast, pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

# KoBART 모델과 토크나이저 로드 함수
@st.cache_resource  # Streamlit에서 모델을 캐싱하여 로드 속도 개선
def load_kobart_model():
    model = BartForConditionalGeneration.from_pretrained('gogamza/kobart-summarization')
    tokenizer = PreTrainedTokenizerFast.from_pretrained('gogamza/kobart-summarization')
    return model, tokenizer

# 추출적 요약 함수
def extractive_summary(content, n=3):
    """
    추출적 요약: TF-IDF 기반으로 중요 문장 n개 추출
    """
    sentences = content.split('. ')
    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform(sentences)
    sentence_scores = tfidf_matrix.sum(axis=1).flatten().tolist()[0]
    ranked_sentences = np.argsort(sentence_scores)[::-1][:n]  # 상위 n개 문장 선택
    extracted_summary = '. '.join([sentences[i] for i in ranked_sentences])
    return extracted_summary

# 생성적 요약 함수
def generative_summary(content, model, tokenizer, max_length=64, min_length=16):
    """
    KoBART 생성적 요약
    """
    inputs = tokenizer.encode("summarize: " + content, return_tensors="pt", max_length=1024, truncation=True)
    summary_ids = model.generate(
        inputs,
        max_length=max_length,
        min_length=min_length,
        length_penalty=2.0,
        num_beams=4,
        early_stopping=True
    )
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary

# 하이브리드 요약 함수
def hybrid_summary(content, model, tokenizer, extract_n=3):
    """
    추출적 요약 + 생성적 요약을 결합
    """
    extracted = extractive_summary(content, n=extract_n)
    generated = generative_summary(extracted, model, tokenizer)
    return generated

# 오늘 날짜와 내일 날짜 계산
today = datetime.today()
tomorrow = today + timedelta(days=1)

# 날짜를 'YYYY-MM-DD' 형식으로 변환
from_date = today.strftime('%Y-%m-%d')
until_date = tomorrow.strftime('%Y-%m-%d')

# 기본 API 요청 매개변수
params = {
    "argument": {
        "query": "롯데이노베이트 OR 이노베이트 OR 롯데 AND AI",  # 초기 query (변경 가능)
        "published_at": {
            "from": from_date,
            "until": until_date
        },
        "category": [
            "008000000"
        ],
        "sort": {
            "date": "desc"
        },
        "return_from": "0",
        "return_size": "10000",
        "fields": [
            "news_id",
            "published_at",
            "title",
            "content",
            "provider",
            "byline",
            "category",
            "category_incident",
            "provider_link_page",
            "printing_page"
        ]
    },
    "access_key": "newstoresample"
}

headers = {'Content-type': 'application/json'}

# Streamlit에서 사용자가 입력한 키워드 받아오기
st.markdown(f"<h1 style='color: rgb(237, 27, 36); text-align: center;'>📰 오늘의 롯데 <span style='font-size: 14px; color: black;'>- {from_date}</span></h1>", unsafe_allow_html=True)

# 기본 키워드를 입력하는 필드 (초기 query문에 포함)
default_keywords = ["롯데이노베이트", "이노베이트", "롯데 AND AI"]
keywords_input = st.text_input("키워드를 입력하세요 (separate by 콤마, AND)", ", ".join(default_keywords))

# 입력된 키워드에 따라 query 변경
if keywords_input:
    keywords = [keyword.strip() for keyword in keywords_input.split(",")]
    query = " OR ".join(keywords)
else:
    query = "롯데이노베이트 OR 이노베이트 OR 롯데 AND AI"

# API 요청 매개변수에 query 반영
params["argument"]["query"] = query

# KoBART 모델 로드
model, tokenizer = load_kobart_model()

# API 요청을 보내고 결과를 받음
response = requests.post("https://www.newstore.or.kr/api-newstore/v1/search/newsAllList.json", json=params, headers=headers)

# 응답이 정상적인 경우
if response.status_code == 200:
    result = response.json()
    
    # 'returnObject'가 문자열인 경우 다시 JSON으로 파싱
    return_object = json.loads(result.get('returnObject', '{}'))
    
    # 'documents' 리스트 추출
    documents = return_object.get('documents', [])
    
    # 검색된 뉴스 리스트 출력
    if documents:
        st.write(f"📢 총 {len(documents)}건의 오늘의 롯데 소식을 알려드립니다! ")
        
        for document in documents:
            title = document.get('title', 'No Title')
            content = document.get('content', 'No Content')
            provider = document.get('provider', 'No Provider')
            provider_link_page = document.get('provider_link_page', 'No Link')
            published_at = document.get('published_at', 'No Date')

            # 날짜 포맷 변경: ISO 8601 형식에서 사람이 읽을 수 있는 형식으로 변환
            published_at_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            formatted_date = published_at_date.strftime('%Y-%m-%d %H:%M:%S')

            # 하이브리드 요약 실행
            summarized_content = hybrid_summary(content, model, tokenizer)

            # 제목을 클릭하면 링크로 이동 (제목은 굵은 글씨로 표시)
            with st.expander(f"**{title}**"):
                # 요약된 뉴스 내용 표시
                st.write(f"**요약 내용:** {summarized_content}")

                # 전체 뉴스 내용 표시
                st.write(f"**전체 뉴스:** {content}")
                
                # provider와 링크를 한 줄에 표시
                st.markdown(f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                            f'<span>Provider: {provider}</span>'
                            f'<a href="{provider_link_page}" target="_blank" style="text-decoration: none;">[Go to link]</a>'
                            f'</div>', unsafe_allow_html=True)

                # 날짜 표시
                st.markdown(f"**Published at: {formatted_date}**", unsafe_allow_html=True)
    else:
        # 결과가 없으면 "무소식이 희소식입니다!" 출력
        st.write("무소식이 희소식입니다!😌")
else:
    # 응답이 실패한 경우
    st.error("Failed to fetch data from the API.")
