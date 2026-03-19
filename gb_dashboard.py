import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from supabase import create_client, Client

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="hince 2026 Sell-In Analysis", layout="wide")

# hince 브랜드 테마 스타일
st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    h2 { color: #A37F7D; font-size: 20px; border-left: 5px solid #A37F7D; padding-left: 10px; margin-top: 30px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 데이터 로딩 (출고_RAW 위주) ---
@st.cache_data(ttl=5)
def get_raw_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        response = supabase.table("출고_RAW").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"출고_RAW 로드 실패: {e}")
        return pd.DataFrame()

df_raw = get_raw_data()

# --- 3. 데이터 전처리 (사용자 요청 로직 기반) ⭐ ---
def preprocess_sell_in(df):
    if df.empty: return df
    
    # 공백 제거
    df.columns = [str(c).strip() for c in df.columns]

    # [S열: Y (연도)] - 숫자 변환
    if 'Y' in df.columns:
        df['year_val'] = pd.to_numeric(df['Y'], errors='coerce').fillna(0).astype(int)
    
    # [Q열: 대 (카테고리)] - '아이', '립', '치크' 등 데이터
    # 만약 컬럼명이 '대' 혹은 '카테고리' 등인 경우 확인
    df['cat_display'] = df['대'] if '대' in df.columns else df.columns[16] # 17번째(Q) 열 추적

    # [N열: 매출취합용_공급가액(원화기준)] - 금액 데이터
    rev_col = '매출취합용_공급가액(원화기준)'
    if rev_col in df.columns:
        df['revenue_num'] = pd.to_numeric(df[rev_col].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    else:
        df['revenue_num'] = 0

    return df

df_proc = preprocess_sell_in(df_raw)

# --- 4. 2026년 데이터 필터링 (S열=2026) ---
f_2026 = df_proc[df_proc['year_val'] == 2026].copy()

# --- 5. 대시보드 출력 ---
st.title("📊 2026 hince Sell-In 심층 분석")

if f_2026.empty:
    st.info("💡 2026년 데이터가 아직 수집되지 않았습니다. S열(연도)을 확인해주세요.")
else:
    # --- 메인 상단: KPI ---
    k1, k2, k3 = st.columns(3)
    k1.metric("2026 총 누적 Sell-In 금액", f"₩{f_2026['revenue_num'].sum():,.0f}")
    k2.metric("최고 구매 카테고리", f_2026.groupby('cat_display')['revenue_num'].sum().idxmax())
    k3.metric("누적 거래 채널 수", f"{f_2026['채널명'].nunique()} 개사")

    st.markdown("---")

    # --- [사용자 요청] 새로운 그래프: 거래처별 카테고리 구매 현황 ---
    st.markdown("## ■ 2026년 거래처별 제품 카테고리 구매 비중")
    st.caption("출고_RAW 시트 S열(2026년), Q열(카테고리), N열(매출액) 데이터 기반 누적 분석")

    # 데이터 집계: 채널명과 카테고리(대)별 금액 합산
    analysis_df = f_2026.groupby(['채널명', 'cat_display'])['revenue_num'].sum().reset_index()
    
    # 거래처별 전체 매출 규모로 정렬하여 보기 좋게 표시 (매출 큰 거래처가 위로)
    total_rev_per_channel = analysis_df.groupby('채널명')['revenue_num'].sum().sort_values(ascending=True).index
    
    # hince 고유의 다채로운 팔레트
    hince_colors = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

    # 가로형 누적 막대 그래프 생성 (Stacked Bar Chart)
    fig = px.bar(
        analysis_df, 
        y='채널명', 
        x='revenue_num', 
        color='cat_display',
        orientation='h',
        text_auto=',.0f', # 막대 안에 금액 수치 표시
        title=None,
        color_discrete_sequence=hince_colors,
        category_orders={"채널명": total_rev_per_channel} # 매출액 순으로 나열
    )

    # 차트 디자인 세밀 조정
    fig.update_traces(
        textfont_size=10, 
        textposition='inside', 
        insidetextanchor='middle',
        marker_line_width=0
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title="총 구매 금액 (원)",
        yaxis_title=None,
        height=600,
        legend_title_text="카테고리",
        margin=dict(t=10, b=10, l=10, r=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # 그리드 추가하여 읽기 편하게
    fig.update_xaxes(showgrid=True, gridcolor='#EEEEEE')
    
    st.plotly_chart(fig, use_container_width=True)

    # 하단 카테고리별 요약 요약
    st.markdown("### 📋 2026 카테고리별 매출 비중 요약")
    cat_summary = f_2026.groupby('cat_display')['revenue_num'].agg(['sum', 'count']).rename(columns={'sum': '총 매출액', 'count': '출고 건수'})
    cat_summary['비중(%)'] = (cat_summary['총 매출액'] / cat_summary['총 매출액'].sum() * 100).round(1)
    st.table(cat_summary.sort_values('총 매출액', ascending=False).style.format({'총 매출액': '{:,.0f}원', '비중(%)': '{:.1f}%'}))