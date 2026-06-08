import pandas as pd

def generate_looksam_labeling_file():
    """
    [설명] looksam_chats.csv 파일의 절대 타임스탬프 구조를 분석하여,
    진짜 영상 재생 시간 기준 30분 이후의 채팅 데이터만 1,000줄 추출합니다.
    """
    input_file = "looksam_chats.csv"
    output_file = "wbb_labeling_work_looksam.csv"
    
    # 우리가 원하는 건 영상 시작 후 30분 지점 (= 1,800,000 밀리초)
    offset_30_min_ms = 30 * 60 * 1000 
    
    try:
        # 1. 0초부터 수집된 원본 채팅 파일 로드
        df = pd.read_csv(input_file)
        
        # 2. [버그 수정 핵심] 파일의 최상단 첫 번째 행의 time_ms를 영상의 진짜 0초 시점으로 바인딩
        video_start_timestamp = df["time_ms"].iloc[0]
        
        # 3. 진짜 영상 시작 절대 시간에 30분(1,800,000ms)을 더해 올바른 필터링 타겟 타임 계산
        target_time_ms = video_start_timestamp + offset_30_min_ms
        
        # 4. 수정된 절대 시간 기준값을 적용하여 진짜 30분 이후의 행들만 필터링
        filtered_df = df[df["time_ms"] >= target_time_ms].copy()
        
        # 5. 혼자 진행하는 라벨링 공수 분량을 고려해 해당 지점부터 정확히 1,000줄만 슬라이싱
        final_work_df = filtered_df.head(1000).copy()
        
        # 6. KoBERT 파인튜닝 학습 데이터 포맷에 맞게 빈 label 열 추가
        final_work_df["label"] = ""
        
        # 7. 엑셀 한글 깨짐을 방지하는 인코딩 규격을 지정하여 최종 파일 생성
        final_work_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        
        print(f"🏁 30분 지점 타겟 라벨링 파일 생성 완료: {output_file}")
        print(f"📊 영상 시작 타임스탬프: {video_start_timestamp}")
        print(f"📊 필터링 적용 타임스탬프 (30분 후): {target_time_ms}")
        print(f"📊 최종 추출된 데이터 규모: {len(final_work_df)} 줄")
        
    except FileNotFoundError:
        print(f"❌ 오류: '{input_file}' 파일이 디렉토리에 없습니다.")
    except Exception as e:
        print(f"❌ 예외 에러 발생: {str(e)}")

if __name__ == "__main__":
    generate_looksam_labeling_file()