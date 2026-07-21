import requests
import pandas as pd
import time

def extract_lol_stream_chats():
    """
    [설명] 롤 MSI T1 vs G2 VOD(14092142) 하이라이트 구간 무필터 수집 엔진
    4시간 17분 지점부터 연속된 시청자 채팅 데이터를 정확히 1,000줄 추출합니다.
    """
    video_id = "14092142"  # 스크린샷 주소창에서 확인한 롤 경기 고유 영상 ID
    output_file = "wbb_labeling_work_lol.csv"
    
    # [시간 계산] 요청하신 4시간 17분을 밀리초(ms) 단위 정수로 환산
    start_time_ms = (4 * 60 * 60 + 17 * 60) * 1000   # 15,420,000 ms
    
    current_time_ms = start_time_ms
    raw_records = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    print(f"🚀 롤 MSI VOD 구간 수집 가동: {start_time_ms}ms 지점(4시간 17분) 진입...")

    while True:
        # 네이버 API 규격에 맞춰 영상 재생 상대 시간(ms) 파라미터 전송
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
                print("🏁 해당 구간 뒤로 더 이상 데이터가 없어 종료합니다.")
                break
            
            for chat in chat_list:
                msg = chat.get("content")
                
                # 핵심 키워드 제한 없이 모든 순수 채팅 적재
                if msg:
                    raw_records.append({
                        "time_ms": chat.get("messageTime"), # 마스터 데이터셋 호환용 절대시간
                        "chat_message": str(msg)
                    })
                    
                # 요구사항인 1,000줄이 충족되면 루프 조기 탈출
                if len(raw_records) >= 1000:
                    break
            
            # 현재 수집 중인 경기 시/분/초 진행 현황 모니터링 출력
            if chat_list:
                last_p_time = chat_list[-1].get("playerMessageTime")
                current_hour = last_p_time // 3600000
                current_min = (last_p_time % 3600000) // 60000
                current_sec = (last_p_time % 60000) // 1000
                print(f"🔄 재생시간 {current_hour}시간 {current_min}분 {current_sec}초 통과 중... (누적: {len(raw_records)}/1000 줄)")
            
            # 1,000줄 달성 시 무한 루프 완전히 탈출
            if len(raw_records) >= 1000:
                print("\n🎯 목표 하이라이트 1,000줄 수집 완료!")
                break
                
            next_time = content.get("nextPlayerMessageTime")
            if next_time is None or next_time == -1 or next_time == current_time_ms:
                break
                
            current_time_ms = next_time
            time.sleep(0.2) # 네이버 디도스 차단 회피용 슬립 인터벌
            
        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {str(e)}")
            break

    # 파일 디스크 저장 제어
    if raw_records:
        df = pd.DataFrame(raw_records).head(1000)
        df["label"] = "" # 수동 감정 분류용 빈 열 할당
        
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"🎉 파일 생성 완료: {output_file}")
    else:
        print("❌ 데이터 적재에 실패했습니다. 코드를 재점검해야 합니다.")

if __name__ == "__main__":
    extract_lol_stream_chats()