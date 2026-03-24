import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# ─────────────────────────────────────────
# 1. 페이지 설정 & 스타일
# ─────────────────────────────────────────
st.set_page_config(page_title="2026 hince Sales Dashboard", layout="wide")

st.markdown("""
<style>
.main { background-color: #F8F9FA; }
h1 { color: #A37F7D !important; }
h3 { color: #A37F7D !important; font-size: 15px !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# 2. Supabase 데이터 로드
# ─────────────────────────────────────────
@st.cache_data(ttl=60)
def load_raw_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)

        all_rows = []
        chunk = 1000
        offset = 0

        while True:
            response = supabase.table("출고_RAW").select(
                "Y, M, 채널명, 제품판매수량"
            ).range(offset, offset + chunk - 1).execute()

            if not response.data:
                break

            all_rows.extend(response.data)

            if len(response.data) < chunk:
                break  # 마지막 페이지

            offset += chunk

        return pd.DataFrame(all_rows)

    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df_raw = load_raw_data()

# ─────────────────────────────────────────
# 3. 전처리
# ─────────────────────────────────────────
def preprocess(df):
    if df.empty:
        return df

    df["Y"] = pd.to_numeric(df["Y"], errors="coerce")
    df["M"] = pd.to_numeric(df["M"], errors="coerce")
    df["제품판매수량"] = pd.to_numeric(df["제품판매수량"], errors="coerce").fillna(0)

    # 2025년 4월 ~ 2026년 3월 필터
    mask = (
        ((df["Y"] == 2025) & (df["M"] >= 4)) |
        ((df["Y"] == 2026) & (df["M"] <= 3))
    )
    df = df[mask].copy()

    # 월 레이블: "25.04", "25.05" ... "26.03"
    df["월_label"] = df["Y"].astype(str).str[-2:] + "." + df["M"].astype(int).astype(str).str.zfill(2)

    # 정렬키: 연도*100 + 월
    df["sort_key"] = df["Y"] * 100 + df["M"]

    return df

df = preprocess(df_raw)

# ─────────────────────────────────────────
# 4. 대시보드 헤더
# ─────────────────────────────────────────
st.markdown('<h1 style="font-size:24px;">📦 hince Sell-in Dashboard</h1>', unsafe_allow_html=True)
st.markdown("---")

# ─────────────────────────────────────────
# 5. 그래프 영역 (3열 레이아웃 준비)
# ─────────────────────────────────────────
col1, col2, col3 = st.columns(3)

# ── 그래프 1: 월별 거래처별 출고량 ──────────
with col1:
    st.markdown("### 📊 월별 Sell-in 출고량 (거래처별)")

    if df.empty:
        st.info("데이터 없음")
    else:
        # 월 × 거래처별 수량 합산
        chart_df = (
            df.groupby(["sort_key", "월_label", "채널명"])["제품판매수량"]
            .sum()
            .reset_index()
            .sort_values("sort_key")
        )

        # x축 순서 고정 리스트
        month_order = (
            chart_df[["sort_key", "월_label"]]
            .drop_duplicates()
            .sort_values("sort_key")["월_label"]
            .tolist()
        )

        # 월별 총합 (상단 레이블용)
        totals = (
            chart_df.groupby("월_label")["제품판매수량"]
            .sum()
            .reindex(month_order)
            .reset_index()
        )

        fig = px.bar(
            chart_df,
            x="월_label",
            y="제품판매수량",
            color="채널명",
            color_discrete_sequence=px.colors.qualitative.Pastel
                                   + px.colors.qualitative.Set3,
            category_orders={"월_label": month_order},  # ✅ 순서 고정
        )

        fig.update_traces(textposition="none")

        # 막대 상단 총합 레이블
        for _, row in totals.iterrows():
            fig.add_annotation(
                x=row["월_label"],
                y=row["제품판매수량"],
                text=f"<b>{int(row['제품판매수량']):,}</b>",
                showarrow=False,
                yshift=10,
                font=dict(size=11, color="#333333"),
            )

        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                type="category",       # ✅ 숫자가 아닌 카테고리로 강제 지정
                categoryorder="array",
                categoryarray=month_order,
            ),
            xaxis_title=None,
            yaxis_title="출고 수량",
            height=420,
            margin=dict(t=40, b=10),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.25,
                xanchor="center",
                x=0.5,
                title=None,
                font=dict(size=10),
            ),
            bargap=0.2,
        )

        st.plotly_chart(fig, use_container_width=True)

# ── 그래프 2, 3: 추후 추가 ──────────────────
with col2:
    st.markdown("### ⬜ 그래프 2")
    st.info("추후 추가 예정")

with col3:
    st.markdown("### ⬜ 그래프 3")
    st.info("추후 추가 예정")