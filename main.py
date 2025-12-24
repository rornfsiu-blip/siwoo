import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import unicodedata
from pathlib import Path

# --- 1. 페이지 설정 및 CSS (한글 폰트 적용) ---
st.set_page_config(
    page_title="극지식물 최적 EC 농도 연구",
    page_icon="🌱",
    layout="wide"
)

# Streamlit Cloud 및 로컬 환경 한글 폰트 깨짐 방지 CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# Plotly 차트 공통 폰트 설정
PLOTLY_FONT = dict(family="Noto Sans KR, Malgun Gothic, sans-serif")

# --- 2. 데이터 로딩 및 전처리 함수 (NFC/NFD 해결) ---
@st.cache_data
def load_data():
    """
    데이터 폴더의 파일들을 스캔하여 NFC로 정규화한 뒤,
    키워드 매칭으로 안전하게 데이터를 로드합니다.
    """
    base_path = Path("data")
    
    # 학교별 설정 (목표 EC, 색상 등)
    school_config = {
        "송도고": {"ec": 1.0, "color": "#FF9F36"},
        "하늘고": {"ec": 2.0, "color": "#2ECC71"}, # 최적
        "아라고": {"ec": 4.0, "color": "#3498DB"},
        "동산고": {"ec": 8.0, "color": "#9B59B6"}
    }
    
    env_dfs = []
    growth_df_all = pd.DataFrame()
    
    if not base_path.exists():
        return None, None, "데이터 폴더(data/)가 존재하지 않습니다."

    # 폴더 내 모든 파일 탐색
    files_map = {}
    for p in base_path.iterdir():
        # 파일명을 NFC로 정규화 (Mac/Linux/Windows 호환성 확보)
        norm_name = unicodedata.normalize('NFC', p.name)
        files_map[norm_name] = p

    # 1) 환경 데이터 로드 (CSV)
    for school_name, config in school_config.items():
        found = False
        for fname, fpath in files_map.items():
            if school_name in fname and "환경" in fname and fname.endswith(".csv"):
                try:
                    df = pd.read_csv(fpath)
                    # 컬럼 공백 제거 및 소문자 변환
                    df.columns = df.columns.str.strip().str.lower()
                    
                    # 시간 컬럼 처리
                    if 'time' in df.columns:
                        df['time'] = pd.to_datetime(df['time'], errors='coerce')
                    
                    df['school'] = school_name
                    df['target_ec'] = config['ec']
                    env_dfs.append(df)
                    found = True
                    break
                except Exception as e:
                    return None, None, f"{fname} 로딩 실패: {str(e)}"
        
        if not found:
            # 해당 학교 환경 데이터가 없어도 진행할지, 에러를 낼지 결정 (여기선 경고 후 진행)
            pass

    # 2) 생육 결과 데이터 로드 (XLSX)
    growth_file = None
    for fname, fpath in files_map.items():
        if "생육결과" in fname and fname.endswith(".xlsx"):
            growth_file = fpath
            break
            
    if growth_file:
        try:
            # 시트 전체 로드 (sheet_name=None)
            sheets = pd.read_excel(growth_file, sheet_name=None)
            
            for sheet_name, df in sheets.items():
                norm_sheet = unicodedata.normalize('NFC', sheet_name)
                # 시트 이름이 학교 이름을 포함하는지 확인
                matched_school = next((s for s in school_config.keys() if s in norm_sheet), None)
                
                if matched_school:
                    df['school'] = matched_school
                    df['target_ec'] = school_config[matched_school]['ec']
                    growth_df_all = pd.concat([growth_df_all, df], ignore_index=True)
        except Exception as e:
            return None, None, f"생육 데이터 로딩 실패: {str(e)}"
    else:
        return None, None, "생육결과 엑셀 파일(생육결과...xlsx)을 찾을 수 없습니다."

    if not env_dfs:
        return None, None, "환경 데이터 CSV 파일을 찾을 수 없습니다."

    env_df_all = pd.concat(env_dfs, ignore_index=True)
    return env_df_all, growth_df_all, None

# --- 데이터 로딩 실행 ---
with st.spinner("데이터를 불러오고 있습니다..."):
    env_df, growth_df, error_msg = load_data()

if error_msg:
    st.error(f"🚨 오류 발생: {error_msg}")
    st.stop()

# --- 사이드바 ---
st.sidebar.header("🔍 필터 설정")
school_list = ["전체"] + sorted(env_df['school'].unique().tolist())
selected_school = st.sidebar.selectbox("학교 선택", school_list)

# 데이터 필터링
if selected_school != "전체":
    filtered_env = env_df[env_df['school'] == selected_school]
    filtered_growth = growth_df[growth_df['school'] == selected_school]
else:
    filtered_env = env_df
    filtered_growth = growth_df

# --- 메인 타이틀 ---
st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")
st.markdown("---")

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# ==========================================
# Tab 1: 실험 개요
# ==========================================
with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("연구 목적")
        st.info("""
        **극지식물의 생육에 최적인 EC 농도 탐색**
        
        본 연구는 각기 다른 EC(전기전도도) 환경에서 
        식물의 생장 지표(생중량, 잎 수, 길이)를 비교하여
        최적의 배양 조건을 도출하는 것을 목적으로 합니다.
        """)
        
    with col2:
        st.subheader("실험 조건 요약")
        summary_df = growth_df.groupby(['school', 'target_ec']).size().reset_index(name='개체수')
        summary_df.columns = ['학교명', '목표 EC (dS/m)', '개체수 (n)']
        
        # 스타일링을 위한 데이터프레임 표시
        st.dataframe(
            summary_df.style.background_gradient(cmap="Greens", subset=['목표 EC (dS/m)']),
            use_container_width=True,
            hide_index=True
        )

    st.markdown("### 📌 주요 지표 (Key Metrics)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 분석 개체수", f"{len(growth_df)}개")
    m2.metric("전체 평균 온도", f"{env_df['temperature'].mean():.1f} ℃")
    m3.metric("전체 평균 습도", f"{env_df['humidity'].mean():.1f} %")
    m4.metric("목표 최적 EC", "2.0 (하늘고)", delta="Target", delta_color="normal")

# ==========================================
# Tab 2: 환경 데이터
# ==========================================
with tab2:
    st.header("학교별 환경 데이터 비교")
    
    # 1. 환경 평균 비교 (2x2 Subplots)
    # 학교별 평균 계산
    env_avg = env_df.groupby('school')[['temperature', 'humidity', 'ph', 'ec', 'target_ec']].mean().reset_index()
    
    fig_env = make_subplots(
        rows=2, cols=2,
        subplot_titles=("평균 온도 (℃)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC (dS/m)"),
        vertical_spacing=0.15
    )
    
    # 색상 맵
    colors = px.colors.qualitative.Pastel
    
    # 좌상: 온도
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['temperature'], name="온도", marker_color='#E74C3C'), row=1, col=1)
    # 우상: 습도
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['humidity'], name="습도", marker_color='#3498DB'), row=1, col=2)
    # 좌하: pH
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['ph'], name="pH", marker_color='#F1C40F'), row=2, col=1)
    # 우하: EC 비교 (Grouped Bar)
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['target_ec'], name="목표 EC", marker_color='gray'), row=2, col=2)
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['ec'], name="실측 EC", marker_color='#2ECC71'), row=2, col=2)

    fig_env.update_layout(height=600, showlegend=True, font=PLOTLY_FONT)
    st.plotly_chart(fig_env, use_container_width=True)

    st.divider()

    # 2. 시계열 변화 (선택된 학교만)
    st.subheader(f"⏱️ 시계열 변화 추이 ({selected_school})")
    
    if filtered_env.empty:
        st.warning("선택된 학교의 환경 데이터가 없습니다.")
    else:
        # 시간순 정렬
        ts_df = filtered_env.sort_values('time')
        
        # 탭 내에서 또 탭으로 분리하여 깔끔하게 표시
        t_col1, t_col2, t_col3 = st.columns(3)
        
        # 온도 시계열
        fig_ts1 = px.line(ts_df, x='time', y='temperature', color='school', title="온도 변화")
        fig_ts1.update_layout(font=PLOTLY_FONT)
        t_col1.plotly_chart(fig_ts1, use_container_width=True)
        
        # 습도 시계열
        fig_ts2 = px.line(ts_df, x='time', y='humidity', color='school', title="습도 변화")
        fig_ts2.update_layout(font=PLOTLY_FONT)
        t_col2.plotly_chart(fig_ts2, use_container_width=True)
        
        # EC 시계열 (목표선 추가)
        fig_ts3 = px.line(ts_df, x='time', y='ec', color='school', title="EC 변화")
        # 목표 EC 수평선 추가 (필터링된 데이터의 첫 번째 목표값 사용)
        if 'target_ec' in ts_df.columns:
            target_val = ts_df['target_ec'].iloc[0]
            fig_ts3.add_hline(y=target_val, line_dash="dash", line_color="red", annotation_text="목표 EC")
        fig_ts3.update_layout(font=PLOTLY_FONT)
        t_col3.plotly_chart(fig_ts3, use_container_width=True)

    # 3. 데이터 다운로드
    with st.expander("📥 환경 데이터 원본 보기 및 다운로드"):
        st.dataframe(filtered_env)
        csv_buffer = filtered_env.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="CSV 다운로드",
            data=csv_buffer,
            file_name=f"env_data_{selected_school}.csv",
            mime="text/csv"
        )

# ==========================================
# Tab 3: 생육 결과
# ==========================================
with tab3:
    st.header("📈 EC 농도별 생육 비교 분석")
    
    # 분석용 데이터 집계 (EC별)
    growth_summary = growth_df.groupby(['school', 'target_ec'])[['생중량(g)', '잎 수(장)', '지상부 길이(mm)', '지하부길이(mm)']].mean().reset_index()
    
    # 1. 핵심 결과 카드 (생중량 최댓값)
    if not growth_summary.empty:
        max_row = growth_summary.loc[growth_summary['생중량(g)'].idxmax()]
        st.success(f"🏆 분석 결과, **{max_row['school']} (EC {max_row['target_ec']})** 조건에서 평균 생중량이 **{max_row['생중량(g)']:.2f}g**으로 가장 높았습니다.")
    
    # 2. 2x2 시각화 (생중량, 잎수, 길이, 개체수)
    fig_growth = make_subplots(
        rows=2, cols=2,
        subplot_titles=("평균 생중량 (g) ⭐", "평균 잎 수 (장)", "평균 지상부 길이 (mm)", "학교별 개체수 (n)"),
        vertical_spacing=0.15
    )
    
    # 색상 조건: 하늘고(최적)는 초록색, 나머지는 회색/파랑 계열
    colors = ['#2ECC71' if s == '하늘고' else '#95A5A6' for s in growth_summary['school']]
    
    # 좌상: 생중량
    fig_growth.add_trace(go.Bar(x=growth_summary['school'], y=growth_summary['생중량(g)'], marker_color=colors, name="생중량"), row=1, col=1)
    # 우상: 잎 수
    fig_growth.add_trace(go.Bar(x=growth_summary['school'], y=growth_summary['잎 수(장)'], marker_color=colors, name="잎 수"), row=1, col=2)
    # 좌하: 지상부 길이
    fig_growth.add_trace(go.Bar(x=growth_summary['school'], y=growth_summary['지상부 길이(mm)'], marker_color=colors, name="지상부 길이"), row=2, col=1)
    
    # 우하: 개체수 (원본 DF 사용)
    count_data = growth_df['school'].value_counts().reset_index()
    count_data.columns = ['school', 'count']
    fig_growth.add_trace(go.Bar(x=count_data['school'], y=count_data['count'], marker_color='#34495E', name="개체수"), row=2, col=2)

    fig_growth.update_layout(height=700, showlegend=False, font=PLOTLY_FONT)
    st.plotly_chart(fig_growth, use_container_width=True)
    
    st.divider()
    
    # 3. 상세 분포 및 상관관계
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("#### 📦 학교별 생중량 분포 (Box Plot)")
        fig_box = px.box(filtered_growth, x='school', y='생중량(g)', color='school', points="all")
        fig_box.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig_box, use_container_width=True)
        
    with col_b:
        st.markdown("#### 🔗 잎 수 vs 생중량 상관관계")
        fig_scatter = px.scatter(filtered_growth, x='잎 수(장)', y='생중량(g)', color='school', trendline="ols")
        fig_scatter.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig_scatter, use_container_width=True)

    # 4. 데이터 다운로드 (XLSX - BytesIO 사용 필수)
    with st.expander("📥 생육 데이터 원본 보기 및 다운로드"):
        st.dataframe(filtered_growth)
        
        # Excel 다운로드 로직
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            filtered_growth.to_excel(writer, index=False, sheet_name='Growth_Data')
        buffer.seek(0)
        
        st.download_button(
            label="XLSX 다운로드",
            data=buffer,
            file_name="polar_plant_growth_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
