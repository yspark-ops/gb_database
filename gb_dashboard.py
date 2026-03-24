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
# 2. Supabase 데이터 로드 (페이지네이션)
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
                'Y, M, 채널명, 제품판매수량, "매출취합용_공급가액(원화기준)", 중, 제품명'
            ).range(offset, offset + chunk - 1).execute()

            if not response.data:
                break

            all_rows.extend(response.data)

            if len(response.data) < chunk:
                break

            offset += chunk

        return pd.DataFrame(all_rows)

    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df_raw = load_raw_data()

# ─────────────────────────────────────────
# 3. 전처리
# ─────────────────────────────────────────
def get_quarter(m):
    if m <= 3:   return "1Q"
    elif m <= 6: return "2Q"
    elif m <= 9: return "3Q"
    else:        return "4Q"

def preprocess(df):
    if df.empty:
        return df

    df["Y"] = pd.to_numeric(df["Y"], errors="coerce")
    df["M"] = pd.to_numeric(df["M"], errors="coerce")

    # 제품판매수량 정제
    df["제품판매수량"] = (
        df["제품판매수량"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    # 매출액 정제: "₩2,692,800" → 2692800
    df["매출액_num"] = (
        df["매출취합용_공급가액(원화기준)"]
        .astype(str)
        .str.replace("₩", "", regex=False)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    # 2025년 4월 ~ 2026년 3월 필터
    mask = (
        ((df["Y"] == 2025) & (df["M"] >= 4)) |
        ((df["Y"] == 2026) & (df["M"] <= 3))
    )
    df = df[mask].copy()

    # 월 레이블: "25.04" ~ "26.03"
    df["월_label"] = (
        df["Y"].astype(int).astype(str).str[-2:] + "." +
        df["M"].astype(int).astype(str).str.zfill(2)
    )

    # 월 정렬키
    df["sort_key"] = df["Y"] * 100 + df["M"]

    # 분기 레이블: "25_2Q", "25_3Q", "25_4Q", "26_1Q"
    quarter_num = {"1Q": 1, "2Q": 2, "3Q": 3, "4Q": 4}
    df["분기_label"] = (
        df["Y"].astype(int).astype(str).str[-2:] + "_" +
        df["M"].astype(int).apply(get_quarter)
    )
    df["분기_sort"] = (
        df["Y"] * 10 +
        df["M"].astype(int).apply(get_quarter).map(quarter_num)
    )

    return df

df = preprocess(df_raw)

# ─────────────────────────────────────────
# 4. 대시보드 헤더
# ─────────────────────────────────────────
st.markdown('<h1 style="font-size:24px;">📦 hince Sell-in Dashboard</h1>', unsafe_allow_html=True)
st.markdown("---")

# ─────────────────────────────────────────
# 5. 그래프 영역 (3열 레이아웃)
# ─────────────────────────────────────────
col1, col2, col3 = st.columns(3)

# ── 그래프 1: 월별 거래처별 출고량 ──────────
with col1:
    st.markdown("### 📊 월별 Sell-in 출고량 (거래처별)")

    if df.empty:
        st.info("데이터 없음")
    else:
        chart_df = (
            df.groupby(["sort_key", "월_label", "채널명"])["제품판매수량"]
            .sum()
            .reset_index()
            .sort_values("sort_key")
        )

        month_order = (
            chart_df[["sort_key", "월_label"]]
            .drop_duplicates()
            .sort_values("sort_key")["월_label"]
            .tolist()
        )

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
            category_orders={"월_label": month_order},
        )

        fig.update_traces(textposition="none")

        for _, row in totals.iterrows():
            fig.add_annotation(
                x=row["월_label"],
                y=row["제품판매수량"],
                text=f"<b>{int(row['제품판매수량']):,}</b>",
                showarrow=False,
                yshift=8,
                font=dict(size=10, color="#555555"),
                bgcolor="rgba(255,255,255,0.0)",
                borderpad=1,
            )

        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                type="category",
                categoryorder="array",
                categoryarray=month_order,
                tickfont=dict(size=11),
                range=[-0.5, len(month_order) - 0.5],
            ),
            yaxis=dict(
                title=None,
                tickformat=",",
                range=[0, totals["제품판매수량"].max() * 1.15],
            ),
            xaxis_title=None,
            height=420,
            margin=dict(t=50, b=10, l=10, r=10),
            bargap=0.3,
            bargroupgap=0.0,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.25,
                xanchor="center",
                x=0.5,
                title=None,
                font=dict(size=10),
            ),
        )

        st.plotly_chart(fig, use_container_width=True)

# ── 그래프 2: 월별 매출액 ──────────────────
with col2:
    st.markdown("### 💰 월별 Sell-in 매출액 (원화 기준)")

    if df.empty:
        st.info("데이터 없음")
    else:
        rev_df = (
            df.groupby(["sort_key", "월_label"])["매출액_num"]
            .sum()
            .reset_index()
            .sort_values("sort_key")
        )

        month_order2 = rev_df["월_label"].tolist()

        fig2 = px.bar(
            rev_df,
            x="월_label",
            y="매출액_num",
            color_discrete_sequence=["#C4A09E"],
            category_orders={"월_label": month_order2},
        )

        fig2.update_traces(textposition="none")

        for _, row in rev_df.iterrows():
            fig2.add_annotation(
                x=row["월_label"],
                y=row["매출액_num"],
                text=f"<b>{int(row['매출액_num'] / 1_000_000):.0f}M</b>",
                showarrow=False,
                yshift=8,
                font=dict(size=10, color="#555555"),
                bgcolor="rgba(255,255,255,0.0)",
                borderpad=1,
            )

        fig2.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                type="category",
                categoryorder="array",
                categoryarray=month_order2,
                tickfont=dict(size=11),
                range=[-0.5, len(month_order2) - 0.5],
            ),
            yaxis=dict(
                title=None,
                tickformat=",.0f",
                range=[0, rev_df["매출액_num"].max() * 1.15],
            ),
            xaxis_title=None,
            height=420,
            margin=dict(t=50, b=10, l=10, r=10),
            bargap=0.3,
            showlegend=False,
        )

        st.plotly_chart(fig2, use_container_width=True)

# ── 그래프 3: 카테고리별 분기 출고량 Top5 선 차트 ──
with col3:
    st.markdown("### 📈 카테고리별 분기 출고량 Top 5")

    if df.empty:
        st.info("데이터 없음")
    else:
        if "중" not in df.columns:
            st.info("'중' 컬럼 없음")
        else:
            top5 = (
                df[df["중"].notna() & (df["중"] != "-")]
                .groupby("중")["제품판매수량"]
                .sum()
                .nlargest(5)
                .index.tolist()
            )

            line_df = (
                df[df["중"].isin(top5)]
                .groupby(["분기_sort", "분기_label", "중"])["제품판매수량"]
                .sum()
                .reset_index()
                .sort_values("분기_sort")
            )

            q_order = (
                line_df[["분기_sort", "분기_label"]]
                .drop_duplicates()
                .sort_values("분기_sort")["분기_label"]
                .tolist()
            )

            fig3 = px.line(
                line_df,
                x="분기_label",
                y="제품판매수량",
                color="중",
                markers=True,
                color_discrete_sequence=px.colors.qualitative.Pastel,
                category_orders={"분기_label": q_order},
            )

            fig3.update_traces(
                line=dict(width=2.5),
                marker=dict(size=8),
            )

            for _, row in line_df.iterrows():
                fig3.add_annotation(
                    x=row["분기_label"],
                    y=row["제품판매수량"],
                    text=f"{int(row['제품판매수량']):,}",
                    showarrow=False,
                    yshift=12,
                    font=dict(size=9, color="#555555"),
                )

            fig3.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(
                    type="category",
                    categoryorder="array",
                    categoryarray=q_order,
                    tickfont=dict(size=11),
                ),
                yaxis=dict(
                    title=None,
                    tickformat=",",
                    range=[0, line_df["제품판매수량"].max() * 1.2],
                ),
                xaxis_title=None,
                height=420,
                margin=dict(t=50, b=10, l=10, r=10),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.25,
                    xanchor="center",
                    x=0.5,
                    title=None,
                    font=dict(size=10),
                ),
            )

            st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────────────────────
# 6. Top Selling SKU 테이블 (최근 3개월)
# ─────────────────────────────────────────
st.markdown("---")
st.markdown("### 🏆 Top Selling SKU — 최근 3개월 (2026.01 ~ 2026.03)")

if df.empty:
    st.info("데이터 없음")
else:
    sku_df = df[
        (df["Y"] == 2026) & (df["M"] <= 3)
    ].copy()

    if sku_df.empty:
        st.info("최근 3개월 데이터 없음")
    else:
        sku_table = (
            sku_df.groupby("제품명")
            .agg(
                총_출고수량=("제품판매수량", "sum"),
                총_매출액=("매출액_num", "sum"),
            )
            .reset_index()
            .sort_values("총_출고수량", ascending=False)
            .head(20)
            .reset_index(drop=True)
        )

        # 순위 컬럼 추가
        sku_table.insert(0, "순위", range(1, len(sku_table) + 1))

        # 포맷 적용
        sku_display = sku_table.copy()
        sku_display["총_출고수량"] = sku_display["총_출고수량"].apply(lambda x: f"{int(x):,}")
        sku_display["총_매출액"] = sku_display["총_매출액"].apply(lambda x: f"₩{int(x):,}")
        sku_display.columns = ["순위", "제품명", "출고 수량", "매출액 (원화)"]

        st.dataframe(
            sku_display,
            use_container_width=True,
            hide_index=True,
        )