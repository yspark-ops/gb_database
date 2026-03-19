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
        response = supabase.table("SS_Master").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"SS_Master 로드 실패: {e}")
        return pd.DataFrame()

df_raw_master = get_master_data()

# --- 3. 컬럼 매핑 및 전처리 (월 인덱스 강화) ---
def robust_preprocess(df):
    if df.empty: return df
    df.columns = [str(c).strip() for c in df.columns]
    
    # AJ열 (연도) 자동 매핑
    col_year = next((c for c in df.columns if '연도' in c or c == 'Y' or c == '연도'), None)
    if col_year:
        df['year_val'] = pd.to_numeric(df[col_year], errors='coerce').fillna(0).astype(int)
    
    # A열 (월: '-') 자동 매핑 및 숫자 인덱스 추출 (01월, 3월 등 대응)
    col_month = next((c for c in df.columns if c == '-' or '월' in c), None)
    if col_month:
        # 월에서 숫자만 뽑아냄 (1월 -> 1, 02월 -> 2)
        df['month_idx'] = df[col_month].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
        df['month_display'] = df[col_month]
    
    # C열 (CUSTOMER) 매핑
    col_customer = next((c for c in df.columns if 'CUSTOMER' in c or '거래처' in c), None)
    df['customer_display'] = df[col_customer] if col_customer else "기타 거래처"

    # M열 (매출액) 매핑 및 정제
    col_revenue = next((c for c in df.columns if '매출액' in c), None)
    if col_revenue:
        df['revenue_clean'] = pd.to_numeric(df[col_revenue].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    
    return df

df_proc = robust_preprocess(df_raw_master)

# --- 4. 사이드바 구성 ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 연도 필터 (2026 기본값)
    if 'year_val' in df_proc.columns:
        all_years = sorted([y for y in list(df_proc['year_val'].unique()) if y > 2000], reverse=True)
        if 2026 not in all_years: all_years.insert(0, 2026)
        selected_year = st.selectbox("📅 기준 연도 선택", all_years, index=all_years.index(2026) if 2026 in all_years else 0)
    else:
        selected_year = 2026

    # 거래처 필터
    filtered_df_year = df_proc[df_proc['year_val'] == selected_year]
    all_customers = sorted(list(filtered_df_year['customer_display'].unique())) if not filtered_df_year.empty else []
    selected_customers = st.multiselect("🤝 거래처 선택", all_customers, default=all_customers)

# --- 5. 최종 데이터 필터링 ---
f_df = df_proc[
    (df_proc['year_val'] == selected_year) & 
    (df_proc['customer_display'].isin(selected_customers))
].copy()

# 데이터가 있으면 month_idx 기준으로 전체 정렬 ⭐
if not f_df.empty:
    f_df = f_df.sort_values('month_idx')

# --- 6. 메인 화면 출력 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 26px;">📊 {selected_year} hince Sales Analysis</h1>', unsafe_allow_html=True)

if f_df.empty:
    st.info(f"💡 {selected_year}년 선택된 조건에 맞는 데이터가 없습니다.")
else:
    # KPI 카드
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{selected_year} 총 매출액</div><div class="metric-value">₩{f_df["revenue_clean"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2:
        mar_rev = f_df[f_df['month_idx'] == 3]['revenue_clean'].sum()
        st.markdown(f'<div class="metric-card"><div class="metric-label">3월 확정 매출액</div><div class="metric-value">₩{mar_rev:,.0f}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">데이터 기준</div><div class="metric-value">{f_df["month_display"].unique().shape[0]}개 월</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 메인 그래프: 월별 거래처 매출 추이 (정렬 문제 해결 ⭐) ---
    st.markdown("### ■ 월별 거래처 매출 추이")
    
    # 차트용 데이터 집계 및 정렬
    chart_data = f_df.groupby(['month_display', 'month_idx', 'customer_display'])['revenue_clean'].sum().reset_index()
    chart_data = chart_data.sort_values('month_idx') # 수치로 다시 한 번 정렬
    
    # ⭐ Plotly에게 정렬된 '월' 순서를 강제로 지정
    month_order = chart_data['month_display'].unique().tolist()
    
    hince_palette = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

    fig = px.bar(
        chart_data, 
        x='month_display', 
        y='revenue_clean', 
        color='customer_display',
        text='revenue_clean',
        category_orders={"month_display": month_order}, # 여기서 순서 고정!
        color_discrete_sequence=hince_palette
    )
    
    fig.update_traces(
        texttemplate='%{text:,.0s}', # 천단위 요약 표시 (가독성 위해)
        textposition='inside',
        insidetextanchor='middle',
        marker_line_width=0
    )
    
    # 막대 상단 총합 레이블
    totals = chart_data.groupby('month_display')['revenue_clean'].sum().reindex(month_order).reset_index()
    for _, row in totals.iterrows():
        fig.add_annotation(
            x=row['month_display'], y=row['revenue_clean'],
            text=f"<b>₩{row['revenue_clean']:,.0f}</b>",
            showarrow=False, yshift=10, font=dict(size=11, color="#333333")
        )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title=None,
        height=550, margin=dict(t=50, b=80),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None)
    )
    fig.update_yaxes(showgrid=True, gridcolor='#EEEEEE')
    
    st.plotly_chart(fig, use_container_width=True)

    # --- 상세 내역 ---
    st.markdown("### 📋 2026 상세 매출 내역 (정렬순)")
    # 테이블용 정렬 (month_idx 우선)
    table_df = f_df.sort_values(['month_idx', 'customer_display'])
    view_cols = ['month_display', 'customer_display', 'revenue_clean']
    if 'Type' in table_df.columns: view_cols.append('Type')
    
    st.dataframe(table_df[view_cols], use_container_width=True, hide_index=True)

# 다운로드
csv = f_df.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(label="📥 데이터 다운로드 (CSV)", data=csv, file_name=f'hince_sales_{selected_year}.csv', mime='text/csv')