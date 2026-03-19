import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
st.set_page_config(page_title="2026 hince Sales Master", layout="wide")

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
        .metric-value { color: #A37F7D; font-size: 22px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 16px !important; font-weight: 700 !important; margin-bottom: 15px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
@st.cache_data(ttl=5)
def get_master_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        response = supabase.table("SS_Master").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"SS_Master 로드 실패: {e}")
        return pd.DataFrame()

df_raw = get_master_data()

# --- 3. 컬럼 매핑 및 전처리 (KeyError 원천 봉쇄) ⭐ ---
def robust_preprocess(df):
    if df.empty: return df
    
    # 공백 제거 처리
    df.columns = [str(c).strip() for c in df.columns]
    
    # 1. AJ열 (연도) 찾기 (컬럼명에 '연도'가 포함된 것 혹은 'AJ' 관련)
    col_year = next((c for c in df.columns if '연도' in c or c == 'Y'), None)
    if col_year:
        df['year_val'] = pd.to_numeric(df[col_year], errors='coerce').fillna(0).astype(int)
    else:
        df['year_val'] = 0

    # 2. A열 (월) 찾기 (컬럼명이 '-'이거나 '월'이 포함된 첫 번째 열)
    col_month = next((c for c in df.columns if c == '-' or '월' in c), None)
    if col_month:
        # '3월' -> 3 추출 / 값이 숫자면 그대로 사용
        df['month_idx'] = df[col_month].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
        df['month_name'] = df[col_month]
    else:
        df['month_idx'] = 0
        df['month_name'] = "미지정"

    # 3. C열 (거래처) 찾기
    col_customer = next((c for c in df.columns if 'CUSTOMER' in c or '거래처' in c), None)
    df['customer_name'] = df[col_customer] if col_customer else "기타 거래처"

    # 4. M열 (매출액) 찾기
    col_revenue = next((c for c in df.columns if '매출액' in c), None)
    if col_revenue:
        # 숫자가 아닌 문자 제거 후 수치화
        df['rev_num'] = pd.to_numeric(df[col_revenue].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    else:
        df['rev_num'] = 0

    return df

df_proc = robust_preprocess(df_raw)

# --- 4. 2026년 필터링 ---
if not df_proc.empty and 'year_val' in df_proc.columns:
    # 연도가 2026인 것만 추출하고, 추출한 뒤에 월 순서대로 정렬
    f_df = df_proc[df_proc['year_val'] == 2026].sort_values('month_idx')
else:
    f_df = pd.DataFrame()

# --- 5. 화면 출력 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 26px;">📊 2026 hince Sales Master 분석</h1>', unsafe_allow_html=True)

if f_df.empty:
    st.info("💡 2026년 데이터를 찾을 수 없습니다.")
    with st.expander("🧐 시스템 진단: DB 컬럼 상태 확인"):
        st.write("감지된 컬럼들:", df_proc.columns.tolist())
        st.write("발견된 연도 데이터 목록:", df_proc['year_val'].unique() if 'year_val' in df_proc.columns else "없음")
        st.write("원본 데이터 샘플 (상위 5건):", df_raw.head(5))
else:
    # KPI 카드
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 총 누적 매출액</div><div class="metric-value">₩{f_df["rev_num"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2:
        # 3월 매출만 합산 (사용자 요청)
        mar_rev = f_df[f_df['month_idx'] == 3]['rev_num'].sum()
        st.markdown(f'<div class="metric-card"><div class="metric-label">3월 확정 매출액</div><div class="metric-value">₩{mar_rev:,.0f}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">활성 거래처 수</div><div class="metric-value">{f_df["customer_name"].nunique()} 개</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 그래프: 월별 거래처 매출 현황 ---
    st.markdown("### ■ 월별 거래처 매출 추이")
    
    # 집계
    chart_df = f_df.groupby(['month_name', 'month_idx', 'customer_name'])['rev_num'].sum().reset_index().sort_values('month_idx')
    
    # 색상 테마
    hince_palette = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

    # 막대 그래프
    fig = px.bar(
        chart_df, x='month_name', y='rev_num', color='customer_name',
        text='rev_num', color_discrete_sequence=hince_palette
    )
    
    fig.update_traces(
        texttemplate='%{text:,.0f}', textposition='inside', insidetextanchor='middle'
    )
    
    # 상단 총합 레이블
    totals = chart_df.groupby('month_name')['rev_num'].sum().reset_index()
    for _, row in totals.iterrows():
        fig.add_annotation(
            x=row['month_name'], y=row['rev_num'],
            text=f"<b>₩{row['rev_num']:,.0f}</b>",
            showarrow=False, yshift=10
        )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title=None,
        height=450, margin=dict(t=30),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 하단 데이터
    st.markdown("### 📋 2026 상세 내역")
    # 보여줄 컬럼 선택
    v_cols = ['month_name', 'customer_name', 'Type', '매출액']
    avail_v = [c for c in v_cols if c in f_df.columns or c in ['month_name', 'customer_name']]
    st.dataframe(f_df.sort_values(['month_idx', 'rev_num'], ascending=[True, False])[avail_v], use_container_width=True, hide_index=True)