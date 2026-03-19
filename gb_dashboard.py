import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (Rose-Beige 테마) ---
st.set_page_config(page_title="hince 2026 Sales Dashboard", layout="wide")

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
            text-align: center;
            border: 1px solid #F0F0F0;
        }
        .metric-label { color: #6B7280; font-size: 13px; font-weight: 500; margin-bottom: 5px; }
        .metric-value { color: #A37F7D; font-size: 24px; font-weight: 700; }
        h2 { color: #A37F7D !important; font-size: 20px !important; border-left: 5px solid #A37F7D; padding-left: 10px; margin-top: 30px; margin-bottom: 20px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 16px !important; font-weight: 700 !important; margin-bottom: 15px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
@st.cache_data(ttl=5)
def get_raw_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        # 출고_RAW 시트(테이블) 데이터만 호출
        response = supabase.table("출고_RAW").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df_raw_src = get_raw_data()

# --- 3. 사용자 요청 데이터 정밀 전처리 ⭐ ---
def preprocess_for_charts(df):
    if df.empty: return df
    
    # 1) S열(헤더 'Y'): 숫자 연도 정밀 인식
    # 사용자님이 말씀하신 2025, 2026 숫자가 들어있는 S열 매핑
    if 'Y' in df.columns:
        df['year_int'] = pd.to_numeric(df['Y'], errors='coerce').fillna(0).astype(int)
    else:
        # 혹시 'Y'라는 이름이 없으면 19번째 열(S)을 가져옴
        df['year_int'] = pd.to_numeric(df.iloc[:, 18], errors='coerce').fillna(0).astype(int)
    
    # 2) Q열(헤더 '대'): 제품군 카테고리
    # Q열은 17번째 열
    df['category_main'] = df['대'] if '대' in df.columns else df.iloc[:, 16]
    df['category_main'] = df['category_main'].fillna('미분류')

    # 3) N열(헤더 '매출취합용_공급가액(원화기준)'): 공급가액
    # N열은 14번째 열
    revenue_col = '매출취합용_공급가액(원화기준)'
    if revenue_col in df.columns:
        df['revenue_clean'] = pd.to_numeric(df[revenue_col].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    else:
        df['revenue_clean'] = 0

    # 4) 월(M/T열) 인덱스 정렬용 (정렬 시 필요)
    if '월' in df.columns:
        df['month_idx'] = df['월'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)

    return df

df_proc = preprocess_for_charts(df_raw_src)

# --- 4. 사이드바 구성 및 연도 고정 (2026 ⭐) ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 연도 선택 리스트 (2026 기본값)
    y_list = sorted([y for y in df_proc['year_int'].unique() if y > 2000], reverse=True)
    if 2026 not in y_list: y_list.insert(0, 2026)
    
    selected_year = st.selectbox("📅 기준 연도", y_list, index=y_list.index(2026) if 2026 in y_list else 0)
    
    # 채널/거래처 선택
    ch_list = sorted(df_proc[df_proc['year_int'] == selected_year]['채널명'].unique())
    selected_ents = st.multiselect("🤝 거래처 선택", ch_list, default=ch_list)

# 2026년 데이터 필터링
f_raw = df_proc[(df_proc['year_int'] == selected_year) & (df_proc['채널명'].isin(selected_ents))]

# --- 5. 대시보드 화면 ---
st.markdown(f'<h1 style="color: #A37F7D;">📊 {selected_year} hince Sales Mastery (Sell-In)</h1>', unsafe_allow_html=True)

if f_raw.empty:
    st.warning(f"💡 현재 {selected_year}년 데이터가 감지되지 않습니다. (S열 확인 필요)")
    with st.expander("🧐 데이터 필터 진단"):
        st.write("S열(Y)에서 발견된 모든 연도:", sorted(df_proc['year_int'].unique().tolist()))
else:
    # --- 1행: KPI ---
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">2026 총 누계 공급가액</div><div class="metric-value">₩{f_raw["revenue_clean"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2: 
        # 수량이 없으면 건수라도 표시
        row_cnt = len(f_raw)
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 총 출고 건수</div><div class="metric-value">{row_cnt:,.0f} 건</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">현재 분석 중 거래처</div><div class="metric-value">{f_raw["채널명"].nunique()} 개</div></div>', unsafe_allow_html=True)
    with k4: 
        max_month = f_raw["월"].max() if "월" in f_raw.columns else "-"
        st.markdown(f'<div class="metric-card"><div class="metric-label">최종 집계월</div><div class="metric-value">{max_month}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 2행: 메인 Sell-In 현황 분석 그래프 ---
    col_left, col_right = st.columns([1.2, 0.8])
    
    with col_left:
        # [사용자 요청] 거래처별 제품군 구매 분석
        st.markdown("## ■ 거래처별 카테고리(대) 구매 상세 현황")
        st.caption(f"{selected_year}년 누계 | S열(연도), Q열(카테고리), N열(공급가액) 기준 분석")
        
        # 데이터 집계: 채널별 카테고리 금액
        cat_agg = f_raw.groupby(['채널명', 'category_main'])['revenue_clean'].sum().reset_index()
        # 가독성을 위해 전체 매출 높은 거래처 순서로 정렬
        sorted_cust = cat_agg.groupby('채널명')['revenue_clean'].sum().sort_values(ascending=True).index.tolist()

        fig_cat = px.bar(
            cat_agg, y='채널명', x='revenue_clean', color='category_main',
            orientation='h', text_auto=',.0s', # 가독성을 위한 요약 숫자
            category_orders={'채널명': sorted_cust},
            color_discrete_sequence=px.colors.qualitative.Pastel + px.colors.qualitative.Prism
        )
        
        fig_cat.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', height=550, margin=dict(t=0, l=10),
            xaxis_title="총 구매액 (KRW)", yaxis_title=None,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
        )
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_right:
        # 전체 카테고리 점유율 비중
        st.markdown("## ■ 카테고리 점유율")
        fig_pie = px.pie(f_raw, values='revenue_clean', names='category_main', hole=0.5,
                        color_discrete_sequence=px.colors.qualitative.Safe)
        fig_pie.update_layout(height=500, margin=dict(t=10, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # --- 3행: 월별 매출 트렌드 확인 ---
    st.markdown("## ■ 2026 월별 누적 공급가액 추이")
    if 'month_idx' in f_raw.columns:
        trend_df = f_raw.groupby(['월', 'month_idx'])[ 'revenue_clean'].sum().reset_index().sort_values('month_idx')
        fig_trend = px.bar(trend_df, x='월', y='revenue_clean', color_discrete_sequence=['#A37F7D'], text_auto=',.0f')
        fig_trend.update_layout(plot_bgcolor='rgba(0,0,0,0)', height=400, xaxis_title=None, yaxis_title="금액")
        st.plotly_chart(fig_trend, use_container_width=True)

    # 상세 내역
    with st.expander("📋 2026년 거래처별 품목 상세 데이터 리스트"):
        view_cols = ['월', '채널명', '대', '중', '제품명', 'revenue_clean']
        available = [c for c in view_cols if c in f_raw.columns or c in ['revenue_clean', 'category_main']]
        st.dataframe(f_raw[available].sort_values(['year_int'], ascending=False), use_container_width=True, hide_index=True)

# 📥 데이터 다운로드 (사이드바)
csv = f_raw.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button("📥 필터링된 데이터 (CSV)", data=csv, file_name=f"hince_2026_sellin.csv")