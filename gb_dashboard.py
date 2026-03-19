import os
import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# ─────────────────────────────────────────
# 0. 설정
# ─────────────────────────────────────────
DEBUG_MODE = os.getenv("STREAMLIT_DEBUG", "false").lower() == "true"

st.set_page_config(page_title="2026 hince Sales Dashboard", layout="wide")

# ─────────────────────────────────────────
# 1. 스타일
# ─────────────────────────────────────────
def apply_styles() -> None:
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
        h2 { color: #A37F7D !important; font-size: 20px !important; border-left: 5px solid #A37F7D;
             padding-left: 10px; margin-top: 20px; margin-bottom: 20px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 15px !important; font-weight: 700 !important;
             margin-top: 5px !important; margin-bottom: 10px !important; }
        </style>
    """, unsafe_allow_html=True)

apply_styles()

# ─────────────────────────────────────────
# 2. 헬퍼: KPI 카드
# ─────────────────────────────────────────
def metric_card(label: str, value: str) -> None:
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────
# 3. 데이터 로드 (캐시 300초 + 수동 새로고침)
# ─────────────────────────────────────────
# 필요한 컬럼만 명시해 네트워크/메모리 절감
RAW_COLS = (
    "매출인식_기준일(출고일),채널명,제품명,제품판매수량,"
    "매출취합용_공급가액(원화기준),월,대"
)
MASTER_COLS = "Y,연도,CUSTOMER,출고_수량,매출액,월"

@st.cache_data(ttl=300)
def load_table(table_name: str, columns: str) -> pd.DataFrame:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        response = supabase.table(table_name).select(columns).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"{table_name} 데이터 로드 실패: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────
# 4. 전처리
# ─────────────────────────────────────────
def preprocess(df: pd.DataFrame, qty_col: str, rev_col: str, month_col: str) -> pd.DataFrame:
    if df.empty:
        return df

    # 연도 추출 ("2026. 3. 5" 형태 대응)
    date_col = "매출인식_기준일(출고일)"
    if date_col in df.columns:
        df["year_val"] = (
            df[date_col].astype(str)
            .str.extract(r"(20\d{2})", expand=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
            .astype(int)
        )
    elif "Y" in df.columns:
        df["year_val"] = pd.to_numeric(df["Y"], errors="coerce").fillna(0).astype(int)
    elif "연도" in df.columns:
        df["year_val"] = pd.to_numeric(df["연도"], errors="coerce").fillna(0).astype(int)
    else:
        df["year_val"] = 0

    # 숫자형 변환 (콤마·공백 등 제거)
    for col in [qty_col, rev_col]:
        if col in df.columns:
            df[col] = (
                pd.to_numeric(
                    df[col].astype(str).str.replace(r"[^0-9.-]", "", regex=True),
                    errors="coerce",
                ).fillna(0)
            )

    # 월 인덱스 (정렬용) — 문자열 "1월"·"10월"의 사전순 오정렬 방지
    if month_col in df.columns:
        df["month_idx"] = (
            df[month_col].astype(str)
            .str.extract(r"(\d+)", expand=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
            .astype(int)
        )
    else:
        df["month_idx"] = 0

    return df

# ─────────────────────────────────────────
# 5. 차트 렌더링 함수
# ─────────────────────────────────────────
HINCE_COLORS = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

def render_sellin_chart(df: pd.DataFrame, year: int) -> None:
    st.markdown(f"### ■ {year} 월별 Sell-In")
    si_df = (
        df.groupby(["월", "month_idx", "채널명"])["제품판매수량"]
        .sum()
        .reset_index()
        .sort_values("month_idx")
    )
    fig = px.bar(
        si_df, x="월", y="제품판매수량", color="채널명",
        text="제품판매수량", color_discrete_sequence=HINCE_COLORS,
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="inside")

    totals = si_df.groupby("월")["제품판매수량"].sum().reset_index()
    for _, row in totals.iterrows():
        fig.add_annotation(
            x=row["월"], y=row["제품판매수량"],
            text=f"<b>{row['제품판매수량']:,.0f}</b>",
            showarrow=False, yshift=10,
        )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", barmode="stack",
        xaxis_title=None, height=350, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_category_chart(df: pd.DataFrame) -> None:
    st.markdown("### ■ 카테고리 비중(대)")
    if "대" not in df.columns:
        st.info("'대' 컬럼이 없습니다.")
        return
    fig = px.pie(
        df, values="제품판매수량", names="대",
        hole=0.5, color_discrete_sequence=HINCE_COLORS,
    )
    fig.update_layout(height=350, showlegend=True, legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(fig, use_container_width=True)


def render_sellout_chart(df: pd.DataFrame, year: int) -> None:
    st.markdown(f"### ■ {year} Sell-Out 현황")
    if df.empty:
        st.info("Sell-Out 데이터가 없습니다.")
        return
    fig = px.bar(
        df, x="월", y="출고_수량", color="CUSTOMER",
        text_auto=",.0f", color_discrete_sequence=HINCE_COLORS,
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", height=350,
        showlegend=False, xaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────
# 6. 데이터 로드 & 전처리
# ─────────────────────────────────────────
df_raw_all    = preprocess(load_table("출고_RAW",  RAW_COLS),    "제품판매수량", "매출취합용_공급가액(원화기준)", "월")
df_master_all = preprocess(load_table("SS_Master", MASTER_COLS), "출고_수량",    "매출액",                       "월")

# ─────────────────────────────────────────
# 7. 사이드바
# ─────────────────────────────────────────
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")

    # 수동 새로고침 버튼
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

    # 연도 선택 (2026 항상 포함)
    all_years = sorted(
        set(df_raw_all["year_val"].unique()) | set(df_master_all["year_val"].unique()),
        reverse=True,
    )
    all_years = [y for y in all_years if y > 2000]
    if 2026 not in all_years:
        all_years.insert(0, 2026)

    selected_year = st.selectbox("📅 연도 선택", all_years, index=all_years.index(2026))

    # 거래처/채널 필터
    ch_list  = set(df_raw_all   [df_raw_all   ["year_val"] == selected_year]["채널명"].dropna().unique())
    cu_list  = set(df_master_all[df_master_all["year_val"] == selected_year]["CUSTOMER"].dropna().unique())
    all_ents = sorted(ch_list | cu_list)

    selected_ents = st.multiselect("🤝 거래처/채널 선택", all_ents, default=all_ents)

# 빈 선택 방어
if not selected_ents:
    st.warning("거래처/채널을 하나 이상 선택해주세요.")
    st.stop()

# ─────────────────────────────────────────
# 8. 필터링
# ─────────────────────────────────────────
f_raw    = df_raw_all   [(df_raw_all   ["year_val"] == selected_year) & (df_raw_all   ["채널명"].isin(selected_ents))]
f_master = df_master_all[(df_master_all["year_val"] == selected_year) & (df_master_all["CUSTOMER"].isin(selected_ents))]

# ─────────────────────────────────────────
# 9. 메인 대시보드
# ─────────────────────────────────────────
st.markdown(
    f'<h1 style="color:#A37F7D;font-size:28px;">📊 {selected_year} hince Sales Analysis</h1>',
    unsafe_allow_html=True,
)

# 디버그 패널 (환경변수 STREAMLIT_DEBUG=true 일 때만 표시)
if DEBUG_MODE and f_raw.empty and selected_year == 2026:
    with st.expander("🧐 데이터 진단: 2026 데이터가 왜 안 보일까요?"):
        st.write("DB에서 감지된 연도들:", sorted(df_raw_all["year_val"].unique()))
        if not df_raw_all.empty:
            st.write("데이터 샘플 (날짜 원본):", df_raw_all["매출인식_기준일(출고일)"].head(5).tolist())
        st.info("실제 데이터가 있는데도 안 나온다면 날짜 컬럼의 오타나 공백을 확인하세요.")

# KPI 카드
k1, k2, k3, k4 = st.columns(4)
with k1:
    val = f_raw["매출취합용_공급가액(원화기준)"].sum() if not f_raw.empty else 0
    metric_card("총 매출액", f"₩{val:,.0f}")
with k2:
    val = f_raw["제품판매수량"].sum() if not f_raw.empty else 0
    metric_card("총 출고량", f"{val:,.0f} EA")
with k3:
    val = f_raw["채널명"].nunique() if not f_raw.empty else 0
    metric_card("활성 채널", f"{val} 개")
with k4:
    # month_idx 기준으로 최대월 텍스트 추출 (사전순 오정렬 방지)
    if not f_raw.empty:
        max_idx = f_raw["month_idx"].max()
        m_val = f_raw.loc[f_raw["month_idx"] == max_idx, "월"].iloc[0]
    else:
        m_val = "없음"
    metric_card("현재 기준월", str(m_val))

st.markdown("---")

# 차트
if not f_raw.empty:
    c1, c2, c3 = st.columns(3)
    with c1:
        render_sellin_chart(f_raw, selected_year)
    with c2:
        render_category_chart(f_raw)
    with c3:
        render_sellout_chart(f_master, selected_year)

    # 상세 내역 테이블
    st.markdown("### 📋 상세 데이터 내역")
    v_cols = ["월", "채널명", "제품명", "제품판매수량", "매출취합용_공급가액(원화기준)", "매출인식_기준일(출고일)"]
    avail  = [c for c in v_cols if c in f_raw.columns]
    st.dataframe(f_raw.sort_values("month_idx")[avail], use_container_width=True, hide_index=True)
else:
    st.info(f"{selected_year}년 데이터가 존재하지 않습니다. 사이드바에서 거래처 선택을 확인해주세요.")