import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
st.set_page_config(page_title="2026 hince Category Analysis", layout="wide")

def local_css():
    st.markdown("""
        <style>
        .main { background-color: #F8F9FA; }
        .metric-card {
            background-color: #FFFFFF;
            padding: 15px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            text-align: center;
            border: 1px solid #F0F0F0;
        }
        .metric-label { color: #6B7280; font-size: 13px; font-weight: 500; margin-bottom: 5px; }
        .metric-value { color: #A37F7D; font-size: 24px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 18px !important; font-weight: 700 !important; margin-bottom: 20px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. 데이터 로드 (출고_RAW) ---
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

df_src = get_raw_data()

# --- 3. 데이터 전처리 (2026 찾기 및 S/Q/N열 매핑) ⭐ ---
def force_preprocess_raw(df):
    if df.empty: return df
    
    # 1) 연도(S열: Y) 인식 로직
    # 컬럼명이 'Y'거나 19번째 열을 찾아 강제로 숫자화
    y_col = 'Y' if 'Y' in df.columns else df.columns[18] # S열은 19번째
    df['year_int'] = pd.to_numeric(df[y_col].astype(str).str.extract(r'(20\d{2})')[0], errors='coerce').fillna(0).astype(int)
    
    # 2) 카테고리(Q열: 대) 인식 로직
    q_col = '대' if '대' in df.columns else df.columns[16] # Q열은 17번째
    df['category_name'] = df[q_col].astype(str).str.strip()
    
    # 3) 판매금액(N열: 매출취합용_공급가액(원화기준)) 인식 로직
    n_col = '매출취합용_공급가액(원화기준)' if '매출취합용_공급가액(원화기준)' in df.columns else df.columns[13] # N열은 14번째
    df['amount_num'] = pd.to_numeric(df[n_col].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    
    # 거래처명 (채널명)
    c_col = '채널명' if '채널명' in df.columns else df.columns[3]
    df['customer_name'] = df[c_col].astype(str).str.strip()

    return df

df_proc = force_preprocess_raw(df_src)

# --- 4. 2026년 데이터만 추출 ---
f_df = df_proc[df_proc['year_int'] == 2026].copy()

# --- 5. 메인 대시보드 출력 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 26px;">📊 2026 거래처별 제품군 분석 (Sell-In)</h1>', unsafe_allow_html=True)

if f_df.empty:
    st.warning("⚠️ 2026년 데이터가 여전히 잡히지 않습니다. 시스템 진단을 시도합니다.")
    with st.expander("🕵️ 데이터 내부 분석 결과"):
        st.write("발견된 연도들 (Y열 기준):", sorted(df_proc['year_int'].unique()))
        if not df_proc.empty:
            st.write("Y열 원본 데이터 샘플:", df_proc['Y'].head(10).tolist() if 'Y' in df_proc.columns else "Y열 없음")
        st.info("💡 2026 데이터가 분명히 있다면, Y열에 숫자 대신 '2026.0' 등으로 들어가 있지는 않은지 확인해주세요.")
else:
    # KPI 카드
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 누적 Sell-In 금액</div><div class="metric-value">₩{f_df["amount_num"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2:
        top_cat = f_df.groupby('category_name')['amount_num'].sum().idxmax()
        st.markdown(f'<div class="metric-card"><div class="metric-label">인기 품목 카테고리</div><div class="metric-value">{top_cat}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">활성 거래처 수</div><div class="metric-value">{f_df["customer_name"].nunique()} 개</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 핵심 그래프: 거래처별 카테고리 구매 비중 ---
    st.markdown("### ■ 거래처별 카테고리 구매 분석 (금액 합산 기준)")
    
    # 데이터 집계
    chart_df = f_df.groupby(['customer_name', 'category_name'])['amount_num'].sum().reset_index()
    
    # 가독성을 위해 매출이 높은 거래처 순서대로 정렬
    cust_order = chart_df.groupby('customer_name')['amount_num'].sum().sort_values(ascending=True).index.tolist()
    
    hince_palette = px.colors.qualitative.Pastel + px.colors.qualitative.Safe

    # 가로 누적 막대 그래프 생성
    fig = px.bar(
        chart_df, 
        y='customer_name', 
        x='amount_num', 
        color='category_name',
        orientation='h',
        text_auto=',.0f', # 막대 안에 금액 수치 표시
        category_orders={'customer_name': cust_order},
        color_discrete_sequence=hince_palette
    )
    
    fig.update_traces(
        textfont_size=10, 
        textposition='inside',
        insidetextanchor='middle',
        marker_line_width=0
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title="총 구매액 (N열: 공급가액 합계)",
        yaxis_title=None,
        height=600,
        margin=dict(t=10, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
    )
    fig.update_xaxes(showgrid=True, gridcolor='#EEEEEE')
    
    st.plotly_chart(fig, use_container_width=True)

    # 하단 상세 요약 테이블
    st.markdown("### 📋 2026 상세 카테고리 집계")
    st.dataframe(
        chart_df.sort_values(['customer_name', 'amount_num'], ascending=[True, False]), 
        use_container_width=True, 
        hide_index=True
    )