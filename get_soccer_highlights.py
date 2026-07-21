import requests
import pandas as pd
import time

def extract_soccer_raw_chats():
    """
    [설명] 대한민국 vs 체코 축구 VOD(13666314) 후반전 무필터 수집 엔진 (최종 보정본)
    400 에러를 유발하던 절대 타임스탬프 주입 방식을 폐기하고, API 동기화 규격에 맞추어
    2시간 27분 지점부터 연속된 순수 채팅 데이터를 정확히 2,000줄 수집합니다.
    """
    video_id = "13666314"
    output_file = "wbb_labeling_work_worldcup.csv"
    
    # [시간 동기화] 유저가 지정한 재생 시간 (2시간 27분 및 3시간 3분)을 밀리초(ms)로 환산
    start_time_ms = (2 * 60 * 60 + 27 * 60) * 1000  # 2시간 27분 = 8,820,000 ms
    end_time_ms = (3 * 60 * 60 + 3 * 60) * 1000     # 3시간 03분 = 10,980,000 ms
    
    current_time_ms = start_time_ms
    raw_records = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"🚀 [체코전 후반전] 무필터 2,000줄 데이터 수집 파이프라인 가동...")
    print(f"📍 타겟 재생 타임라인: {start_time_ms}ms 지점 진입 시도")

    while True:
        # 네이버 API 표준 규격에 맞게 상대 재생 시간 밀리초를 파라미터로 직접 바인딩
        target_url = f"https://api.chzzk.naver.com/service/v1/videos/{video_id}/chats?playerMessageTime={current_time_ms}&previousVideoChatSize=50"
        
        try:
            response = requests.get(target_url, headers=headers, timeout=5)
            if response.status_code != 200:
                print(f"❌ 네이버 서버 통신 에러 (HTTP 코드: {response.status_code})")
                break
                
            res_json = response.json()
            content = res_json.get("content", {})
            chat_list = content.get("videoChats", [])
            
            for chat in chat_list:
                msg = chat.get("content")
                
                # ★ 핵심 교정: 13자리 절대 시간이 아닌, 객체 내부에 포함된 비디오 상대 시간(playerMessageTime) 추출
                chat_player_time = chat.get("playerMessageTime")
                
                # 설정한 종료 시간(3시간 3분)을 넘어서면 수집 즉시 중단 (타입 불일치 버그 해결)
                if chat_player_time and chat_player_time > end_time_ms:
                    break
                
                if msg:
                    raw_records.append({
                        "time_ms": chat.get("messageTime"), # 기존 데이터셋 구조와의 호환성을 위한 절대 시간 기록
                        "chat_message": str(msg)
                    })
                    
                # 목표 수량인 2,000줄이 충족되면 배열 적재 즉시 중단
                if len(raw_records) >= 2000:
                    break
            
            # 실제 파일 진행률 터미널 모니터링 출력
            if chat_list:
                last_time = chat_list[-1].get("playerMessageTime")
                print(f"🔄 재생시간 {last_time // 60000}분 {(last_time % 60000) // 1000}초 구역 통과 중... (누적: {len(raw_records)}/2000 줄)")
            
            # 2,000줄 조건 충족 시 전체 무한 루프 탈출
            if len(raw_records) >= 2000:
                print("\n🎯 체코 골 장면 이후 순수 연속 채팅 2,000줄 수집 완료!")
                break
                
            next_time = content.get("nextPlayerMessageTime")
            
            if next_time is None or next_time == -1 or next_time == current_time_ms or next_time > end_time_ms:
                print("🏁 지정한 시간 경계선을 무사히 통과하여 엔진을 안전하게 중지합니다.")
                break
                
            current_time_ms = next_time
            time.sleep(0.2) # 네이버 디도스 오차 방지용 인터벌 슬립
            
        except Exception as e:
            print(f"❌ 크롤링 구동 중 치명적 예외 발생: {str(e)}")
            break

    # 가공 데이터프레임 CSV 디스크 저장
    if raw_records:
        df = pd.DataFrame(raw_records).head(2000)
        df["label"] = "" # 수동 감정 마킹용 공란 열 할당
        
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"🎉 최상위 작업 디렉토리에 '{output_file}' 파일이 정상 빌드되었습니다.")
    else:
        print("❌ 최종 데이터 적재에 실패했습니다. 다시 실행해 주십시오.")

if __name__ == "__main__":
    extract_soccer_raw_chats()