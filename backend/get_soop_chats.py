import time
import pandas as pd
import requests
import xml.etree.ElementTree as ET

def extract_soop_chats():
    """
    [설명] 와바바(WBB) 프로젝트 SOOP TV VOD 채팅 중복 방지 수집 엔진
    <chat> 부모 노드 기반 파싱 및 중복 검사(Set)를 통해 
    1시간 17분(4620초) 이후 순수 시청자 채팅 2,000줄을 수집합니다.
    """
    video_id = "202059681"
    output_file = "wbb_labeling_work_soop.csv"

    # F12 Network 탭에서 추출한 rowKey
    ROW_KEY = "20260720_0744473D_295715391_5_c"
    
    # 수집 시작 시간 (1시간 17분 = 4620.0초)
    current_start_time = 4620.0 
    target_count = 2000
    
    raw_records = []
    seen_records = set()  # 중복 채팅 검출용 집합(Set)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    })

    print(f"🚀 [와바바 수집 엔진] SOOP TV 영상({video_id}) 1시간 17분({current_start_time}초) 지점 수집 가동...")

    api_url = "https://videoimg.sooplive.com/php/ChatLoadSplit.php"

    # 채팅 반복 수집 파이프라인
    while len(raw_records) < target_count:
        params = {
            "rowKey": ROW_KEY,
            "startTime": str(current_start_time)
        }

        try:
            res = session.get(api_url, params=params, timeout=10)
            
            if res.status_code != 200:
                print(f"❌ API 통신 실패 (HTTP 코드: {res.status_code})")
                break

            root = ET.fromstring(res.text)
            
            # [수정] <m> 대신 부모 태그인 <chat>을 가져옵니다.
            chats = root.findall('.//chat')

            if not chats:
                print("🏁 더 이상 불러올 채팅이 없어 수집을 종료합니다.")
                break

            max_time_in_batch = current_start_time

            for chat_node in chats:
                # <chat> 부모 안에서 <m>(메시지)과 <t>(시간) 자식 노드를 각각 추출
                msg_node = chat_node.find('m')
                time_node = chat_node.find('t')

                msg_text = msg_node.text.strip() if (msg_node is not None and msg_node.text) else ""
                chat_time_sec = float(time_node.text) if (time_node is not None and time_node.text) else current_start_time
                
                # 와바바 데이터셋 규격(ms) 변환
                chat_time_ms = int(chat_time_sec * 1000)

                # 배치 내 가장 늦은 작성 시간 기록
                if chat_time_sec > max_time_in_batch:
                    max_time_in_batch = chat_time_sec

                # (시간, 채팅내용) 조합으로 중복 여부 판별
                record_key = (chat_time_ms, msg_text)

                if msg_text and (record_key not in seen_records):
                    seen_records.add(record_key)
                    raw_records.append({
                        "time_ms": chat_time_ms,
                        "chat_message": msg_text,
                    })
                
                if len(raw_records) >= target_count:
                    break

            if len(raw_records) >= target_count:
                break

            # 진행 상황 출력
            if raw_records:
                last_time_ms = raw_records[-1]["time_ms"]
                current_min = last_time_ms // 60000
                current_sec = (last_time_ms % 60000) // 1000
                print(f"🔄 재생시간 {current_min}분 {current_sec}초 통과 중... (누적: {len(raw_records)}/{target_count} 줄)")

            # [시간 갱신] 배치에서 가장 높은 시간을 다음 startTime으로 지정
            if max_time_in_batch <= current_start_time:
                current_start_time += 1.0
            else:
                current_start_time = max_time_in_batch + 0.001

            time.sleep(0.2)  # API 차단 방지 인터벌

        except ET.ParseError:
            print("❌ XML 파싱 에러: 응답 형식이 올바르지 않습니다.")
            break
        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {str(e)}")
            break

    # CSV 디스크 저장 (Pandas + utf-8-sig)
    if raw_records:
        df = pd.DataFrame(raw_records).head(target_count)
        df["label"] = ""  # 라벨링용 빈 열 생성

        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n🎯 목표 하이라이트 {len(df)}줄 수집 완료! 중복 없는 파일 생성: {output_file}")
    else:
        print("❌ 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    extract_soop_chats()