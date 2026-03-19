import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
st.set_page_config(page_title="2026 hince Revenue Audit", layout="wide")

# --- 2. 데이터 로드 (캐시 제거하여 실시간 반영) ---
def get_master_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        response = supabase.table("SS_Master").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

df_raw = get_master_data()

# --- 3. 사용자 요청 열 로직 (A, C, M, AJ열) 엄격 적용 ⭐ ---
def audit_preprocess(df):
    if df.empty: return df
    
    # 공백 제거
    df.columns = [str(c).strip() for c in df.columns]

    # [AJ열: 연도] - 정확한 매핑 필요 (컬럼명이 '연도' 인지 확인)
    col_year = '연도' 
    df['Y_AUDIT'] = pd.to_numeric(df[col_year], errors='coerce').fillna(0).astype(int)

    # [A열: 월] - 정확히 '-' 컬럼
    col_month = '-'
    df['M_AUDIT'] = df[col_month].astype(str).str.strip()

    # [C열: 거래처명] - 'CUSTOMER' 혹은 '재무_거래처명'
    col_customer = 'CUSTOMER'
    df['C_AUDIT'] = df[col_customer].astype(str).str.strip()

    # [N열: 매출액] - 반드시 이 컬럼의 숫자만 더함 ⭐
    col_rev = '매출액'
    # 숫자가 아닌 문자 제거 후 실수(float) 변환
    df['N_REV'] = pd.to_numeric(df[col_rev].astype(str).str.replace(r'[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
    
    return df

df_clean = audit_preprocess(df_raw)

# --- 4. 2026년 3월 데이터만 현미경 필터링 ⭐ ---
# 연도: 2026 / 월: 정확히 '3월'
f_2026_march = df_clean[(df_clean['Y_AUDIT'] == 2026) & (df_clean['M_AUDIT'] == '3월')].copy()

# 3월 총 매출액 계산
march_total = f_2026_march['N_REV'].sum()

# --- 5. 메인 화면 출력 ---
st.markdown(f'<h1 style="color: #A37F7D;">🔍 2026년 3월 매출액 정밀 검증</h1>', unsafe_allow_html=True)

# KPI 카드
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("선택된 연도", "2026년 (AJ열)")
with c2:
    # 여기가 사용자님이 말씀하신 숫자가 나오는 곳입니다.
    st.error(f"계산된 3월 총 매출액: ₩{march_total:,.0f}")
with k3 := c3:
    st.metric("3월 데이터 행 수", f"{len(f_2026_march)} 건")

st.markdown("---")

# 💡 [핵심] 311,600,813원이 어떻게 나왔는지 거래처별로 낱낱이 보여줌
st.subheader("📋 3월 매출 합산 내역 (이 리스트를 엑셀과 비교해 보세요)")
if not f_2026_march.empty:
    # 검증을 위해 원본 '매출액' 글자와 계산된 '숫자'를 같이 보여줍니다.
    audit_display = f_2026_march[['M_AUDIT', 'C_AUDIT', '매출액', 'N_REV', 'Y_AUDIT']]
    audit_display.columns = ['월(A열)', '거래처(C열)', '원본문구(N열)', '계산된금액(N열)', '연도(AJ열)']
    
    st.dataframe(audit_display, use_container_width=True, hide_index=True)
    
    # 막대 그래프
    st.markdown("### ■ 3월 거래처별 매출 비중")
    fig = px.bar(audit_display, x='거래처(C열)', y='계산된금액(N열)', text_auto=',.0f', color='거래처(C열)')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', height=400)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("3월에 해당하는 데이터가 하나도 없습니다. DB에서 '3월'과 '2026'이 동시에 있는 행이 있는지 확인해주세요.")

# 전체 연도 데이터 확인용
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    st.write("📊 **데이터 분포 확인**")
    st.write("DB에 있는 연도들:", df_clean['Y_AUDIT'].unique().tolist())
    st.write("DB에 있는 월들:", df_clean['M_AUDIT'].unique().tolist())