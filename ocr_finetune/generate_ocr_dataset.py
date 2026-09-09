"""
=============================================================================
[와바바(WBB)] PP-OCRv3 채팅창 인식 파인튜닝용 합성 데이터셋 생성기
- 제안서 WBS 2.2.1 "다양한 스트리밍 폰트 및 배경 노이즈가 포함된
  채팅창 합성 데이터셋 구축" 에 해당하는 구현입니다.

[동작 방식]
1) 실제 방송 영상에서 프레임을 뽑아 '배경'으로 사용합니다.
   (실제 게임 화면/반투명 채팅창 위에 글자가 얹히는 상황을 그대로 재현)
2) 채팅 어휘 목록에서 문구를 뽑아 랜덤 폰트/크기/색상으로 렌더링합니다.
3) PP-OCR recognition 학습 포맷(크롭된 한 줄 이미지 + 정답 텍스트)으로 저장합니다.

[중요] PP-OCR의 인식(recognition) 모델은 '이미 잘려진 한 줄짜리 텍스트 이미지'를
입력으로 받습니다. 그래서 전체 화면이 아니라 채팅 한 줄 크기로 크롭된
이미지를 생성해야 합니다. 이 스크립트는 그 포맷을 따릅니다.

출력 구조:
  output_dir/
    ├── train/            (이미지들)
    ├── val/
    ├── train_label.txt   ("train/0001.jpg\t안녕하세요" 형식, 탭 구분)
    └── val_label.txt
=============================================================================
"""

import os
import random
import argparse

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 스트리밍 채팅창에서 흔히 보이는 텍스트 색상들
# (닉네임은 컬러, 본문은 흰색/회색인 경우가 많음)
TEXT_COLORS = [
    (255, 255, 255), (240, 240, 240), (220, 220, 220),
    (255, 220, 120), (130, 220, 255), (180, 255, 180),
    (255, 170, 200), (200, 180, 255), (255, 200, 150),
]

DEFAULT_VOCAB = [
    "ㅋㅋㅋㅋㅋㅋ", "ㅋㅋㅋㅋ", "ㅋㅋ", "ㅠㅠ", "ㅜㅜ", "ㄷㄷ", "ㅇㅈ", "ㄹㅇ",
    "대박", "와 미쳤다", "레전드", "지금 뭐임?", "개웃기네", "아니 왜저래",
    "나이스", "굿굿", "폼 미쳤다", "캐리 감사합니다", "형 잘한다",
    "에휴 답답하네", "노답이다 진짜", "트롤인데?", "발컨 ㅋㅋ",
    "헐 뭐야", "소름", "무서워", "심장 떨어질뻔", "깜짝이야",
    "ㅇㅇ", "ㄱㄱ", "ㅈㄴ 잘하네", "실화냐", "이걸 이김?", "역시 갓",
    "안녕하세요", "방금 들어왔어요", "오늘 방송 언제까지 해요?",
    "구독하고 갑니다", "형 목소리 좋다", "화이팅!!", "다시보기 올려주세요",
]


def load_fonts(font_dir):
    """폰트 디렉토리에서 .ttf/.otf/.ttc 파일을 모두 수집"""
    exts = (".ttf", ".otf", ".ttc", ".TTF", ".OTF", ".TTC")
    fonts = []
    if os.path.isdir(font_dir):
        for f in sorted(os.listdir(font_dir)):
            if f.endswith(exts):
                fonts.append(os.path.join(font_dir, f))
    if not fonts:
        # fonts/ 폴더가 비어있으면 시스템에 설치된 한국어 지원 폰트로 폴백
        fallbacks = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
            "C:/Windows/Fonts/malgun.ttf",
            "C:/Windows/Fonts/malgunbd.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        ]
        fonts = [p for p in fallbacks if os.path.exists(p)]
    return fonts


def load_vocab(vocab_path):
    """채팅 어휘 목록 로드. 파일이 없으면 내장 기본 어휘 사용."""
    if vocab_path and os.path.exists(vocab_path):
        with open(vocab_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if lines:
            print(f"[어휘] {vocab_path} 에서 {len(lines)}개 문구 로드")
            return lines
    print(f"[어휘] 사용자 어휘 파일이 없어 내장 기본 어휘 {len(DEFAULT_VOCAB)}개를 사용합니다.")
    return DEFAULT_VOCAB


def extract_background_patches(video_path, num_frames, patch_h_range=(28, 56)):
    """
    실제 영상에서 프레임을 뽑아, 채팅 한 줄 크기의 배경 패치를 만듭니다.
    영상이 없으면 단색/그라데이션 합성 배경으로 폴백합니다.
    """
    patches = []
    if video_path and os.path.exists(video_path):
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total > 0:
            idxs = np.linspace(0, max(total - 1, 0), min(num_frames, max(total, 1))).astype(int)
            for i in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
                ret, frame = cap.read()
                if ret:
                    patches.append(frame)
        cap.release()
        print(f"[배경] 영상에서 {len(patches)}개 프레임 추출")

    if not patches:
        print("[배경] 영상이 없어 합성 배경(어두운 반투명 채팅창 느낌)을 사용합니다.")
        for _ in range(30):
            base = random.randint(10, 70)
            img = np.full((360, 640, 3), base, dtype=np.uint8)
            noise = np.random.randint(-12, 12, img.shape, dtype=np.int16)
            img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            patches.append(img)
    return patches


def render_sample(text, bg_frame, fonts, out_path):
    """배경 프레임 위에 텍스트를 한 줄 렌더링하고 그 영역만 크롭해 저장"""
    font_path = random.choice(fonts)
    font_size = random.randint(18, 34)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    # 텍스트 크기 측정
    tmp = Image.new("RGB", (10, 10))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if tw <= 0 or th <= 0:
        return False

    pad_x, pad_y = random.randint(6, 16), random.randint(4, 10)
    canvas_w, canvas_h = tw + pad_x * 2, th + pad_y * 2

    # 배경에서 해당 크기만큼 랜덤 위치로 잘라오기
    bh, bw = bg_frame.shape[:2]
    if bw < canvas_w or bh < canvas_h:
        bg_frame = cv2.resize(bg_frame, (max(bw, canvas_w + 10), max(bh, canvas_h + 10)))
        bh, bw = bg_frame.shape[:2]
    x0 = random.randint(0, bw - canvas_w)
    y0 = random.randint(0, bh - canvas_h)
    patch = bg_frame[y0:y0 + canvas_h, x0:x0 + canvas_w].copy()

    pil = Image.fromarray(cv2.cvtColor(patch, cv2.COLOR_BGR2RGB))

    # 채팅창 반투명 오버레이 재현 (약 60% 확률)
    if random.random() < 0.6:
        overlay = Image.new("RGBA", pil.size, (0, 0, 0, random.randint(60, 150)))
        pil = Image.alpha_composite(pil.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(pil)
    color = random.choice(TEXT_COLORS)

    # 스트리밍 채팅은 가독성을 위해 외곽선(stroke)을 넣는 경우가 많음
    stroke_w = random.choice([0, 0, 1, 2])
    draw.text((pad_x, pad_y), text, font=font, fill=color,
              stroke_width=stroke_w, stroke_fill=(0, 0, 0))

    img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    # --- 현실적인 열화(degradation) 적용 ---
    if random.random() < 0.4:  # 블러
        k = random.choice([3, 3, 5])
        img = cv2.GaussianBlur(img, (k, k), 0)
    if random.random() < 0.3:  # 센서/압축 노이즈
        noise = np.random.normal(0, random.uniform(3, 10), img.shape)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if random.random() < 0.5:  # JPEG 압축 아티팩트
        q = random.randint(35, 80)
        _, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    if random.random() < 0.3:  # 저해상도 스트림 재현 (축소 후 확대)
        s = random.uniform(0.5, 0.8)
        small = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        img = cv2.resize(small, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_CUBIC)

    cv2.imwrite(out_path, img)
    return True


def main():
    ap = argparse.ArgumentParser(description="PP-OCRv3 채팅 인식 파인튜닝용 합성 데이터셋 생성기")
    ap.add_argument("--video", default=None, help="배경으로 쓸 실제 방송 영상 경로 (권장)")
    ap.add_argument("--fonts", default="./fonts", help="폰트(.ttf/.otf) 폴더")
    ap.add_argument("--vocab", default="./vocab/chat_vocab.txt", help="채팅 문구 목록 txt (한 줄에 하나)")
    ap.add_argument("--out", default="./ocr_dataset", help="출력 폴더")
    ap.add_argument("--num", type=int, default=5000, help="생성할 총 샘플 수")
    ap.add_argument("--val-ratio", type=float, default=0.1, help="검증셋 비율")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    fonts = load_fonts(args.fonts)
    if not fonts:
        print("❌ 사용 가능한 폰트가 없습니다. --fonts 폴더에 .ttf 파일을 넣어주세요.")
        return
    print(f"[폰트] {len(fonts)}개 사용: {[os.path.basename(f) for f in fonts]}")

    vocab = load_vocab(args.vocab)
    backgrounds = extract_background_patches(args.video, num_frames=200)

    train_dir = os.path.join(args.out, "train")
    val_dir = os.path.join(args.out, "val")
    os.makedirs(train_dir, exist_ok=True)
    os.makedirs(val_dir, exist_ok=True)

    n_val = int(args.num * args.val_ratio)
    train_labels, val_labels = [], []

    made = 0
    attempt = 0
    while made < args.num and attempt < args.num * 3:
        attempt += 1
        text = random.choice(vocab)

        # 두 문구를 붙여 긴 채팅도 재현 (20% 확률)
        if random.random() < 0.2:
            text = text + " " + random.choice(vocab)

        is_val = made < n_val
        split_dir = val_dir if is_val else train_dir
        split_name = "val" if is_val else "train"
        fname = f"{made:06d}.jpg"
        out_path = os.path.join(split_dir, fname)

        bg = random.choice(backgrounds)
        if render_sample(text, bg, fonts, out_path):
            line = f"{split_name}/{fname}\t{text}"
            (val_labels if is_val else train_labels).append(line)
            made += 1
            if made % 500 == 0:
                print(f"  ... {made}/{args.num} 생성")

    with open(os.path.join(args.out, "train_label.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(train_labels) + "\n")
    with open(os.path.join(args.out, "val_label.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(val_labels) + "\n")

    print("\n" + "=" * 60)
    print(f"✅ 완료: 학습 {len(train_labels)}장 / 검증 {len(val_labels)}장")
    print(f"   출력 위치: {os.path.abspath(args.out)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
