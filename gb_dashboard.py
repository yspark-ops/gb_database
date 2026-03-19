import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (Rose-Beige) ---
st.set_page_config(page_title="hince 2026 Sell-In Dashboard", layout="wide")

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
        h3 { color: #A37F7D !important; font-size: 16px !important; font-weight: 700 !important; margin-top: 5px !important; margin-bottom: 15px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
@st.cache_data(ttl=10)
def get_raw_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        # 출고_RAW 시트 호출
        response = supabase.table("출고_RAW").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")
        return pd.DataFrame()

df_raw = get_raw_data()
# get_raw_data() 호출 직후에 추가
df_raw = get_raw_data()

# ⬇️ 이 블록 임시 추가
with st.expander("🔍 진단 데이터 (확인 후 삭제)"):
    st.write("**전체 컬럼 목록:**", df_raw.columns.tolist())
    st.write("**상위 5행:**")
    st.dataframe(df_raw.head(5))
    if 'Y' in df_raw.columns:
        st.write("**Y열 유니크 값:**", df_raw['Y'].unique().tolist())
        st.write("**Y열 타입:**", df_raw['Y'].dtype)
    else:
        st.error("Y 컬럼 없음!")

# --- 3. 사용자 요청 로직 전처리 (Y열 타격) ⭐ ---
def preprocess_raw_data(df):
    if df.empty: return df
    
    # 1) 열 이름에서 공백 제거
    df.columns = [str(c).strip() for c in df.columns]

    # 2) 'Y' 열을 연도 기준으로 사용
    if 'Y' in df.columns:
        df['year_numeric'] = pd.to_numeric(df['Y'], errors='coerce').fillna(0).astype(int)
    else:
        # 혹시 'Y' 컬럼명을 못 찾을 경우 데이터 진단을 위해 표시
        st.error("'Y'라는 열 이름을 찾을 수 없습니다. DB의 실제 컬럼명을 확인해 주세요.")
        st.write("감지된 컬럼 리스트:", df.columns.tolist())
        df['year_numeric'] = 0

    # 3) 매출취합용_공급가액(원화기준) (N열) 숫자화
    rev_col = '매출취합용_공급가액(원화기준)'
    if rev_col in df.columns:
        df['amount_num'] = pd.to_numeric(df[rev_col].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    else:
        df['amount_num'] = 0

    # 4) 대 (Q열: 카테고리) 정제
    cat_col = '대'
    df['category_display'] = df[cat_col].fillna('기타') if cat_col in df.columns else '미지정'

    # 5) 월(T열) 및 채널명
    df['month_display'] = df['월'].fillna('-') if '월' in df.columns else '-'
    df['month_idx'] = df['month_display'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    df['customer_display'] = df['채널명'].fillna('알수없음') if '채널명' in df.columns else '기타'

    return df

df_proc = preprocess_raw_data(df_raw)

# --- 4. 2026년 데이터 고정 필터링 ---
f_df = df_proc[df_proc['year_numeric'] == 2026].copy()

# --- 5. 사이드바 거래처 필터 ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    st.markdown("### 🔍 Filter")
    if not f_df.empty:
        all_customers = sorted(f_df['customer_display'].unique())
        selected_customers = st.multiselect("거래처 선택", all_customers, default=all_customers)
        f_df = f_df[f_df['customer_display'].isin(selected_customers)]
    else:
        selected_customers = []

# --- 6. 대시보드 화면 출력 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 26px;">📊 2026 hince Integrated Sell-In Performance</h1>', unsafe_allow_html=True)

if f_df.empty:
    st.warning("⚠️ 열 이름 'Y'에서 2026 데이터를 찾을 수 없습니다.")
    with st.expander("🛠️ 시스템 진단 데이터 (출고_RAW)"):
        st.write("1. 발견된 연도(Y열) 값들:", df_proc['year_numeric'].unique().tolist() if not df_proc.empty else "데이터 없음")
        st.write("2. '출고_RAW' 상위 3건 미리보기:", df_raw.head(3))
else:
    # --- KPI 영역 ---
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 누적 공급가액</div><div class="metric-value">₩{f_df["amount_num"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">분석 거래처 수</div><div class="metric-value">{f_df["customer_display"].nunique()} 개</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 총 출고 건수</div><div class="metric-value">{len(f_df):,.0f} 건</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # --- 첫 번째 그래프: 월별 거래처 매출 현황 ---
    st.markdown("### ■ 월별 거래처 출고 추이 (누적 금액)")
    monthly_data = f_df.groupby(['month_display', 'month_idx', 'customer_display'])['amount_num'].sum().reset_index().sort_values('month_idx')
    
    fig_monthly = px.bar(
        monthly_data, x='month_display', y='amount_num', color='customer_display',
        text_auto=',.0s', color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_monthly.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', height=400, xaxis_title=None, showlegend=True,
                             legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None))
    st.plotly_chart(fig_monthly, use_container_width=True)

    # --- 두 번째 그래프: [사용자 요청] 거래처별 품목 구매 상세 분석 ⭐ ---
    st.markdown("### ■ 거래처별 카테고리(대) 구매 분석")
    st.caption("Q열('대' 카테고리)과 N열('공급가액') 기준 집계")
    
    cat_agg = f_df.groupby(['customer_display', 'category_display'])['amount_num'].sum().reset_index()
    # 전체 매출 높은 거래처 순 정렬
    cust_rank = cat_agg.groupby('customer_display')['amount_num'].sum().sort_values(ascending=True).index.tolist()

    fig_cat = px.bar(
        cat_agg, y='customer_display', x='amount_num', color='category_display',
        orientation='h', text_auto=',.0s', 
        category_orders={'customer_display': cust_rank},
        color_discrete_sequence=px.colors.qualitative.Prism
    )
    fig_cat.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', height=550, yaxis_title=None, xaxis_title="구매액 합계",
        margin=dict(t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
    )
    st.plotly_chart(fig_cat, use_container_width=True)

    # --- 하단 상세 내역 ---
    with st.expander("📋 상세 출고 로우 데이터 확인"):
        view_cols = ['month_display', 'customer_display', 'category_display', '제품명', 'amount_num']
        st.dataframe(f_df[view_cols].sort_values(['month_idx', 'amount_num'], ascending=[True, False]), use_container_width=True, hide_index=True)

# 📥 다운로드
csv_data = f_df.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(label="📥 데이터 내보내기 (CSV)", data=csv_data, file_name=f'hince_sell_in_2026.csv')