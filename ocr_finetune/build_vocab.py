"""
=============================================================================
[와바바(WBB)] OCR 합성 데이터셋용 채팅 어휘 파일 생성기
- generate_ocr_dataset.py 가 사용할 vocab/chat_vocab.txt 를 만듭니다.

[왜 별도 스크립트가 필요한가]
OCR 인식 모델의 사전(dict)은 '어휘 파일에 등장한 문자'만으로 구성됩니다.
사전에 없는 글자는 화면에 아무리 선명해도 모델이 출력 자체를 할 수 없습니다.
그래서 어휘 파일은 단순히 문장을 많이 모으는 게 아니라,
'한글 문자를 얼마나 폭넓게 덮는가'를 확인하면서 만들어야 합니다.

[권장 소스 조합]
1. extracted_ocr_chats.csv  → 실제 방송 채팅 (도메인 일치도 최상)
2. AI Hub 감성 대화 말뭉치   → 한글 문자 커버리지 확보용
3. 내장 스트리밍 슬랭 목록   → ㅋㅋㅋ, ㄷㄷ 등 비정형 자음 보강

사용 예:
  python build_vocab.py \\
      --csv extracted_ocr_chats.csv:chat_text \\
      --csv aihub_emotion.csv:sentence \\
      --out vocab/chat_vocab.txt
=============================================================================
"""

import os
import re
import csv
import random
import argparse
from collections import Counter

# 스트리밍 채팅 특유의 비정형 표현. AI Hub 같은 정제된 말뭉치에는
# 거의 없기 때문에 별도로 섞어줘야 합니다.
STREAMING_SLANG = [
    "ㅋㅋ", "ㅋㅋㅋ", "ㅋㅋㅋㅋ", "ㅋㅋㅋㅋㅋㅋ", "ㅋㅋㅋㅋㅋㅋㅋㅋ",
    "ㅠㅠ", "ㅠㅠㅠ", "ㅜㅜ", "ㄷㄷ", "ㄷㄷㄷ", "ㅇㅈ", "ㄹㅇ", "ㅇㅇ",
    "ㄱㄱ", "ㅅㄱ", "ㅎㅇ", "ㅂㅂ", "ㅡㅡ", "ㅗ", "ㄴㄴ",
    "레전드", "대박", "미쳤다", "지렸다", "갓", "폼 미쳤다", "캐리",
    "나이스", "굿굿", "개웃기네", "실화냐", "이걸 이김?", "소름",
    "에휴", "노답", "발컨", "트롤", "답답하네", "극혐", "뇌절",
    "헐", "깜짝이야", "무서워", "심장 떨어질뻔", "와 미쳤다",
    "구독하고 갑니다", "다시보기 올려주세요", "방금 들어왔어요",
    "형 잘한다", "오늘 방송 언제까지 해요?", "화이팅",
]

# 채팅 한 줄로 보기엔 너무 길거나 짧은 것 제외
MIN_LEN = 1
MAX_LEN = 40


def clean_line(text: str) -> str:
    """줄바꿈/중복 공백 정리. 원본 표기는 최대한 보존합니다."""
    t = str(text).replace("\n", " ").replace("\t", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def hangul_chars(text: str) -> set:
    """완성형 한글 + 자모만 추출"""
    return {c for c in text if "\uac00" <= c <= "\ud7a3" or "\u3131" <= c <= "\u318e"}


def load_csv_column(spec: str) -> list:
    """'파일경로:컬럼명' 형식을 받아 해당 컬럼 값을 리스트로 반환"""
    if ":" in spec:
        path, col = spec.rsplit(":", 1)
    else:
        path, col = spec, None

    if not os.path.exists(path):
        print(f"  ⚠️ 파일 없음, 건너뜀: {path}")
        return []

    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if col and reader.fieldnames and col not in reader.fieldnames:
            print(f"  ⚠️ '{col}' 컬럼 없음 (있는 컬럼: {reader.fieldnames}), 건너뜀")
            return []
        for r in reader:
            val = r.get(col) if col else next(iter(r.values()), "")
            if val:
                rows.append(val)
    print(f"  ✔ {path} [{col}] → {len(rows)}줄")
    return rows


def load_txt(path: str) -> list:
    if not os.path.exists(path):
        print(f"  ⚠️ 파일 없음, 건너뜀: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln for ln in f]
    print(f"  ✔ {path} → {len(lines)}줄")
    return lines


def main():
    ap = argparse.ArgumentParser(description="OCR 합성용 채팅 어휘 파일 생성기")
    ap.add_argument("--csv", action="append", default=[],
                    help="'경로:컬럼명' 형식. 여러 번 지정 가능")
    ap.add_argument("--txt", action="append", default=[],
                    help="한 줄에 문구 하나인 txt. 여러 번 지정 가능")
    ap.add_argument("--out", default="vocab/chat_vocab.txt")
    ap.add_argument("--max-lines", type=int, default=20000,
                    help="최종 어휘 최대 줄 수 (너무 크면 생성 시간만 늘어남)")
    ap.add_argument("--no-slang", action="store_true",
                    help="내장 스트리밍 슬랭을 섞지 않음")
    ap.add_argument("--slang-ratio", type=float, default=0.15,
                    help="최종 어휘 중 슬랭이 차지할 비율")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)

    print("[1] 소스 수집")
    raw = []
    for spec in args.csv:
        raw += load_csv_column(spec)
    for path in args.txt:
        raw += load_txt(path)

    if not raw:
        print("  (외부 소스 없음 — 내장 슬랭만으로 생성합니다)")

    print("\n[2] 정제 및 중복 제거")
    seen = set()
    cleaned = []
    for line in raw:
        t = clean_line(line)
        if not (MIN_LEN <= len(t) <= MAX_LEN):
            continue
        # 한글이 하나도 없는 줄(숫자/영문 URL 등)은 제외
        if not hangul_chars(t):
            continue
        if t in seen:
            continue
        seen.add(t)
        cleaned.append(t)
    print(f"  정제 후 고유 문구: {len(cleaned)}개")

    print("\n[3] 스트리밍 슬랭 보강")
    if args.no_slang:
        print("  건너뜀(--no-slang)")
        final = cleaned
    else:
        # 슬랭이 목표 비율만큼 차지하도록 반복 삽입
        target_slang = int(len(cleaned) * args.slang_ratio / (1 - args.slang_ratio)) if cleaned else len(STREAMING_SLANG) * 5
        slang_pool = []
        while len(slang_pool) < max(target_slang, len(STREAMING_SLANG)):
            slang_pool += STREAMING_SLANG
        slang_pool = slang_pool[:max(target_slang, len(STREAMING_SLANG))]
        final = cleaned + slang_pool
        print(f"  슬랭 {len(slang_pool)}줄 추가 (목표 비율 {args.slang_ratio:.0%})")

    random.shuffle(final)
    if len(final) > args.max_lines:
        final = final[:args.max_lines]
        print(f"  최대 줄 수 제한 적용 → {args.max_lines}줄")

    print("\n[4] 문자 커버리지 분석")
    all_chars = set()
    for t in final:
        all_chars |= hangul_chars(t)

    counter = Counter()
    for t in final:
        counter.update(hangul_chars(t))

    # 딱 1~2번만 등장하는 글자는 모델이 제대로 못 배웁니다.
    rare = [c for c, n in counter.items() if n <= 2]

    print(f"  총 문구 수        : {len(final)}")
    print(f"  고유 한글 문자 수 : {len(all_chars)}")
    print(f"  희소 문자(≤2회)   : {len(rare)}개")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(final) + "\n")

    print("\n" + "=" * 60)
    print(f"✅ 저장 완료: {os.path.abspath(args.out)}")
    print("=" * 60)

    if len(all_chars) < 500:
        print("\n⚠️ 고유 한글 문자가 500자 미만입니다.")
        print("   실제 방송에서 사전에 없는 글자가 나오면 인식 자체가 불가능합니다.")
        print("   AI Hub 감성 대화 말뭉치 같은 큰 코퍼스를 --csv 로 추가하세요.")
    if rare and len(rare) > len(all_chars) * 0.3:
        print(f"\n⚠️ 희소 문자 비율이 높습니다 ({len(rare)}/{len(all_chars)}).")
        print("   해당 글자들은 학습이 잘 안 될 수 있으니 어휘를 더 늘리는 걸 권장합니다.")


if __name__ == "__main__":
    main()
