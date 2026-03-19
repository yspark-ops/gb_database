import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (Rose-Beige) ---
st.set_page_config(page_title="2026 hince SS_Master Analysis", layout="wide")

def local_css():
    st.markdown("""
        <style>
        .main { background-color: #F8F9FA; }
        .metric-card {
            background-color: #FFFFFF;
            padding: 20px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            text-align: center;
            border: 1px solid #F0F0F0;
        }
        .metric-label { color: #6B7280; font-size: 14px; font-weight: 500; margin-bottom: 8px; }
        .metric-value { color: #A37F7D; font-size: 26px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-weight: 700 !important; margin-bottom: 20px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 (SS_Master 전용) ---
@st.cache_data(ttl=5)
def get_master_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        # SS_Master 테이블만 호출
        response = supabase.table("SS_Master").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"SS_Master 데이터 로드 실패: {e}")
        return pd.DataFrame()

df_all = get_master_data()

if df_all.empty:
    st.warning("⚠️ SS_Master 테이블에 데이터가 없습니다.")
    st.stop()

# --- 3. 데이터 전처리 (사용자 요청 로직 기반) ⭐ ---

def preprocess_master(df):
    # 컬럼명 앞뒤 공백 제거
    df.columns = [c.strip() for c in df.columns]
    
    # 1) AJ열(연도) 인식: 2026 필터링을 위해 숫자화
    if '연도' in df.columns:
        df['year_val'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    
    # 2) A열(월: '-') 인식 및 정렬용 인덱스 생성
    if '-' in df.columns:
        # '3월' -> 3 추출
        df['month_idx'] = df['-'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    
    # 3) M열(매출액) 숫자형 변환 (콤마, 원화기호 등 제거)
    if '매출액' in df.columns:
        df['매출액_num'] = pd.to_numeric(df['매출액'].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    
    return df

df_proc = preprocess_master(df_all)

# --- 4. 2026년 데이터 필터링 ---
# AJ열에서 2026 찾기
f_df = df_proc[df_proc['year_val'] == 2026].sort_values('month_idx')

# --- 5. 메인 대시보드 UI ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 28px;">📊 2026 hince Sales Dashboard (Master)</h1>', unsafe_allow_html=True)

if f_df.empty:
    st.info("💡 현재 2026년(AJ열 기준) 데이터가 검색되지 않습니다. 데이터의 연도 값을 확인해주세요.")
else:
    # KPI 카드 섹션
    k1, k2, k3 = st.columns(3)
    with k1:
        total_rev = f_df['매출액_num'].sum()
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 총 누적 매출액</div><div class="metric-value">₩{total_rev:,.0f}</div></div>', unsafe_allow_html=True)
    with k2:
        avg_rev = total_rev / f_df['-'].nunique() if f_df['-'].nunique() > 0 else 0
        st.markdown(f'<div class="metric-card"><div class="metric-label">월평균 매출액</div><div class="metric-value">₩{avg_rev:,.0f}</div></div>', unsafe_allow_html=True)
    with k3:
        cust_cnt = f_df['CUSTOMER'].nunique()
        st.markdown(f'<div class="metric-card"><div class="metric-label">활성 거래처 수</div><div class="metric-value">{cust_cnt} 개</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 메인 그래프: 월별 거래처 매출 현황 ---
    st.markdown("### ■ 월별 거래처 매출 현황 (SS_Master)")
    
    # 데이터 집계 (A열: 월, C열: CUSTOMER, M열: 매출액)
    chart_df = f_df.groupby(['-', 'month_idx', 'CUSTOMER'])['매출액_num'].sum().reset_index().sort_values('month_idx')
    
    # hince 테마 색상 팔레트
    hince_palette = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

    # 누적 막대 그래프 생성
    fig = px.bar(
        chart_df, 
        x='-', 
        y='매출액_num', 
        color='CUSTOMER',
        text='매출액_num', # 막대 안에 매출액 표시
        color_discrete_sequence=hince_palette
    )
    
    # 막대 내부 숫자 포맷 및 스타일
    fig.update_traces(
        texttemplate='%{text:,.0s}', # 단위 약어 표시 (예: 120M)
        textposition='inside',
        insidetextanchor='middle',
        marker_line_width=0
    )
    
    # 막대 상단에 월별 총합 표시
    totals = chart_df.groupby('-')['매출액_num'].sum().reset_index()
    for _, row in totals.iterrows():
        fig.add_annotation(
            x=row['-'], y=row['매출액_num'],
            text=f"<b>₩{row['매출액_num']:,.0f}</b>",
            showarrow=False, yshift=10, font=dict(size=12, color="#333333")
        )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title=None,
        yaxis_title="매출액 (KRW)",
        height=550,
        margin=dict(t=40),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None)
    )
    fig.update_yaxes(showgrid=True, gridcolor='#EEEEEE')
    
    st.plotly_chart(fig, use_container_width=True)

    # 하단 상세 데이터 테이블
    st.markdown("### 📋 2026 상세 매출 내역 (SS_Master)")
    # 사용자 요청 열: A(-), C(CUSTOMER), M(매출액) 위주로 구성
    display_cols = ['-', 'CUSTOMER', 'Type', '출고_수량', '매출액', '연도']
    avail_cols = [c for c in display_cols if c in f_df.columns]
    
    # 정렬 후 출력
    st.dataframe(f_df.sort_values('month_idx')[avail_cols], use_container_width=True, hide_index=True)

# 💡 사이드바 정보 (데이터 확인용)
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    st.write("🔍 **SS_Master 열 매칭 확인**")
    st.write(f"- 연도(AJ): {'연도' in df_proc.columns}")
    st.write(f"- 월(A): {'-' in df_proc.columns}")
    st.write(f"- 거래처(C): {'CUSTOMER' in df_proc.columns}")
    st.write(f"- 매출액(M): {'매출액' in df_proc.columns}")
    if not f_df.empty:
        st.success("2026년 데이터를 성공적으로 찾았습니다!")