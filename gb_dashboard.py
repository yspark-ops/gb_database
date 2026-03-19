import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
st.set_page_config(page_title="hince 2026 Q1 Analysis", layout="wide")

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
        }
        .metric-value { color: #A37F7D; font-size: 26px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-weight: 700; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
@st.cache_data(ttl=5)
def get_supabase_data(table_name):
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"{table_name} 로드 실패: {e}")
        return pd.DataFrame()

df_raw = get_supabase_data("출고_RAW")
df_master = get_supabase_data("SS_Master")

# --- 3. 데이터 전처리 및 필터링 (사용자 요청 로직) ⭐ ---

# 3-1. 출고_RAW 전처리 (S열: Y, T열: M)
if not df_raw.empty:
    # 숫자형 변환
    df_raw['Y'] = pd.to_numeric(df_raw['Y'], errors='coerce')
    df_raw['M'] = pd.to_numeric(df_raw['M'], errors='coerce')
    df_raw['제품판매수량'] = pd.to_numeric(df_raw['제품판매수량'], errors='coerce').fillna(0)
    df_raw['매출취합용_공급가액(원화기준)'] = pd.to_numeric(df_raw['매출취합용_공급가액(원화기준)'], errors='coerce').fillna(0)
    
    # ⭐ 2026년 1~3월 데이터만 추출
    f_raw = df_raw[(df_raw['Y'] == 2026) & (df_raw['M'].isin([1, 2, 3]))].copy()
    f_raw['월_표시'] = f_raw['M'].apply(lambda x: f"{int(x):02d}월")
else:
    f_raw = pd.DataFrame()

# 3-2. SS_Master 매출액 매칭 (AJ열: 연도, B열: 월, D열: CUSTOMER, N열: 매출액)
if not df_master.empty:
    # AJ열(연도) 2026, B열(월) '3월' 필터링
    # (주의: B열이 '3월' 문자열인지 확인 필요)
    f_master_march = df_master[(df_master['연도'] == 2026) & (df_master['월'] == '3월')].copy()
    f_master_march['매출액'] = pd.to_numeric(f_master_march['매출액'], errors='coerce').fillna(0)
    
    # 3월 총 매출액 계산 (SS_Master 기준)
    march_total_revenue = f_master_march['매출액'].sum()
else:
    march_total_revenue = 0

# --- 4. 메인 화면 ---
st.markdown(f'<h1 style="color: #A37F7D;">📊 2026년 1분기 Sell-In 집중 분석</h1>', unsafe_allow_html=True)

if f_raw.empty:
    st.warning("⚠️ 출고_RAW 시트에서 2026년 1~3월 데이터를 찾을 수 없습니다. (S열과 T열 확인)")
else:
    # KPI 섹션
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">1~3월 총 출고 수량</div><div class="metric-value">{f_raw["제품판매수량"].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
    with k2:
        # SS_Master에서 가져온 3월 매출액 표시
        st.markdown(f'<div class="metric-card"><div class="metric-label">3월 확정 매출액 (Master)</div><div class="metric-value">₩{march_total_revenue:,.0f}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">출고 진행 거래처</div><div class="metric-value">{f_raw["채널명"].nunique()} 개</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 첫 번째 그래프: 월별 거래처 출고 현황 ---
    st.markdown("### ■ 월별 거래처 출고 현황 (Sell-In)")
    
    # 월별/거래처별 집계
    chart_data = f_raw.groupby(['월_표시', 'M', '채널명'])['제품판매수량'].sum().reset_index().sort_values('M')
    
    # 누적 막대 그래프 생성
    fig = px.bar(
        chart_data, 
        x='월_표시', 
        y='제품판매수량', 
        color='채널명',
        text='제품판매수량', # 막대 안에 수량 표시
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    # 그래프 스타일 조정 (사진 디자인 재현)
    fig.update_traces(
        texttemplate='%{text:,.0f}', 
        textposition='inside',
        insidetextanchor='middle',
        textfont=dict(size=11, color="white")
    )
    
    # 상단 총합 레이블 추가
    totals = chart_data.groupby('월_표시')['제품판매수량'].sum().reset_index()
    for _, row in totals.iterrows():
        fig.add_annotation(
            x=row['월_표시'], y=row['제품판매수량'],
            text=f"<b>{row['제품판매수량']:,.0f}</b>",
            showarrow=False, yshift=10, font=dict(size=12, color="#333333")
        )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title=None,
        yaxis_title="출고량 (EA)",
        height=500,
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 상세 데이터 확인용 테이블
    with st.expander("📝 2026년 1~3월 상세 출고 데이터 확인"):
        st.dataframe(f_raw[['월_표시', '채널명', '제품명', '제품판매수량', '매출취합용_공급가액(원화기준)']], use_container_width=True, hide_index=True)

# 💡 데이터가 안 나올 경우를 위한 진단 정보
if df_raw.empty:
    st.info("💡 Supabase '출고_RAW' 테이블이 비어있습니다.")
else:
    with st.sidebar:
        st.write("🔍 **Data Logic Check**")
        st.write(f"RAW 연도(S열) 종류: {df_raw['Y'].unique().tolist()}")
        st.write(f"RAW 월(T열) 종류: {df_raw['M'].unique().tolist()}")