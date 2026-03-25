import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components
from supabase import create_client, Client

# ─────────────────────────────────────────
# 1. 페이지 설정 & 스타일
# ─────────────────────────────────────────
st.set_page_config(page_title="hince Global Dashboard", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* { font-family: 'Inter', sans-serif; }
.main { background-color: #F7F5F4; }
.block-container { padding-top: 2rem !important; }
.section-title {
    font-size: 18px;
    font-weight: 700;
    color: #2D2D2D;
    margin: 28px 0 14px 0;
    letter-spacing: -0.3px;
}
h3 {
    color: #2D2D2D !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    margin-bottom: 8px !important;
}
/* 월별 요약 테이블 */
.summary-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 8px;
}
.summary-table th {
    background: #F5F0EF;
    color: #A37F7D;
    font-weight: 600;
    padding: 7px 10px;
    text-align: center;
    border-bottom: 2px solid #E8E0DF;
}
.summary-table td {
    padding: 6px 10px;
    text-align: center;
    border-bottom: 1px solid #F3F4F6;
    color: #374151;
    font-weight: 500;
}
.summary-table tr:last-child td { border-bottom: none; }
.summary-table tr:hover td { background: #FAF7F7; }
.summary-table td:first-child { font-weight: 700; color: #A37F7D; }
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
                'Y, M, 채널명, 제품판매수량, "매출취합용_공급가액(원화기준)", 중, 제품명, FOC'
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

    df["제품판매수량"] = (
        df["제품판매수량"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    df["매출액_num"] = (
        df["매출취합용_공급가액(원화기준)"]
        .astype(str)
        .str.replace("₩", "", regex=False)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    mask = (
        ((df["Y"] == 2025) & (df["M"] >= 4)) |
        ((df["Y"] == 2026) & (df["M"] <= 3))
    )
    df = df[mask].copy()

    df["월_label"] = (
        df["Y"].astype(int).astype(str).str[-2:] + "." +
        df["M"].astype(int).astype(str).str.zfill(2)
    )
    df["sort_key"] = df["Y"] * 100 + df["M"]

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
# 4. 헤더 (로고 + 타이틀)
# ─────────────────────────────────────────
logo_col, title_col = st.columns([1, 9])
with logo_col:
    st.image("hince.png", width=120)
with title_col:
    st.markdown("""
    <div style="padding-top: 10px;">
        <div style="font-size:28px; font-weight:700; color:#2D2D2D; letter-spacing:-0.5px;">
            hince Global Dashboard
        </div>
        <div style="font-size:13px; color:#A37F7D; font-weight:500; margin-top:4px;">
            Sell-in Performance · 2025.04 – 2026.03
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────
# 5. 2026 월별 KPI 카드 (1~3월)
# ─────────────────────────────────────────
st.markdown('<div class="section-title">📅 2026 월별 주요 지표</div>', unsafe_allow_html=True)

if not df.empty:
    kpi_months = [(2026, 1, "2026년 1월"), (2026, 2, "2026년 2월"), (2026, 3, "2026년 3월")]
    kpi_cols = st.columns(3)

    for col, (y, m, label) in zip(kpi_cols, kpi_months):
        m_df = df[(df["Y"] == y) & (df["M"] == m)]

        non_foc = m_df[m_df["FOC"] != "Y"]
        foc     = m_df[m_df["FOC"] == "Y"]

        rev              = non_foc["매출액_num"].sum()
        total_qty        = non_foc["제품판매수량"].sum()
        foc_qty          = foc["제품판매수량"].sum()
        active_customers = non_foc[non_foc["매출액_num"] > 0]["채널명"].nunique()
        avg_rev          = rev / active_customers if active_customers > 0 else 0

        with col:
            components.html(f"""
            <!DOCTYPE html><html><head>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                * {{ font-family: 'Inter', sans-serif; box-sizing: border-box; margin: 0; padding: 0; }}
                body {{ background: transparent; }}
                .kpi-card {{
                    background: #FFFFFF;
                    padding: 20px 18px;
                    border-radius: 16px;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
                    border: 1px solid #F0EDED;
                }}
                .kpi-month {{ color: #A37F7D; font-size: 15px; font-weight: 700; margin-bottom: 14px; text-align: center; }}
                .kpi-row {{ display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid #F3F4F6; }}
                .kpi-row:last-child {{ border-bottom: none; }}
                .kpi-label {{ color: #9CA3AF; font-size: 12px; font-weight: 500; }}
                .kpi-value {{ color: #1F2937; font-size: 16px; font-weight: 700; }}
                .kpi-value-highlight {{ color: #A37F7D; font-size: 20px; font-weight: 700; }}
            </style>
            </head><body>
            <div class="kpi-card">
                <div class="kpi-month">📆 {label}</div>
                <div class="kpi-row">
                    <span class="kpi-label">매출액 (FOC 제외)</span>
                    <span class="kpi-value-highlight">₩{int(rev):,}</span>
                </div>
                <div class="kpi-row">
                    <span class="kpi-label">총 출고량 (FOC 제외)</span>
                    <span class="kpi-value">{int(total_qty):,} 개</span>
                </div>
                <div class="kpi-row">
                    <span class="kpi-label">FOC 출고량</span>
                    <span class="kpi-value">{int(foc_qty):,} 개</span>
                </div>
                <div class="kpi-row">
                    <span class="kpi-label">활성 거래처 수</span>
                    <span class="kpi-value">{active_customers} 개</span>
                </div>
                <div class="kpi-row">
                    <span class="kpi-label">거래처당 평균 매출</span>
                    <span class="kpi-value">₩{int(avg_rev):,}</span>
                </div>
            </div>
            </body></html>
            """, height=290)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

# ─────────────────────────────────────────
# 6. 그래프 영역 (3열 레이아웃)
# ─────────────────────────────────────────
st.markdown('<div class="section-title">📊 Sell-in 트렌드 분석</div>', unsafe_allow_html=True)
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

# ── 그래프 2: 월별 매출액 (FOC 제외) ────────
with col2:
    st.markdown("### 💰 월별 Sell-in 매출액 (원화 기준)")

    if df.empty:
        st.info("데이터 없음")
    else:
        rev_df = (
            df[df["FOC"] != "Y"]
            .groupby(["sort_key", "월_label"])["매출액_num"]
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

            fig3.update_traces(line=dict(width=2.5), marker=dict(size=8))

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
# 7. 월별 요약 표 (그래프 아래)
# ─────────────────────────────────────────
if not df.empty:
    summary = (
        df[df["FOC"] != "Y"]
        .groupby(["sort_key", "월_label"])
        .agg(
            출고량=("제품판매수량", "sum"),
            매출액=("매출액_num", "sum"),
        )
        .reset_index()
        .sort_values("sort_key")
    )

    rows_html = ""
    for _, row in summary.iterrows():
        rows_html += f"""
        <tr>
            <td>{row['월_label']}</td>
            <td>{int(row['출고량']):,}</td>
            <td>₩{int(row['매출액']):,}</td>
        </tr>
        """

    components.html(f"""
    <!DOCTYPE html><html><head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        * {{ font-family: 'Inter', sans-serif; box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ background: transparent; padding: 4px 0; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        th {{
            background: #F5F0EF;
            color: #A37F7D;
            font-weight: 600;
            padding: 8px 12px;
            text-align: center;
            border-bottom: 2px solid #E8E0DF;
        }}
        td {{
            padding: 7px 12px;
            text-align: center;
            border-bottom: 1px solid #F3F4F6;
            color: #374151;
            font-weight: 500;
        }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: #FAF7F7; }}
        td:first-child {{ font-weight: 700; color: #A37F7D; }}
        td:nth-child(3) {{ color: #1F2937; font-weight: 600; }}
    </style>
    </head><body>
    <table>
        <thead>
            <tr>
                <th>월</th>
                <th>출고량 (FOC 제외)</th>
                <th>매출액 (FOC 제외)</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    </body></html>
    """, height=60 + len(summary) * 34)

# ─────────────────────────────────────────
# 8. Top Selling SKU 테이블 (최근 3개월, FOC 제외)
# ─────────────────────────────────────────
st.markdown("---")
st.markdown('<div class="section-title">🏆 Top Selling SKU — 최근 3개월 (2026.01 ~ 2026.03)</div>', unsafe_allow_html=True)

if df.empty:
    st.info("데이터 없음")
else:
    sku_df = df[
        (df["Y"] == 2026) & (df["M"] <= 3) & (df["FOC"] != "Y")
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

        sku_table.insert(0, "순위", range(1, len(sku_table) + 1))

        sku_display = sku_table.copy()
        sku_display["총_출고수량"] = sku_display["총_출고수량"].apply(lambda x: f"{int(x):,}")
        sku_display["총_매출액"] = sku_display["총_매출액"].apply(lambda x: f"₩{int(x):,}")
        sku_display.columns = ["순위", "제품명", "출고 수량", "매출액 (원화)"]

        st.dataframe(
            sku_display,
            use_container_width=True,
            hide_index=True,
        )