import requests
import pandas as pd
import time

def extract_norway_chats():
    """
    [설명] 노르웨이 vs 잉글랜드 8강전 VOD(14153628) 하이라이트 수집 엔진
    1시간 5분 ~ 1시간 20분 사이의 순수 채팅을 무필터로 정확히 2,000줄 수집합니다.
    """
    video_id = "14153628"  # 스크린샷 주소창에서 확인한 노르웨이전 고유 영상 ID
    output_file = "wbb_labeling_work_norway.csv"
    
    # 1시간 5분과 1시간 20분을 밀리초(ms) 단위 정수로 환산
    start_time_ms = (1 * 60 * 60 + 5 * 60) * 1000   # 3,900,000 ms
    end_time_ms = (1 * 60 * 60 + 20 * 60) * 1000  # 4,800,000 ms
    
    current_time_ms = start_time_ms
    raw_records = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    print(f"🚀 노르웨이전 수집 가동: {start_time_ms}ms 지점(1시간 5분)부터 탐색 시작...")

    while True:
        target_url = f"https://api.chzzk.naver.com/service/v1/videos/{video_id}/chats?playerMessageTime={current_time_ms}&previousVideoChatSize=50"
        
        try:
            response = requests.get(target_url, headers=headers, timeout=5)
            if response.status_code != 200:
                print(f"❌ 네이버 통신 실패 (HTTP 코드: {response.status_code})")
                break
                
            res_json = response.json()
            content = res_json.get("content", {})
            chat_list = content.get("videoChats", [])
            
            if not chat_list:
                print("🏁 해당 구간에 더 이상 가져올 채팅이 없어 종료합니다.")
                break
            
            for chat in chat_list:
                msg = chat.get("content")
                chat_player_time = chat.get("playerMessageTime")
                
                # 설정한 종료 시간 경계(1시간 20분)를 넘어가면 루프 차단
                if chat_player_time and chat_player_time > end_time_ms:
                    break
                
                if msg:
                    raw_records.append({
                        "time_ms": chat.get("messageTime"),
                        "chat_message": str(msg)
                    })
                    
                # 목표 수량 2,000줄 충족 시 내부 루프 탈출
                if len(raw_records) >= 2000:
                    break
            
            # 터미널에 현재 수집 중인 영상 시/분/초 현황 출력
            if chat_list:
                last_p_time = chat_list[-1].get("playerMessageTime")
                current_min = last_p_time // 60000
                current_sec = (last_p_time % 60000) // 1000
                print(f"🔄 재생시간 {current_min}분 {current_sec}초 통과 중... (누적: {len(raw_records)}/2000 줄)")
            
            # 2,000줄 달성 시 전체 시스템 종료
            if len(raw_records) >= 2000:
                print("\n🎯 목표 하이라이트 2,000줄 수집 완료!")
                break
                
            next_time = content.get("nextPlayerMessageTime")
            if next_time is None or next_time == -1 or next_time == current_time_ms or next_time > end_time_ms:
                print("🏁 지정한 시간 경계선을 통과하여 수집을 종료합니다.")
                break
                
            current_time_ms = next_time
            time.sleep(0.2) # 차단 우회용 보수적 인터벌
            
        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {str(e)}")
            break

    # 파일 디스크 저장
    if raw_records:
        df = pd.DataFrame(raw_records).head(2000)
        df["label"] = "" # 빈 라벨 열 추가
        
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"🎉 파일 생성 완료: {output_file}")
    else:
        print("❌ 조건에 맞는 데이터가 존재하지 않습니다.")

if __name__ == "__main__":
    # ★ 이름 오타 수정 완료: 정의된 함수명과 실행 함수명을 일치시킴
    extract_norway_chats()