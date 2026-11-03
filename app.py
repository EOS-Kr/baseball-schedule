import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="사회인 야구 대진표 생성기", layout="wide")
st.title("⚾ 사회인 야구 주말리그 대진표 생성기")

# --- 사이드바: 설정 입력 ---
with st.sidebar:
    st.header("1. 기본 일정 설정")
    start_date = st.date_input("리그 개막일 (토요일 권장)", datetime(2026, 3, 7))
    if start_date.weekday() != 5:
        st.warning("선택하신 날짜가 토요일이 아닙니다. 가급적 토요일을 선택해 주세요.")
        
    st.header("2. 구장 및 시간대 설정")
    stadiums_input = st.text_input("4개 구장 이름 (쉼표로 구분)", "1구장, 2구장, 3구장, 4구장")
    times_input = st.text_input("하루 경기 시간대 (2개, 쉼표 구분)", "10:00, 13:00")
    
    st.header("3. 리그별 팀 명단 (각 8팀)")
    leagues = {}
    default_leagues = ["A리그", "B리그", "C리그", "D리그"]
    for idx, l_name in enumerate(default_leagues):
        default_teams = ", ".join([f"{l_name[0]}{i}팀" for i in range(1, 9)])
        t_input = st.text_area(f"{l_name} 팀 목록 (쉼표로 구분)", default_teams, height=68)
        leagues[l_name] = [t.strip() for t in t_input.split(",") if t.strip()]

# --- 대진표 생성 알고리즘 (더블 라운드 로빈) ---
def generate_round_robin(teams):
    n = len(teams)
    rounds = []
    # 전반기 7라운드 생성 (Berger Tables 회전 방식)
    for r in range(n - 1):
        round_matches = []
        for i in range(n // 2):
            t1 = teams[i]
            t2 = teams[n - 1 - i]
            # 홈/어웨이 균형을 위해 라운드 및 인덱스별로 교차 배치
            if i == 0:
                if r % 2 == 0:
                    round_matches.append((t1, t2))
                else:
                    round_matches.append((t2, t1))
            else:
                if i % 2 == 1:
                    round_matches.append((t1, t2))
                else:
                    round_matches.append((t2, t1))
        rounds.append(round_matches)
        # 마지막 팀(8번)을 고정하고 나머지 팀 회전
        teams = teams[:-2] + [teams[-1]] + [teams[-2]]
        teams = [teams[-2]] + teams[:-2] + [teams[-1]]
    
    # 후반기 7라운드 생성 (전반기 대진에서 홈/어웨이만 정확히 반전)
    second_half = []
    for r_matches in rounds:
        second_half.append([(away, home) for home, away in r_matches])
        
    return rounds + second_half

# --- 메인 화면 및 실행 로직 ---
stadiums = [s.strip() for s in stadiums_input.split(",") if s.strip()]
time_slots = [t.strip() for t in times_input.split(",") if t.strip()]

# 입력값 검증
valid = True
if len(stadiums) != 4:
    st.error("구장은 정확히 4개를 입력해야 합니다.")
    valid = False
if len(time_slots) != 2:
    st.error("1개 라운드(16경기)를 주말 양일간 4개 구장에서 소화하려면 하루 시간대는 2개여야 합니다.")
    valid = False
for l_name, t_list in leagues.items():
    if len(t_list) != 8:
        st.error(f"{l_name}의 팀 수가 {len(t_list)}개입니다. 정확히 8팀을 입력해 주세요.")
        valid = False

if valid and st.button("대진표 생성하기", type="primary"):
    league_schedules = {l_name: generate_round_robin(list(t_list)) for l_name, t_list in leagues.items()}
    league_names = list(leagues.keys())
    
    schedule_data = []
    
    # 총 14라운드(14주) 주간 배정
    for r in range(14):
        sat_date = start_date + timedelta(weeks=r)
        sun_date = sat_date + timedelta(days=1)
        
        for l_idx, l_name in enumerate(league_names):
            matches = league_schedules[l_name][r] # 해당 라운드의 리그별 4경기
            
            # 리그별 구장 순환 배정 (주차마다 구장 로테이션)
            for m_idx, (home, away) in enumerate(matches):
                # 4경기를 토요일 2경기, 일요일 2경기로 분할 및 라운드별 요일 교차
                day_offset = (m_idx // 2 + r) % 2
                match_date = sat_date if day_offset == 0 else sun_date
                day_str = "토" if day_offset == 0 else "일"
                
                # 시간대 교차 배정
                time_str = time_slots[(m_idx + r) % 2]
                
                # 구장 균등 순환 배정
                stadium_str = stadiums[(l_idx + m_idx + r) % 4]
                
                schedule_data.append({
                    "라운드": f"{r+1}주차",
                    "날짜": match_date.strftime("%Y-%m-%d"),
                    "요일": day_str,
                    "시간": time_str,
                    "구장": stadium_str,
                    "리그": l_name,
                    "어웨이(선공)": away,
                    "홈(후공)": home
                })
                
    df = pd.DataFrame(schedule_data)
    # 날짜, 시간, 구장 순으로 깔끔하게 정렬
    df = df.sort_values(by=["날짜", "시간", "구장"]).reset_index(drop=True)
    
    st.success("총 14주차(224경기) 대진표가 성공적으로 생성되었습니다!")
    
    # 탭 구성: 전체 일정 보기 / 검증 표 보기
    tab1, tab2 = st.tabs(["📅 전체 대진표", "📊 팀별 홈/어웨이 및 구장 배정 통계"])
    
    with tab1:
        # 필터 기능 제공
        col1, col2 = st.columns(2)
        with col1:
            selected_league = st.multiselect("리그 필터", league_names, default=league_names)
        with col2:
            selected_stadium = st.multiselect("구장 필터", stadiums, default=stadiums)
            
        filtered_df = df[df["리그"].isin(selected_league) & df["구장"].isin(selected_stadium)]
        st.dataframe(filtered_df, use_container_width=True, height=500)
        
        # 엑셀 다운로드 버튼 생성
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="전체대진표")
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 전체 대진표 엑셀(.xlsx) 다운로드",
            data=excel_data,
            file_name="사회인야구_주말리그_대진표.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    with tab2:
        st.subheader("팀별 홈/어웨이 경기 수 검증 (각 7경기씩 총 14경기)")
        home_counts = df.groupby(["리그", "홈(후공)"]).size().unstack(fill_value=0).stack()
        away_counts = df.groupby(["리그", "어웨이(선공)"]).size().unstack(fill_value=0).stack()
        stats_df = pd.DataFrame({"홈 경기 수": home_counts, "어웨이 경기 수": away_counts})
        stats_df["총 경기 수"] = stats_df["홈 경기 수"] + stats_df["어웨이 경기 수"]
        st.dataframe(stats_df, use_container_width=True)