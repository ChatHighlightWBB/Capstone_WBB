import re
import time
import pandas as pd
import requests


def extract_youtube_chats():
    """[설명] 와바바(WBB) 프로젝트 슈카 7월 14일 방송 VOD 수집 전용 엔진

    파일명: get_youtube_shuka2.py
    4분(240,000ms) 지점 이후 'ㅋㅋㅋㅋ', '헉', '???', '캬' 등의
    도배성 감탄사/노이즈 채팅을 필터링하여 유의미한 채팅 2,000줄을 수집합니다.
    """
    # 1. 수집 설정 및 파일명 지정
    output_file = "wbb_labeling_work_youtube2.csv"

    # 스크린샷에서 추출된 수동 Continuation 토큰 주입
    MANUAL_CONTINUATION_TOKEN = "op2w0wR0Gl5DaWtxSndvWVZVTktielpITVhVd1pWOHRkMU10U2xGdU0xUXRla1YzRWd0a1ZFVkxlWE0yVjNreFZSb1Q2cWpkdVFFTkNndGtWRVZMZVhNMlYza3hWU0FCTUFBJTNEQAFaBBCYyw5yCAgEGAIgACgAeAE%3D"

    # 4분(240초)을 밀리초(ms)로 환산: (4 * 60) * 1000 = 240,000 ms
    start_time_ms = 4 * 60 * 1000
    target_count = 2000

    # 제외할 노이즈 단어 리스트
    EXCLUDE_KEYWORDS = ["ㅋㅋㅋㅋ", "헉", "???", "캬"]

    raw_records = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    })

    print(
        f"🚀 [와바바 수집 엔진] 슈카 방송 4분({start_time_ms}ms) 지점 노이즈"
        " 필터링 수집 시작..."
    )

    # 2. 메인 watch 페이지 접속하여 API Key 및 Client Version 동적 파싱
    watch_url = "https://www.youtube.com/watch?v=tn06UEILMlk"
    res_watch = session.get(watch_url)

    if res_watch.status_code != 200:
        print(f"❌ 웹페이지 접속 실패 (HTTP 코드: {res_watch.status_code})")
        return

    html_watch = res_watch.text
    key_match = re.search(r'"INNERTUBE_API_KEY":\s*"([^"]+)"', html_watch)
    version_match = re.search(
        r'"INNERTUBE_CLIENT_VERSION":\s*"([^"]+)"', html_watch
    )

    if not key_match or not version_match:
        print("❌ INNERTUBE_API_KEY 또는 CLIENT_VERSION 추출 실패.")
        return

    api_key = key_match.group(1)
    client_version = version_match.group(1)

    print(f"🔑 동적 API Key 추출 성공: {api_key[:10]}...")
    print(f"📌 Client Version 추출 성공: {client_version}")

    # 3. InnerTube API 헤더 및 엔드포인트 세팅
    chat_api_url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat_replay?key={api_key}"
    api_headers = {
        "Content-Type": "application/json",
        "X-YouTube-Client-Name": "1",
        "X-YouTube-Client-Version": client_version,
    }

    current_token = MANUAL_CONTINUATION_TOKEN

    # 4. 채팅 API 수집 및 노이즈 필터링 순환 루프
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
            chat_res = session.post(
                chat_api_url,
                json=chat_payload,
                headers=api_headers,
                timeout=10,
            )

            if chat_res.status_code != 200:
                print(
                    f"❌ API 통신 실패 (HTTP: {chat_res.status_code}) - 토큰이"
                    " 만료되었거나 잘못되었습니다."
                )
                break

            chat_json = chat_res.json()
            actions = (
                chat_json.get("continuationContents", {})
                .get("liveChatContinuation", {})
                .get("actions", [])
            )

            if not actions:
                print("🏁 더 이상 불러올 채팅이 없어 수집을 종료합니다.")
                break

            for act in actions:
                replay_act = act.get("replayChatItemAction", {})
                chat_offset_ms = int(replay_act.get("videoOffsetTimeMsec", 0))

                # 4분(240,000ms) 이전 채팅은 통과
                if chat_offset_ms < start_time_ms:
                    continue

                for item_act in replay_act.get("actions", []):
                    text_renderer = (
                        item_act.get("addChatItemAction", {})
                        .get("item", {})
                        .get("liveChatTextMessageRenderer")
                    )

                    if text_renderer:
                        runs = text_renderer.get("message", {}).get("runs", [])
                        msg = "".join([r.get("text", "") for r in runs]).strip()

                        # 노이즈 단어 포함 여부 검사
                        is_excluded = False
                        for kw in EXCLUDE_KEYWORDS:
                            if kw in msg:
                                is_excluded = True
                                break

                        # 필터링을 통과한 유의미한 채팅만 저장
                        if msg and not is_excluded:
                            raw_records.append({
                                "time_ms": chat_offset_ms,
                                "chat_message": str(msg),
                            })

                        if len(raw_records) >= target_count:
                            break

                if len(raw_records) >= target_count:
                    break

            # 터미널 수집 현황 출력
            if raw_records:
                last_time_ms = raw_records[-1]["time_ms"]
                current_min = last_time_ms // 60000
                current_sec = (last_time_ms % 60000) // 1000
                print(
                    f"🔄 재생시간 {current_min}분 {current_sec}초 통과 중..."
                    f" (필터링 적용 누적: {len(raw_records)}/{target_count} 줄)"
                )

            # 응답 내 다음 continuation 토큰으로 자동 갱신
            conts = (
                chat_json.get("continuationContents", {})
                .get("liveChatContinuation", {})
                .get("continuations", [])
            )
            if conts:
                current_token = conts[0].get(
                    "liveChatReplayContinuationData", {}
                ).get("continuation")
            else:
                current_token = None
                break

            time.sleep(0.2)  # 서버 차단 방지 인터벌

        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {str(e)}")
            break

    # 5. CSV 저장 (Pandas + utf-8-sig)
    if raw_records:
        df = pd.DataFrame(raw_records).head(target_count)
        df["label"] = ""  # 라벨링용 빈 열 생성

        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(
            f"\n🎯 목표 정제 데이터 {len(df)}줄 수집 완료! 파일 생성:"
            f" {output_file}"
        )
    else:
        print(
            "❌ 조건(4분 이후 및 필터링)에 맞는 데이터가 존재하지 않거나 토큰이"
            " 올바르지 않습니다."
        )


if __name__ == "__main__":
    extract_youtube_chats()