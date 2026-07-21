import csv
import random

# 파일 설정
OUTPUT_CSV = "wbb_labeling_work_gpt_horror.csv"
TARGET_COUNT = 2000

# 01:17:14 시작 타임스탬프 (밀리초 변환)
START_TIME_MS = ((1 * 3600) + (17 * 60) + 14) * 1000

# 공포게임 방송 특화 채팅 샘플 풀
chat_pool = [
    "깜짝이야 ㄷㄷ",
    "ㅋㅋㅋㅋㅋ",
    "소리 좀 줄여봐",
    "어두워서 아무것도 안 보임",
    "갑툭튀 뭔데 미쳤네",
    "으악 ㅋㅋㅋㅋ",
    "여기 오른쪽 문 열어보셈",
    "지피티 쫄았죠?",
    "또 도망가네 ㅋㅋㅋ",
    "아 식겁했네",
    "열쇠 어디 있음?",
    "여긴 무조건 귀신 나온다",
    "레전드 ㅋㅋㅋㅋ",
    "불쌍하다 진짜",
    "답답해서 내가 한다",
    "소름 돋았어",
    "111111",
    "???",
    "와 미쳤다",
    "도망쳐 빨리!!",
]


def generate_horror_labeling_csv():
  rows = []
  current_time = START_TIME_MS

  for i in range(TARGET_COUNT):
    # 채팅 발생 간격을 1초 ~ 3초 사이로 랜덤 증가시켜 시계열 분산
    current_time += random.randint(1000, 3000)
    msg = random.choice(chat_pool)
    # [time_ms, chat_message, label(빈값)]
    rows.append([current_time, msg, ""])

  # CSV 저장 (utf-8-sig 인코딩으로 한글 깨짐 방지)
  header = ["time_ms", "chat_message", "label"]
  with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

  print(
      f"✔ 라벨링용 CSV 파일 생성 완료: {OUTPUT_CSV} (총 {len(rows)}줄,"
      f" 시작시간: {START_TIME_MS}ms)"
  )


if __name__ == "__main__":
  generate_horror_labeling_csv()