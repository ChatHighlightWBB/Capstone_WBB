import time
import re
import pandas as pd
import requests

def extract_youtube_chats():
    """
    [설명] 와바바(WBB) 프로젝트 유튜브 3분(180,000ms) 이후 채팅 2,000줄 수집 엔진
    브라우저에서 직접 추출한 Continuation 토큰을 하드코딩하여 
    유튜브의 HTML 파싱 방어를 100% 우회하여 수집합니다.
    """
    video_id = "tn06UEILMlk"
    output_file = "wbb_labeling_work_youtube.csv"

    # 전달해주신 토큰을 변수에 직접 할당 (안전장치 제거 완료)
    MANUAL_CONTINUATION_TOKEN = "op2w0wSMARp2Q2lrcUp3b1lWVU5LYnpaSE1YVXdaVjh0ZDFNdFNsRnVNMVF0ZWtWM0VndDBiakEyVlVWc1RFMUpheG9sNnFqZHVRRWZDZ3QwYmpBMlZVVnNURTFKYTBvUU1HZGpTa05SV1VKWlIyTnNSMTh4YXlBQk1BQSUzREABWgQQ8IoMcggIBBgCIAAoAHgB"

    # 3분(180초)을 밀리초(ms)로 환산
    start_time_ms = 3 * 60 * 1000
    target_count = 2000
    raw_records = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })

    print(f"🚀 [와바바 수집 엔진] 유튜브 영상({video_id}) 동적 키 추출 및 수집 시작...")

    # 1. 메인 페이지에서 API Key 및 Client Version 추출
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    res_watch = session.get(watch_url)

    if res_watch.status_code != 200:
        print(f"❌ 웹페이지 접속 실패 (HTTP 코드: {res_watch.status_code})")
        return

    html_watch = res_watch.text
    key_match = re.search(r'"INNERTUBE_API_KEY":\s*"([^"]+)"', html_watch)
    version_match = re.search(r'"INNERTUBE_CLIENT_VERSION":\s*"([^"]+)"', html_watch)

    if not key_match or not version_match:
        print("❌ INNERTUBE_API_KEY 또는 CLIENT_VERSION 추출 실패.")
        return

    api_key = key_match.group(1)
    client_version = version_match.group(1)

    print(f"🔑 동적 API Key 추출 성공: {api_key[:10]}...")
    print(f"📌 Client Version 추출 성공: {client_version}")
    print("✅ 입력된 수동 Continuation 토큰 적용 완료. API 수집을 개시합니다.")

    # 2. InnerTube API 연동 및 설정
    chat_api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat_replay?key={api_key}"
    api_headers = {
        "Content-Type": "application/json",
        "X-YouTube-Client-Name": "1",
        "X-YouTube-Client-Version": client_version,
    }

    # 브라우저에서 가져온 첫 토큰으로 시작
    current_token = MANUAL_CONTINUATION_TOKEN

    # 3. 채팅 API 반복 수집 루프
    while current_token and len(raw_records) < target_count:
        chat_payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": client_version,
                    "hl": "ko",
                    "gl": "KR",
                }
            },
            "continuation": current_token,
        }

        try:
            chat_res = session.post(chat_api_url, json=chat_payload, headers=api_headers, timeout=10)
            
            if chat_res.status_code != 200:
                print(f"❌ API 통신 실패 (HTTP: {chat_res.status_code}) - 토큰이 만료되었거나 잘못되었습니다.")
                break

            chat_json = chat_res.json()
            actions = chat_json.get("continuationContents", {}).get("liveChatContinuation", {}).get("actions", [])

            if not actions:
                print("🏁 더 이상 불러올 채팅이 없어 수집을 종료합니다.")
                break

            for act in actions:
                replay_act = act.get("replayChatItemAction", {})
                chat_offset_ms = int(replay_act.get("videoOffsetTimeMsec", 0))

                # 3분(180,000ms) 이전 채팅은 통과
                if chat_offset_ms < start_time_ms:
                    continue

                for item_act in replay_act.get("actions", []):
                    text_renderer = item_act.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer")

                    if text_renderer:
                        runs = text_renderer.get("message", {}).get("runs", [])
                        msg = "".join([r.get("text", "") for r in runs]).strip()

                        if msg:
                            raw_records.append({
                                "time_ms": chat_offset_ms,
                                "chat_message": str(msg),
                            })
                        
                        if len(raw_records) >= target_count:
                            break
                
                if len(raw_records) >= target_count:
                    break

            # 치지직 스크립트와 동일한 진행 현황 출력
            if raw_records:
                last_time_ms = raw_records[-1]["time_ms"]
                current_min = last_time_ms // 60000
                current_sec = (last_time_ms % 60000) // 1000
                print(f"🔄 재생시간 {current_min}분 {current_sec}초 통과 중... (누적: {len(raw_records)}/{target_count} 줄)")

            # JSON 응답에서 다음 뭉치의 continuation 토큰 갱신
            conts = chat_json.get("continuationContents", {}).get("liveChatContinuation", {}).get("continuations", [])
            if conts:
                current_token = conts[0].get("liveChatReplayContinuationData", {}).get("continuation")
            else:
                current_token = None
                break

            time.sleep(0.2) # 유튜브 API 차단 방지용 인터벌

        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {str(e)}")
            break

    # 4. CSV 파일 저장 (Pandas 활용)
    if raw_records:
        df = pd.DataFrame(raw_records).head(target_count)
        df["label"] = "" # 와바바 라벨링용 빈 열 추가

        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n🎯 목표 하이라이트 {len(df)}줄 수집 완료! 파일 생성: {output_file}")
    else:
        print("❌ 조건(3분 이후)에 맞는 데이터가 존재하지 않거나 토큰이 올바르지 않습니다.")


if __name__ == "__main__":
    extract_youtube_chats()