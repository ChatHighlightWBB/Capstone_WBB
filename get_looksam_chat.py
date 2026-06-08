import requests
import pandas as pd
import time

def extract_all_looksam_chats():
    """
    [설명] 6월 데이터셋 고도화 스프린트: 전구간 순수 채팅 수집 엔진
    치지직 VOD API의 실제 데이터 키 규격인 'videoChats'를 매핑하여 수집 실패 버그를 해결한 버전입니다.
    """
    video_id = "13545456"
    
    # [팩트체크] 개발자 도구에서 가로챈 최초 시작 시간 (2초 = 2000ms)
    current_time_ms = 2000  
    
    pure_records = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    print(f"🚀 치지직 VOD [{video_id}] 전구간 순수 채팅 수집 가동...")

    while True:
        # 네이버 오리지널 통신 규격에 맞춰 playerMessageTime 파라미터를 동적으로 변경하며 호출
        target_url = f"https://api.chzzk.naver.com/service/v1/videos/{video_id}/chats?playerMessageTime={current_time_ms}&previousVideoChatSize=50"
        
        try:
            response = requests.get(target_url, headers=headers, timeout=5)
            if response.status_code != 200:
                print(f"❌ 네이버 서버 통신 실패 (HTTP 에러 코드: {response.status_code})")
                break
                
            res_json = response.json()
            content = res_json.get("content", {})
            
            # [버그 수정] messageList를 치지직 실제 규격인 videoChats로 변경합니다.
            chat_list = content.get("videoChats", [])
            
            # 추출된 채팅 오브젝트 내부에서 시간과 내용만 필터링하여 배열에 누적
            for chat in chat_list:
                pure_records.append({
                    "time_ms": chat.get("messageTime"),      # 채팅 발생 절대 시간(ms)
                    "chat_message": chat.get("content")     # 채팅 내용 텍스트
                })
            
            # 채팅이 적재되었을 때만 터미널에 수집 현황 출력
            if chat_list:
                print(f"🔄 재생시간 {current_time_ms // 1000}초 구역 통과 중... (현재 누적: {len(pure_records)}줄)")
            
            # 다음 탐색 시간 포인터 갱신용 변수 확보
            next_time = content.get("nextPlayerMessageTime")
            
            # 네이버 API 종료 시그널(-1)을 만나거나 더 이상 전진할 주소가 없으면 종료
            if next_time is None or next_time == -1 or next_time == current_time_ms:
                # 단, 공백 구간이라 잠시 데이터가 없는 것인지 완전히 끝난 것인지 배열 유무로 2차 검증
                if not chat_list:
                    print("🏁 VOD의 맨 마지막 구역까지 수집이 완료되어 엔진을 중지합니다.")
                    break
            
            # 다음 루프를 위해 시간축 인덱스 변수 스위칭
            current_time_ms = next_time
            
            # 과도한 연속 호출로 인한 네이버 방화벽 차단(DDoS)을 방지하는 안전 슬립
            time.sleep(0.3)
            
        except Exception as e:
            print(f"❌ 크롤링 중 예외 에러 발생: {str(e)}")
            break

    # monster_rat_chats.csv와 동일한 2개 열 규격으로 최종 파일 출력
    if pure_records:
        df = pd.DataFrame(pure_records)
        output_filename = "looksam_chats.csv"
        
        # 엑셀 깨짐을 방지하는 utf-8-sig 인코딩 형식 지정 저장
        df.to_csv(output_filename, index=False, encoding="utf-8-sig")
        print(f"\n🎉 [추출 완료] 최상위 경로에 '{output_filename}' 파일 생성이 완료되었습니다.")
        print(f"📊 최종 확보된 대용량 원본 데이터 규모: {len(df)} 줄")
    else:
        print("❌ 데이터가 하나도 적재되지 않았습니다. 초기 파라미터 설정을 재확인하세요.")

if __name__ == "__main__":
    extract_all_looksam_chats()