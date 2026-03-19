import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (Rose-Beige 테마) ---
st.set_page_config(page_title="2026 hince Sales Dashboard", layout="wide")

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
        h2 { color: #A37F7D !important; font-size: 20px !important; border-left: 5px solid #A37F7D; padding-left: 10px; margin-top: 20px; margin-bottom: 20px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 15px !important; font-weight: 700 !important; margin-top: 5px !important; margin-bottom: 10px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
@st.cache_data(ttl=5) # 즉각적인 반영을 위해 캐시 시간 단축
def get_supabase_data(table_name):
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"{table_name} 데이터 로드 실패: {e}")
        return pd.DataFrame()

df_raw_all = get_supabase_data("출고_RAW")
df_master_all = get_supabase_data("SS_Master")

# --- 3. 데이터 전처리 (연도 컬럼 최우선 인식) ⭐ ---
def smart_preprocess(df, qty_col, rev_col):
    if df.empty: return df
    
    # 1) 연도(AJ열 등) 추출 로직 강화
    # '연도', 'Y' 컬럼이 있으면 최우선으로 정수화하여 사용
    found_year = False
    for col in ['연도', 'Y', 'year']:
        if col in df.columns:
            df['year_val'] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            found_year = True
            break
    
    # 만약 연도 컬럼이 없으면 날짜 컬럼에서 추출 (출고_RAW용)
    if not found_year and "매출인식_기준일(출고일)" in df.columns:
        df['year_val'] = df["매출인식_기준일(출고일)"].astype(str).str.extract(r'(20\d{2})').fillna(0).astype(int)
    elif not found_year:
        df['year_val'] = 0

    # 2) 숫자형 변환 (금액/수량 정제)
    for col in [qty_col, rev_col]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    
    # 3) 월 인덱스 추출
    if '월' in df.columns:
        df['month_idx'] = df['월'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    return df

df_raw_all = smart_preprocess(df_raw_all, "제품판매수량", "매출취합용_공급가액(원화기준)")
df_master_all = smart_preprocess(df_master_all, "출고_수량", "매출액")

# --- 4. 사이드바 필터 (2026 고정) ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 연도 리스트 생성 (2026 최우선)
    all_years = sorted(list(set(df_raw_all['year_val'].unique()) | set(df_master_all['year_val'].unique())), reverse=True)
    all_years = [y for y in all_years if y > 2000]
    if 2026 not in all_years: all_years.insert(0, 2026)
    
    selected_year = st.selectbox("📅 연도 선택", all_years, index=all_years.index(2026))
    
    # 통합 거래처 필터
    ch_list = set(df_raw_all[df_raw_all['year_val'] == selected_year]['채널명'].unique()) if '채널명' in df_raw_all.columns else set()
    cu_list = set(df_master_all[df_master_all['year_val'] == selected_year]['CUSTOMER'].unique()) if 'CUSTOMER' in df_master_all.columns else set()
    all_ents = sorted(list(ch_list | cu_list))
    selected_ents = st.multiselect("🤝 거래처/채널 선택", all_ents, default=all_ents)

# 데이터 필터링
f_raw = df_raw_all[(df_raw_all['year_val'] == selected_year) & (df_raw_all['채널명'].isin(selected_ents))]
f_master = df_master_all[(df_master_all['year_val'] == selected_year) & (df_master_all['CUSTOMER'].isin(selected_ents))]

# --- 5. 메인 대시보드 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 28px;">📊 {selected_year} hince Sales Analysis</h1>', unsafe_allow_html=True)

# 지표가 0일 때만 보여주는 진단 도구
if f_raw.empty and f_master.empty:
    with st.expander("🧐 데이터 진단: 2026 데이터가 보이지 않는 이유"):
        st.write("1. SS_Master에서 발견된 연도들:", sorted(df_master_all['year_val'].unique()))
        st.write("2. 출고_RAW에서 발견된 연도들:", sorted(df_raw_all['year_val'].unique()))
        st.info("💡 만약 위 목록에 2026이 없다면 Supabase의 해당 컬럼에 데이터가 아직 반영되지 않은 것입니다.")

# KPI 카드
k1, k2, k3, k4 = st.columns(4)
with k1:
    val = f_raw["매출취합용_공급가액(원화기준)"].sum() if not f_raw.empty else 0
    st.markdown(f'<div class="metric-card"><div class="metric-label">총 매출액</div><div class="metric-value">₩{val:,.0f}</div></div>', unsafe_allow_html=True)
with k2:
    val = f_raw["제품판매수량"].sum() if not f_raw.empty else 0
    st.markdown(f'<div class="metric-card"><div class="metric-label">총 출고량</div><div class="metric-value">{val:,.0f} EA</div></div>', unsafe_allow_html=True)
with k3:
    val = f_raw["채널명"].nunique() if not f_raw.empty else 0
    st.markdown(f'<div class="metric-card"><div class="metric-label">활성 채널</div><div class="metric-value">{val} 개</div></div>', unsafe_allow_html=True)
with k4:
    m_val = f_raw["월"].max() if not f_raw.empty else "-"
    st.markdown(f'<div class="metric-card"><div class="metric-label">집계 기준월</div><div class="metric-value">{m_val}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# 그래프 섹션 (3개 한 줄 배치)
c1, c2, c3 = st.columns(3)
hince_colors = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

with c1:
    st.markdown("### ■ 월별 Sell-In 현황")
    if not f_raw.empty:
        si_df = f_raw.groupby(['월', 'month_idx', '채널명'])['제품판매수량'].sum().reset_index().sort_values('month_idx')
        fig = px.bar(si_df, x='월', y='제품판매수량', color='채널명', text='제품판매수량', color_discrete_sequence=hince_colors)
        fig.update_traces(texttemplate='%{text:,.0f}', textposition='inside')
        totals = si_df.groupby('월')['제품판매수량'].sum().reset_index()
        for _, row in totals.iterrows():
            fig.add_annotation(x=row['월'], y=row['제품판매수량'], text=f"<b>{row['제품판매수량']:,.0f}</b>", showarrow=False, yshift=10)
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=350, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("2026 Sell-In 데이터 없음")

with c2:
    st.markdown("### ■ 카테고리 비중 (대)")
    if not f_raw.empty and '대' in f_raw.columns:
        fig_p = px.pie(f_raw, values='제품판매수량', names='대', hole=0.5, color_discrete_sequence=hince_colors)
        fig_p.update_layout(height=350, showlegend=True, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_p, use_container_width=True)
    else: st.info("카테고리 정보 없음")

with c3:
    st.markdown("### ■ 거래처별 Sell-Out 비중")
    if not f_master.empty:
        fig_so = px.pie(f_master, values='출고_수량', names='CUSTOMER', hole=0.5, color_discrete_sequence=hince_colors)
        fig_so.update_layout(height=350, showlegend=True, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_so, use_container_width=True)
    else: st.info("2026 Sell-Out 데이터 없음")

st.markdown("---")

# 상세 테이블 (정렬 에러 방지 포함)
st.markdown("### 📋 상세 데이터 내역")
if not f_raw.empty:
    v_cols = ['월', '채널명', '제품명', '제품판매수량', '매출취합용_공급가액(원화기준)']
    avail = [c for c in v_cols if c in f_raw.columns]
    st.dataframe(f_raw.sort_values('month_idx')[avail], use_container_width=True, hide_index=True)