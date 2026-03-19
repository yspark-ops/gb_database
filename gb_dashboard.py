import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
st.set_page_config(page_title="hince Sales Performance Tracker", layout="wide")

def local_css():
    st.markdown("""
        <style>
        .main { background-color: #F8F9FA; }
        [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEEEEE; }
        .metric-card {
            background-color: #FFFFFF;
            padding: 15px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            border: 1px solid #F0F0F0;
            margin-bottom: 10px;
            text-align: center;
        }
        .metric-label { color: #6B7280; font-size: 13px; font-weight: 500; margin-bottom: 5px; }
        .metric-value { color: #A37F7D; font-size: 24px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 16px !important; font-weight: 700 !important; margin-top: 10px !important; margin-bottom: 15px !important; }
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
        # 전체 데이터 호출
        response = supabase.table("SS_Master").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df_raw = get_master_data()

# --- 3. 컬럼 매핑 및 정밀 전처리 ---
def robust_preprocess(df):
    if df.empty: return df
    # 공백 제거
    df.columns = [str(c).strip() for c in df.columns]
    
    # [AJ열: 연도] 찾기
    col_year = next((c for c in df.columns if '연도' in c or c == 'Y'), None)
    if col_year:
        df['year_val'] = pd.to_numeric(df[col_year], errors='coerce').fillna(0).astype(int)
    
    # [A열: 월(-)] 찾기 및 정렬용 숫자 인덱스 추출
    col_month = next((c for c in df.columns if c == '-' or '월' in c), None)
    if col_month:
        df['month_idx'] = df[col_month].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
        df['month_display'] = df[col_month]
    
    # [C열: CUSTOMER] 매핑
    col_customer = next((c for c in df.columns if 'CUSTOMER' in c or '거래처' in c), None)
    df['customer_display'] = df[col_customer] if col_customer else "기타"

    # [M열: 매출액] 매핑 및 숫자 정제
    col_revenue = next((c for c in df.columns if '매출액' in c), None)
    if col_revenue:
        df['revenue_clean'] = pd.to_numeric(df[col_revenue].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    
    return df

df_proc = robust_preprocess(df_raw)

# --- 4. 사이드바 필터 (전체 연도 선택 가능) ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 📅 연도 선택 (DB에 있는 모든 연도를 가져옴)
    if not df_proc.empty and 'year_val' in df_proc.columns:
        # 0이 아닌 연도만 추출 (정렬: 최신순)
        all_available_years = sorted([y for y in df_proc['year_val'].unique() if y > 0], reverse=True)
        
        # 2026년을 기본으로 시도하되, 없으면 가장 최신 연도 선택
        try:
            default_idx = all_available_years.index(2026)
        except ValueError:
            default_idx = 0
            
        selected_year = st.selectbox("📅 기준 연도 선택", all_available_years, index=default_idx)
    else:
        selected_year = 2026 # 데이터 없을 때 대비 기본값

    # 🤝 거래처 필터
    filtered_df_year = df_proc[df_proc['year_val'] == selected_year]
    customer_list = sorted(list(filtered_df_year['customer_display'].unique())) if not filtered_df_year.empty else []
    selected_customers = st.multiselect("🤝 거래처 선택", customer_list, default=customer_list)

# --- 5. 데이터 최종 필터링 및 정렬 ---
f_df = df_proc[
    (df_proc['year_val'] == selected_year) & 
    (df_proc['customer_display'].isin(selected_customers))
].copy()

# 시각화를 위한 1차 수치 정렬 (월 순서대로)
if not f_df.empty:
    f_df = f_df.sort_values('month_idx')

# --- 6. 메인 대시보드 출력 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 26px;">📊 {selected_year} hince Sales Analysis</h1>', unsafe_allow_html=True)

if f_df.empty:
    st.info(f"💡 {selected_year}년 데이터가 없습니다. 사이드바에서 다른 연도를 선택해보세요.")
else:
    # KPI 카드
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{selected_year} 누적 매출액</div><div class="metric-value">₩{f_df["revenue_clean"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2:
        # 선택된 연도의 3월 데이터 합산
        val_3m = f_df[f_df['month_idx'] == 3]['revenue_clean'].sum()
        st.markdown(f'<div class="metric-card"><div class="metric-label">{selected_year}년 3월 매출</div><div class="metric-value">₩{val_3m:,.0f}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">현재 분석 중</div><div class="metric-value">{f_df["month_display"].nunique()}개 월</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 그래프: 월별 거래처 매출 현황 (완벽한 순서 정렬 ⭐) ---
    st.markdown(f"### ■ {selected_year} 월별 거래처 매출 추이")
    
    # 차트용 데이터 집계 및 정렬 (월 인덱스 필수 포함)
    chart_df = f_df.groupby(['month_display', 'month_idx', 'customer_display'])['revenue_clean'].sum().reset_index()
    chart_df = chart_df.sort_values('month_idx') # 1월, 2월, 3월 순서
    
    # 카테고리 순서 명시적 지정 (1,2,3... 순)
    ordered_months = chart_df['month_display'].unique().tolist()
    hince_palette = px.colors.qualitative.Pastel + px.colors.qualitative.Safe

    fig = px.bar(
        chart_df, 
        x='month_display', 
        y='revenue_clean', 
        color='customer_display',
        text='revenue_clean',
        category_orders={"month_display": ordered_months}, # 이 라인이 순서 해결사입니다.
        color_discrete_sequence=hince_palette
    )
    
    fig.update_traces(
        texttemplate='%{text:,.0s}', # 내부 금액 표시 (가독성 위해 축소 포맷)
        textposition='inside',
        insidetextanchor='middle'
    )
    
    # 막대 맨 위 총합 합계 레이블 추가
    totals = chart_df.groupby('month_display')['revenue_clean'].sum().reindex(ordered_months).reset_index()
    for _, row in totals.iterrows():
        fig.add_annotation(
            x=row['month_display'], y=row['revenue_clean'],
            text=f"<b>₩{row['revenue_clean']:,.0f}</b>",
            showarrow=False, yshift=10, font=dict(size=12, color="#333333")
        )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title=None,
        height=550, margin=dict(t=50, b=100),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None)
    )
    fig.update_yaxes(showgrid=True, gridcolor='#EEEEEE')
    
    st.plotly_chart(fig, use_container_width=True)

    # --- 하단 상세 내역 테이블 ---
    st.markdown("### 📋 분석 데이터 리스트")
    view_df = f_df.sort_values(['month_idx', 'customer_display'])
    cols = ['month_display', 'customer_display', 'revenue_clean']
    if 'Type' in view_df.columns: cols.append('Type')
    st.dataframe(view_df[cols], use_container_width=True, hide_index=True)

# 엑셀 다운로드 (CSV)
csv_data = f_df.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(
    label="📥 필터링된 데이터 다운로드",
    data=csv_data,
    file_name=f'hince_report_{selected_year}.csv',
    mime='text/csv'
)