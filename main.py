import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from pathlib import Path
import unicodedata
import io

# =========================
# Streamlit 기본 설정
# =========================
st.set_page_config(
    page_title="🌱 극지식물 최적 EC 농도 연구",
    layout="wide"
)

# =========================
# 한글 폰트 (CSS)
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

PLOTLY_FONT = dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# =========================
# 공통 경로
# =========================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# =========================
# 유니코드 안전 파일 탐색
# =========================
def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFC", name)

def find_file(target_name: str) -> Path | None:
    target_norm = normalize_name(target_name)
    for p in DATA_DIR.iterdir():
        if normalize_name(p.name) == target_norm:
            return p
    return None

# =========================
# 데이터 로딩
# =========================
@st.cache_data
def load_env_data():
    school_files = {
        "송도고": "송도고_환경데이터.csv",
        "하늘고": "하늘고_환경데이터.csv",
        "아라고": "아라고_환경데이터.csv",
        "동산고": "동산고_환경데이터.csv",
    }

    env_data = {}
    for school, fname in school_files.items():
        path = find_file(fname)
        if path is None:
            st.error(f"❌ 환경 데이터 파일을 찾을 수 없습니다: {fname}")
            continue
        df = pd.read_csv(path)
        df["school"] = school
        env_data[school] = df
    return env_data

@st.cache_data
def load_growth_data():
    xlsx_path = find_file("4개교_생육결과데이터.xlsx")
    if xlsx_path is None:
        st.error("❌ 생육 결과 XLSX 파일을 찾을 수 없습니다.")
        return {}

    xls = pd.ExcelFile(xlsx_path)
    growth = {}
    for sheet in xls.sheet_names:
        df = pd.read_excel(xlsx_path, sheet_name=sheet)
        df["school"] = sheet
        growth[sheet] = df
    return growth

# =========================
# 데이터 로딩 실행
# =========================
with st.spinner("📂 데이터 로딩 중..."):
    env_data = load_env_data()
    growth_data = load_growth_data()

if not env_data or not growth_data:
    st.stop()

# =========================
# 메타 정보
# =========================
EC_INFO = {
    "송도고": 1.0,
    "하늘고": 2.0,
    "아라고": 4.0,
    "동산고": 8.0,
}

# =========================
# Sidebar
# =========================
st.sidebar.title("🏫 학교 선택")
school_option = st.sidebar.selectbox(
    "학교",
    ["전체"] + list(EC_INFO.keys())
)

# =========================
# 제목
# =========================
st.title("🌱 극지식물 최적 EC 농도 연구")

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# =====================================================
# Tab 1: 실험 개요
# =====================================================
with tab1:
    st.subheader("🔬 연구 배경 및 목적")
    st.markdown(
        """
        극지 환경을 모사한 조건에서 **전기전도도(EC)** 농도에 따른 식물 생육 차이를 분석하여  
        **최적 EC 조건을 과학적으로 도출**하는 것이 본 연구의 목적이다.
        """
    )

    info_df = pd.DataFrame({
        "학교명": EC_INFO.keys(),
        "EC 목표": EC_INFO.values(),
        "개체수": [len(growth_data[k]) for k in EC_INFO.keys()]
    })

    st.subheader("🏫 학교별 EC 조건")
    st.dataframe(info_df, use_container_width=True)

    all_env = pd.concat(env_data.values())
    total_plants = sum(len(df) for df in growth_data.values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 개체수", total_plants)
    c2.metric("평균 온도", f"{all_env['temperature'].mean():.1f} °C")
    c3.metric("평균 습도", f"{all_env['humidity'].mean():.1f} %")
    c4.metric("최적 EC", "2.0 (하늘고) ⭐")

# =====================================================
# Tab 2: 환경 데이터
# =====================================================
with tab2:
    st.subheader("📈 학교별 환경 평균 비교")

    avg_df = all_env.groupby("school").mean(numeric_only=True).reset_index()

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("평균 온도", "평균 습도", "평균 pH", "목표 EC vs 실측 EC")
    )

    fig.add_trace(go.Bar(x=avg_df["school"], y=avg_df["temperature"]), 1, 1)
    fig.add_trace(go.Bar(x=avg_df["school"], y=avg_df["humidity"]), 1, 2)
    fig.add_trace(go.Bar(x=avg_df["school"], y=avg_df["ph"]), 2, 1)

    fig.add_trace(
        go.Bar(
            x=list(EC_INFO.keys()),
            y=list(EC_INFO.values()),
            name="목표 EC"
        ),
        2, 2
    )
    fig.add_trace(
        go.Bar(
            x=avg_df["school"],
            y=avg_df["ec"],
            name="실측 EC"
        ),
        2, 2
    )

    fig.update_layout(height=600, font=PLOTLY_FONT)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("⏱️ 시계열 데이터")

    if school_option == "전체":
        st.info("개별 학교 선택 시 시계열 그래프가 표시됩니다.")
    else:
        df = env_data[school_option]

        for col, title in zip(
            ["temperature", "humidity", "ec"],
            ["온도 변화", "습도 변화", "EC 변화"]
        ):
            fig_line = px.line(df, x="time", y=col, title=title)
            if col == "ec":
                fig_line.add_hline(y=EC_INFO[school_option], line_dash="dash")
            fig_line.update_layout(font=PLOTLY_FONT)
            st.plotly_chart(fig_line, use_container_width=True)

        with st.expander("📄 환경 데이터 원본"):
            st.dataframe(df)
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "CSV 다운로드",
                data=csv,
                file_name=f"{school_option}_환경데이터.csv",
                mime="text/csv"
            )

# =====================================================
# Tab 3: 생육 결과
# =====================================================
with tab3:
    st.subheader("🥇 EC별 평균 생중량")

    growth_all = pd_
