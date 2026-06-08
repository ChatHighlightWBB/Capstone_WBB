import pandas as pd

def generate_meme_balanced_file():
    """
    [설명] 룩삼 VOD 원본 데이터에서 지정된 감정 및 밈 핵심 키워드가 
    포함된 행만 골라내어 '독립된 별도의 파일'로 안전하게 추출합니다.
    """
    input_file = "looksam_chats.csv"
    
    # [버그 방지] 기존 수작업 파일이 날아가지 않도록 파일명 뒤에 _balanced를 붙여 격리합니다.
    output_file = "wbb_labeling_work_looksam_balanced.csv"
    
    # 영상 시작 후 30분 지점 밀리초 계산
    target_time_ms = 30 * 60 * 1000 
    
    # 요청하신 핵심 키워드 목록 바인딩
    emotion_keywords = [
        "ㅋ", "ㅎ", "ㄷㄷ", "??", "!?", "오", "와", "헐", "캬", 
        "나이스", "개못", "핵", "레전드", "극혐", "망했", "진짜"
    ]
    
    try:
        # 1. 31,843줄짜리 전구간 순수 원본 채팅 로드
        df = pd.read_csv(input_file)
        
        # 2. 영상 시작 타임스탬프를 기점으로 30분 이후 구간만 1차 필터링
        video_start_timestamp = df["time_ms"].iloc[0]
        adjusted_target_time = video_start_timestamp + target_time_ms
        filtered_df = df[df["time_ms"] >= adjusted_target_time].copy()
        
        # 3. 데이터 공백 및 문자열 예외 처리 후 감정 키워드 포함 행만 2차 필터링
        balanced_df = filtered_df[
            filtered_df["chat_message"].apply(
                lambda x: any(keyword in str(x) for keyword in emotion_keywords)
            )
        ].copy()
        
        # 4. 필터링된 유의미 데이터셋 중 상위 1,000줄 확정 슬라이싱
        final_work_df = balanced_df.head(1000).copy()
        
        # 5. 혼자 진행하는 KoBERT 학습용 label 빈 컬럼 할당
        final_work_df["label"] = ""
        
        # 6. 인코딩 설정을 적용하여 별도 파일명으로 디스크 출력
        final_work_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        
        print(f"🎯 키워드 필터링 전용 파일 생성 완료: {output_file}")
        print(f"📊 조건에 맞는 전체 채팅 수: {len(balanced_df)} 줄")
        print(f"📊 최종 적재된 라벨링 작업 규모: {len(final_work_df)} 줄")
        
    except FileNotFoundError:
        print(f"❌ 오류: '{input_file}' 파일이 경로에 없습니다. 크롤러 동작을 먼저 확인하세요.")
    except Exception as e:
        print(f"❌ 예외 에러 발생: {str(e)}")

if __name__ == "__main__":
    generate_meme_balanced_file()