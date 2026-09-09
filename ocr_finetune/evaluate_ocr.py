"""
=============================================================================
[와바바(WBB)] OCR 인식률 검증 스크립트
- 제안서 WBS 2.2.2의 "인식률(Accuracy) 검증" 부분입니다.
- 파인튜닝 전/후 모델을 같은 검증셋으로 돌려 수치를 비교할 때 사용합니다.

측정 지표:
  - 정확 일치율(Exact Match): 문장 전체가 완전히 같은 비율
  - 문자 정확도(Character Accuracy): 편집거리 기반, 한 글자 단위 정확도
=============================================================================
"""

import os
import argparse

from paddleocr import PaddleOCR


def levenshtein(a: str, b: str) -> int:
    """두 문자열의 편집 거리"""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main():
    ap = argparse.ArgumentParser(description="OCR 인식률 검증")
    ap.add_argument("--dataset", default="./ocr_dataset")
    ap.add_argument("--label", default="val_label.txt")
    ap.add_argument("--rec-model-dir", default=None,
                    help="파인튜닝 모델 경로. 생략하면 기본 사전학습 모델로 측정(=베이스라인)")
    ap.add_argument("--rec-char-dict-path", default=None)
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()

    kwargs = dict(lang="korean", use_angle_cls=False, show_log=False)
    if args.rec_model_dir:
        kwargs["rec_model_dir"] = args.rec_model_dir
    if args.rec_char_dict_path:
        kwargs["rec_char_dict_path"] = args.rec_char_dict_path

    label_name = "파인튜닝 모델" if args.rec_model_dir else "베이스라인(사전학습)"
    print(f"[모델] {label_name} 로딩 중...")
    ocr = PaddleOCR(**kwargs)

    label_path = os.path.join(args.dataset, args.label)
    with open(label_path, "r", encoding="utf-8") as f:
        rows = [ln.rstrip("\n").split("\t") for ln in f if "\t" in ln]
    rows = rows[:args.limit]

    exact_hits = 0
    total_chars = 0
    total_edits = 0
    evaluated = 0

    for rel_path, truth in rows:
        img_path = os.path.join(args.dataset, rel_path)
        if not os.path.exists(img_path):
            continue

        try:
            result = ocr.ocr(img_path, cls=False)
        except Exception:
            continue

        pred = ""
        if result and result[0]:
            parts = []
            for line in result[0]:
                try:
                    parts.append(str(line[1][0]))
                except (IndexError, TypeError):
                    continue
            pred = " ".join(parts)

        pred_n = pred.replace(" ", "")
        truth_n = truth.replace(" ", "")

        if pred_n == truth_n:
            exact_hits += 1
        total_edits += levenshtein(pred_n, truth_n)
        total_chars += len(truth_n)
        evaluated += 1

    if evaluated == 0:
        print("❌ 평가할 샘플이 없습니다.")
        return

    exact = exact_hits / evaluated * 100
    char_acc = max(0.0, (1 - total_edits / max(total_chars, 1))) * 100

    print("\n" + "=" * 55)
    print(f" 검증 결과 — {label_name}")
    print("=" * 55)
    print(f" 평가 샘플 수      : {evaluated}")
    print(f" 정확 일치율       : {exact:.2f}%")
    print(f" 문자 단위 정확도  : {char_acc:.2f}%")
    print("=" * 55)


if __name__ == "__main__":
    main()
