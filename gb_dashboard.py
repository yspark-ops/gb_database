import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
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
@st.cache_data(ttl=10) # 갱신을 위해 캐시 시간 단축
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

# --- 3. 데이터 전처리 (2026년 데이터 인식 강화) ⭐ ---
def force_preprocess(df, qty_col, rev_col, month_col):
    if df.empty: return df
    
    # 1) 연도 추출 로직 (매출인식_기준일(출고일) "2026. 3. 5" 대응)
    date_col = "매출인식_기준일(출고일)"
    if date_col in df.columns:
        # 정규표현식으로 20으로 시작하는 숫자 4자리(202X)를 강제로 추출
        df['year_val'] = df[date_col].astype(str).str.extract(r'(20\d{2})').fillna(0).astype(int)
    elif 'Y' in df.columns:
        df['year_val'] = pd.to_numeric(df['Y'], errors='coerce').fillna(0).astype(int)
    elif '연도' in df.columns:
        df['year_val'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    else:
        df['year_val'] = 0

    # 2) 숫자형 변환 (금액/수량 데이터 정제)
    for col in [qty_col, rev_col]:
        if col in df.columns:
            # 숫자가 아닌 문자(콤마, 공백 등)를 모두 제거
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    
    # 3) 월 인덱스 추출 (정렬용)
    if month_col in df.columns:
        df['month_idx'] = df[month_col].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    else:
        df['month_idx'] = 0
        
    return df

df_raw_all = force_preprocess(df_raw_all, "제품판매수량", "매출취합용_공급가액(원화기준)", "월")
df_master_all = force_preprocess(df_master_all, "출고_수량", "매출액", "월")

# --- 4. 사이드바 필터 ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 연도 리스트 생성 (2026 무조건 포함)
    all_years = sorted(list(set(df_raw_all['year_val'].unique()) | set(df_master_all['year_val'].unique())), reverse=True)
    all_years = [y for y in all_years if y > 2000]
    if 2026 not in all_years: all_years.insert(0, 2026)
    
    # 2026 자동 선택
    selected_year = st.selectbox("📅 연도 선택", all_years, index=all_years.index(2026))
    
    # 거래처 필터
    ch_list = set(df_raw_all[df_raw_all['year_val'] == selected_year]['채널명'].unique())
    cu_list = set(df_master_all[df_master_all['year_val'] == selected_year]['CUSTOMER'].unique())
    all_ents = sorted(list(ch_list | cu_list))
    selected_ents = st.multiselect("🤝 거래처/채널 선택", all_ents, default=all_ents)

# 데이터 필터링 (2026 기준)
f_raw = df_raw_all[(df_raw_all['year_val'] == selected_year) & (df_raw_all['채널명'].isin(selected_ents))]
f_master = df_master_all[(df_master_all['year_val'] == selected_year) & (df_master_all['CUSTOMER'].isin(selected_ents))]

# --- 5. 메인 대시보드 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 28px;">📊 {selected_year} hince Sales Analysis</h1>', unsafe_allow_html=True)

# 💡 데이터 유무 확인용 디버깅 창 (문제가 해결되면 삭제 가능)
if f_raw.empty and selected_year == 2026:
    with st.expander("🧐 데이터 진단: 2026 데이터가 왜 안 보일까요?"):
        st.write("DB에서 감지된 연도들:", sorted(df_raw_all['year_val'].unique()))
        if not df_raw_all.empty:
            st.write("데이터 샘플 (날짜 원본):", df_raw_all["매출인식_기준일(출고일)"].head(5).tolist())
        st.info("실제 데이터가 있는데도 안 나온다면 날짜 컬럼의 오타나 공백을 확인해야 합니다.")

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
    m_val = f_raw["월"].max() if not f_raw.empty else "없음"
    st.markdown(f'<div class="metric-card"><div class="metric-label">현재 기준월</div><div class="metric-value">{m_val}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# 그래프 섹션 (3개 한 줄 배치)
if not f_raw.empty:
    c1, c2, c3 = st.columns(3)
    hince_colors = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

    with c1:
        st.markdown(f"### ■ {selected_year} 월별 Sell-In")
        si_df = f_raw.groupby(['월', 'month_idx', '채널명'])['제품판매수량'].sum().reset_index().sort_values('month_idx')
        fig = px.bar(si_df, x='월', y='제품판매수량', color='채널명', text='제품판매수량', color_discrete_sequence=hince_colors)
        fig.update_traces(texttemplate='%{text:,.0f}', textposition='inside')
        
        # 총합 표시
        totals = si_df.groupby('월')['제품판매수량'].sum().reset_index()
        for _, row in totals.iterrows():
            fig.add_annotation(x=row['월'], y=row['제품판매수량'], text=f"<b>{row['제품판매수량']:,.0f}</b>", showarrow=False, yshift=10)
            
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=350, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown(f"### ■ 카테고리 비중(대)")
        if '대' in f_raw.columns:
            fig_p = px.pie(f_raw, values='제품판매수량', names='대', hole=0.5, color_discrete_sequence=hince_colors)
            fig_p.update_layout(height=350, showlegend=True, legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(fig_p, use_container_width=True)

    with c3:
        st.markdown(f"### ■ {selected_year} Sell-Out 현황")
        if not f_master.empty:
            fig_so = px.bar(f_master, x='월', y='출고_수량', color='CUSTOMER', text_auto=',.0f', color_discrete_sequence=hince_colors)
            fig_so.update_layout(plot_bgcolor='rgba(0,0,0,0)', height=350, showlegend=False, xaxis_title=None)
            st.plotly_chart(fig_so, use_container_width=True)

    # 상세 내역 테이블
    st.markdown("### 📋 상세 데이터 내역")
    v_cols = ['월', '채널명', '제품명', '제품판매수량', '매출취합용_공급가액(원화기준)', '매출인식_기준일(출고일)']
    avail = [c for c in v_cols if c in f_raw.columns]
    # 정렬 먼저 하고 컬럼 선택
    st.dataframe(f_raw.sort_values('month_idx')[avail], use_container_width=True, hide_index=True)
else:
    st.info(f"{selected_year}년 데이터가 존재하지 않습니다. 사이드바에서 거래처 선택을 확인해주세요.")