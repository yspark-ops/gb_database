import streamlit as st
import pandas as pd
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

# --- 2. Supabase 데이터 로드 (캐시 TTL 300초 / 수동 새로고침 가능) ---
@st.cache_data(ttl=300)
def get_raw_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        response = supabase.table("출고_RAW").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")
        return pd.DataFrame()

# --- 3. 전처리 ---
def preprocess_raw_data(df):
    if df.empty:
        return df

    df.columns = [str(c).strip() for c in df.columns]

    # Y열: 연도
    if 'Y' in df.columns:
        df['year_numeric'] = pd.to_numeric(df['Y'], errors='coerce').fillna(0).astype(int)
    else:
        st.error("'Y' 컬럼을 찾을 수 없습니다. DB 컬럼명을 확인해주세요.")
        st.write("감지된 컬럼:", df.columns.tolist())
        df['year_numeric'] = 0

    # 매출취합용_공급가액(원화기준)
    rev_col = '매출취합용_공급가액(원화기준)'
    if rev_col in df.columns:
        df['amount_num'] = pd.to_numeric(
            df[rev_col].astype(str).str.replace(r'[^0-9.-]', '', regex=True),
            errors='coerce'
        ).fillna(0)
    else:
        df['amount_num'] = 0

    # 대 (카테고리)
    df['category_display'] = df['대'].fillna('기타') if '대' in df.columns else '미지정'

    # 월 / 채널명
    df['month_display'] = df['월'].fillna('-') if '월' in df.columns else '-'
    df['month_idx'] = df['month_display'].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    df['customer_display'] = df['채널명'].fillna('알수없음') if '채널명' in df.columns else '기타'

    return df

# --- 4. 사이드바 ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")

    # 🔄 수동 새로고침 버튼 (캐시 문제 완전 해결)
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("### 🔍 Filter")

# --- 5. 데이터 로드 및 필터링 ---
df_raw = get_raw_data()
df_proc = preprocess_raw_data(df_raw)
f_df = df_proc[df_proc['year_numeric'] == 2026].copy()

# 사이드바 거래처 필터
with st.sidebar:
    if not f_df.empty:
        all_customers = sorted(f_df['customer_display'].unique())
        selected_customers = st.multiselect("거래처 선택", all_customers, default=all_customers)
        f_df = f_df[f_df['customer_display'].isin(selected_customers)]
    else:
        selected_customers = []

# --- 6. 대시보드 출력 ---
st.markdown('<h1 style="color: #A37F7D; font-size: 26px;">📊 2026 hince Integrated Sell-In Performance</h1>', unsafe_allow_html=True)

if f_df.empty:
    st.warning("⚠️ 2026년 데이터가 없습니다. 사이드바에서 '🔄 데이터 새로고침' 버튼을 눌러주세요.")
    with st.expander("🛠️ 진단 정보"):
        st.write("감지된 연도값:", df_proc['year_numeric'].unique().tolist() if not df_proc.empty else "데이터 없음")
        st.dataframe(df_raw.head(3))
else:
    # KPI 카드
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 누적 공급가액</div><div class="metric-value">₩{f_df["amount_num"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">분석 거래처 수</div><div class="metric-value">{f_df["customer_display"].nunique()} 개</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">2026 총 출고 건수</div><div class="metric-value">{len(f_df):,.0f} 건</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # 그래프 1: 월별 거래처 출고 추이
    st.markdown("### ■ 월별 거래처 출고 추이 (누적 금액)")
    monthly_data = (
        f_df.groupby(['month_display', 'month_idx', 'customer_display'])['amount_num']
        .sum().reset_index().sort_values('month_idx')
    )
    ordered_months = monthly_data.drop_duplicates('month_idx').sort_values('month_idx')['month_display'].tolist()

    fig_monthly = px.bar(
        monthly_data, x='month_display', y='amount_num', color='customer_display',
        text_auto=',.0s',
        category_orders={"month_display": ordered_months},
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_monthly.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', barmode='stack', height=400,
        xaxis_title=None, showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, title=None)
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

    # 그래프 2: 거래처별 카테고리(대) 구매 분석
    st.markdown("### ■ 거래처별 카테고리(대) 구매 분석")

    cat_agg = f_df.groupby(['customer_display', 'category_display'])['amount_num'].sum().reset_index()
    cust_rank = cat_agg.groupby('customer_display')['amount_num'].sum().sort_values(ascending=True).index.tolist()

    fig_cat = px.bar(
        cat_agg, y='customer_display', x='amount_num', color='category_display',
        orientation='h', text_auto=',.0s',
        category_orders={'customer_display': cust_rank},
        color_discrete_sequence=px.colors.qualitative.Prism
    )
    fig_cat.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', height=550,
        yaxis_title=None, xaxis_title="구매액 합계",
        margin=dict(t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
    )
    st.plotly_chart(fig_cat, use_container_width=True)

    # 하단 상세 내역
    with st.expander("📋 상세 출고 로우 데이터 확인"):
        view_cols = ['month_display', 'customer_display', 'category_display', '제품명', 'amount_num']
        st.dataframe(
            f_df[view_cols].sort_values(['month_idx', 'amount_num'], ascending=[True, False]),
            use_container_width=True, hide_index=True
        )

# 📥 다운로드
csv_data = f_df.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(
    label="📥 데이터 내보내기 (CSV)",
    data=csv_data,
    file_name='hince_sell_in_2026.csv'
)