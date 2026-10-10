"""
=============================================================================
[와바바(WBB)] 1단계: PaddleOCR 텍스트 밀도 기반 Auto-ROI 자동 채팅 추출기
- 담당: 송태섭(Auto-ROI 자동 탐지, Windows DLL 충돌 방지) +
        고유찬(PaddleOCR 3.x API 대응, 디버그 이미지 덤프)
- 두 브랜치(feature/ai-nlp, integration/e2e-working-v1)의 작업을 병합했습니다.
=============================================================================

[병합 시 판단 기준]
- PaddleOCR 초기화 파라미터: integration 브랜치 유지
  (use_gpu=False는 설치된 paddleocr 3.x에서 Unknown argument 에러를 내는
   구버전 파라미터라 제거했습니다. 오늘 실제로 이 에러를 겪고 고친 부분입니다.)
- OCR 호출 API: integration 브랜치의 predict() 유지
  (.ocr(img, cls=True)는 3.x에서 predict() got an unexpected keyword
   argument 'cls' 에러가 나서, 이미 predict()로 전환해 검증했습니다.)
- Auto-ROI 자동 탐지(detect_chat_roi): ai-nlp 브랜치에서 채택
  (crop_box를 영상마다 하드코딩하지 않고 자동으로 잡으려는 시도라 유용합니다.
   단, 여기도 내부 OCR 호출을 구버전 .ocr()에서 predict()로 바꿨습니다.)
- Windows DLL 충돌 방지(KMP_DUPLICATE_LIB_OK, torch 우선 import): ai-nlp에서 채택
  (PaddleOCR과 PyTorch를 함께 쓸 때 나는 WinError 127을 예방하는 코드라
   integration 브랜치에서 아직 안 겪었을 뿐 유효한 방어 코드입니다.)
- debug_dump_dir, "인식 0건이어도 CSV는 항상 새로 쓰기": integration 브랜치 유지
  (Auto-ROI가 엉뚱한 영역을 잡아도 눈으로 확인할 수 있어야 하므로 오히려
   자동 탐지를 쓸 때 더 필요한 안전장치입니다.)
"""

import os
import re
import platform
import statistics

# [oneDNN/PIR 호환성 문제 방지] 일부 Windows 환경에서 최신 det 모델을
# oneDNN 가속과 함께 쓸 때 "ConvertPirAttribute2RuntimeAttribute not
# support" 에러가 발생합니다. oneDNN을 꺼서 이 충돌을 피합니다.
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"

# [2026-09 갱신] 예전엔 둘 다 CPU 버전일 때, albumentations가 torch를 뒤늦게
# 불러오며 생기던 DLL 충돌(WinError 127)을 막으려고 여기서 torch를 미리
# import했습니다. 그런데 지금은 torch/paddle 둘 다 GPU 버전이라, 이 줄이
# 오히려 torch의 cuDNN을 먼저 메모리에 올려버려서, 뒤이어 PaddleOCR이 자기
# cuDNN을 부를 때 충돌(WinError 127: cudnn_cnn64_9.dll 프로시저를 찾을 수
# 없음)나는 원인이 됐습니다. highlight_pipeline.py가 OCR을 먼저 만들고
# Whisper/Demucs(torch)는 나중에 만들기 때문에, 여기서 torch를 미리 안
# 불러오는 게 맞습니다.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# [2026-10 수정] Paddle 추론 엔진(C++)은 Windows에서 한글 등 비ASCII 경로의
# 모델 파일을 못 엽니다 ("Cannot open file ...\.paddlex\...\inference.json").
# 사용자 폴더 이름이 한글이면(C:\Users\고유찬) 기본 캐시 경로 ~/.paddlex가
# 깨지므로, 그때는 ASCII 경로인 backend/models/paddlex_cache를 캐시로 씁니다.
if "PADDLE_PDX_CACHE_HOME" not in os.environ and not os.path.expanduser("~").isascii():
    os.environ["PADDLE_PDX_CACHE_HOME"] = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "models", "paddlex_cache"
    )

import cv2
import pandas as pd
import numpy as np
import logging

from paddleocr import PaddleOCR

# PaddleOCR 내부 로그 최소화
logging.getLogger("ppocr").setLevel(logging.ERROR)

# 채팅 텍스트로 보기 어려운 잡음성 특수문자 (Auto-ROI가 게임 UI 테두리 등을
# 잘못 잡았을 때 나오는 무의미한 기호를 걸러내기 위함)
NOISE_CHARS = set("+-=;_~`|")

# --------------------------------------------------------------------------
# [품질 필터] OCR이 뭉개진 자모/음절을 그럴듯한 문장처럼 이어붙이는 경우가
# 있어서, 사전 없이도 "2글자 이상 한글 단어가 충분히 섞여있는가"로
# 진짜 채팅과 잡음을 가려냅니다. 사용자가 실제로 겪은 5개 샘플로 검증한
# 임계값(0.5)입니다.
# --------------------------------------------------------------------------

# 단독으로 쓰여도 정상인 한 글자 단어/조사 (사전 없이 손으로 추린 화이트리스트)
_SINGLE_CHAR_WHITELIST = {
    "못", "안", "왜", "네", "예", "그", "저", "이", "참", "자", "야",
    "흠", "오", "와", "헐", "흥", "게", "좀", "또", "쫌", "헉", "칫",
}

# 채팅 특유의 자음/모음 반복 슬랭 (ㅋㅋㅋ, ㅠㅠ, ㄷㄷ 등) - 정상으로 취급
_SLANG_PATTERN = re.compile(r"^[ㅋㅎㅠㅜㄷㅗㅇㄴㄱ]{2,}$")

QUALITY_THRESHOLD = 0.5

# --------------------------------------------------------------------------
# [Auto-ROI v2 조절용 숫자] detect_chat_roi_v2 가 쓰는 값들입니다.
# 기존 detect_chat_roi 는 초반 2/5/10초만 보고 "글자가 많은 쪽(좌/중/우)"을
# 통째로 감싸서, 방송 제목·메뉴 같은 고정 글자나 잠깐 뜬 창을 채팅으로 잡는
# 일이 있었습니다. v2 는 영상 전체에서 장면을 고르게 뽑아 "방송 내내, 같은
# 왼쪽 끝 위치에서, 비슷한 크기의 글자가 여러 줄 붙어 나오는 곳"을 찾습니다.
# --------------------------------------------------------------------------
ROI_NUM_FRAMES = 20        # 영상 전체에서 고르게 뽑을 장면 수
ROI_START_SEC = 5.0        # 장면을 뽑기 시작할 시각(초)
ROI_END_GUARD_SEC = 5.0    # 영상 끝에서 이만큼 앞까지만 뽑는다 (끝 프레임 읽기 실패 방지)
ROI_FIXED_IOU = 0.5        # "위치가 거의 같다"고 볼 겹침 비율(IoU) 기준
ROI_FIXED_RATIO = 0.5      # 다른 장면 중 이 비율 이상에 같은 자리·같은 글자가 있으면 고정 UI 로 본다
ROI_XMIN_GAP = 0.03        # 묶음 첫 상자의 xmin 과 차이가 이 값 이내면 같은 묶음
ROI_TOP_GROUPS = 5         # 상자 수가 많은 묶음 몇 개를 후보로 검사할지
ROI_HEIGHT_LOW = 0.65      # 상자 높이가 (중간 높이 × 이 값)보다 작으면 뺀다
ROI_HEIGHT_HIGH = 1.35     # 상자 높이가 (중간 높이 × 이 값)보다 크면 뺀다
ROI_VGAP_RATIO = 1.5       # 위아래 상자 사이 빈칸이 (중간 높이 × 이 값)보다 크면 덩어리를 끊는다
ROI_ROW_SAME_RATIO = 0.5   # 세로 중심 차이가 (중간 높이 × 이 값) 이하면 같은 줄로 본다
ROI_BAND_GAP_RATIO = 2.0   # 최종 영역 계산 때 위아래 빈칸이 (중간 높이 × 이 값)보다 크면 띠를 끊는다
ROI_MARGIN_X = 0.02        # 최종 영역 가로 여백 (화면 너비 대비)
ROI_MARGIN_Y = 0.05        # 최종 영역 세로 여백 (화면 높이 대비). 맨 위 줄이 잘리지 않게 넉넉히
ROI_MIN_ROWS = 8           # 고른 묶음의 줄 수 합이 이보다 적으면 실패로 보고 기존 방식을 쓴다


def _is_valid_token(token: str):
    """토큰 하나가 '그럴듯한 한글 단어'인지 판단. 한글이 없으면 None(중립)."""
    hangul_len = len(re.findall(r"[가-힣]", token))
    if hangul_len >= 2:
        return True
    if token in _SINGLE_CHAR_WHITELIST:
        return True
    if _SLANG_PATTERN.match(token):
        return True
    if not re.search(r"[가-힣ㄱ-ㅎㅏ-ㅣ]", token):
        return None  # 숫자/기호만 있는 토큰은 판단에서 제외
    return False


def is_quality_korean_line(text: str, threshold: float = QUALITY_THRESHOLD) -> bool:
    """
    한 줄(공백으로 구분된 여러 토큰) 전체의 '단어다움' 비율을 계산해서,
    기준 이상이면 True(살림), 미만이면 False(잡음으로 판단해 버림)를 반환합니다.
    """
    tokens = text.split()
    judged = [_is_valid_token(t) for t in tokens]
    judged = [j for j in judged if j is not None]
    if not judged:
        return False  # 판단할 한글 토큰이 아예 없으면 잡음으로 취급
    return (sum(judged) / len(judged)) >= threshold


# --------------------------------------------------------------------------
# [Auto-ROI v2 도우미 함수] 상자는 모두 화면 비율(0~1) 좌표 (xmin, ymin, xmax, ymax) 입니다.
# --------------------------------------------------------------------------
def _roi_iou(a, b):
    """두 상자가 얼마나 겹치는지 0~1 로 계산합니다 (겹친 넓이 / 합친 넓이)."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _roi_sample_times(duration_sec, num_frames=ROI_NUM_FRAMES):
    """5초 ~ (영상 길이 - 5초) 사이에서 고르게 num_frames 개의 시각을 고릅니다.
    초반만 보면 방송 시작 화면(대기 화면, 바탕화면 등)에 속기 쉬워서 영상 전체를 봅니다."""
    end = duration_sec - ROI_END_GUARD_SEC
    if end <= ROI_START_SEC:  # 아주 짧은 영상이면 처음부터 (끝 - 5초)까지에서 고른다
        return list(np.linspace(0.0, max(end, 0.0), num_frames))
    return list(np.linspace(ROI_START_SEC, end, num_frames))


def _roi_ocr_frame(ocr, frame):
    """한 장면을 OCR 해서 [(상자, 글자), ...] 를 돌려줍니다.
    v2 는 "같은 자리에 같은 글자가 계속 있나"로 고정 UI 를 가려내므로 글자 내용도 씁니다."""
    h, w = frame.shape[:2]
    items = []
    for res in ocr.predict(frame):
        polys = res.get("rec_polys")
        texts = res.get("rec_texts") or []
        if polys is None or len(polys) == 0:  # 인식 결과가 없으면 감지 상자만이라도 쓴다
            polys = res.get("dt_polys") or []
            texts = []
        for i, poly in enumerate(polys):
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            box = (min(xs) / w, min(ys) / h, max(xs) / w, max(ys) / h)
            text = str(texts[i]).strip() if i < len(texts) else ""
            items.append((box, text))
    return items


def _roi_count_rows(boxes, med_h):
    """한 장면 안의 상자들이 위아래로 몇 줄인지 셉니다.
    세로 중심이 가까운 상자는 옆으로 나란한 같은 줄로 봅니다.
    상자 "개수"로 세면 한 줄에 칸이 여러 개인 메뉴·탭이 이기므로 "줄 수"로 셉니다."""
    if not boxes:
        return 0
    centers = sorted((b[1] + b[3]) / 2 for b in boxes)
    rows = 1
    row_center = centers[0]
    for c in centers[1:]:
        if c - row_center > med_h * ROI_ROW_SAME_RATIO:
            rows += 1
            row_center = c
    return rows


def _roi_count_rows_by_frame(items, med_h):
    """[(상자, 장면번호), ...] 를 장면별로 나눠 줄 수를 센 뒤 합합니다."""
    per_frame = {}
    for b, f in items:
        per_frame.setdefault(f, []).append(b)
    return sum(_roi_count_rows(boxes, med_h) for boxes in per_frame.values())


def _roi_refine_group(group):
    """한 묶음 [(상자, 장면번호), ...] 에서 채팅답지 않은 상자를 걸러냅니다.
    돌려주는 값: (남은 상자 목록, 중간 높이, 줄 수 합)"""
    # 1) 높이 필터: 채팅 글씨는 크기가 거의 같으므로 너무 작거나 큰 상자는 뺀다
    med_h = statistics.median(b[3] - b[1] for b, _ in group)
    by_height = [(b, f) for b, f in group
                 if med_h * ROI_HEIGHT_LOW <= (b[3] - b[1]) <= med_h * ROI_HEIGHT_HIGH]

    # 2) 세로 연속성: 채팅은 줄이 위아래로 붙어 있으므로, 장면마다 위에서부터 줄 세워
    #    빈칸이 크면 덩어리를 끊고 가장 큰 덩어리 하나만 남긴다 (채팅창은 한 장면에 한 덩어리)
    per_frame = {}
    for b, f in by_height:
        per_frame.setdefault(f, []).append(b)
    kept = []
    total_rows = 0
    for f, boxes in per_frame.items():
        boxes.sort(key=lambda b: b[1])
        chunks = [[boxes[0]]]
        for b in boxes[1:]:
            gap = b[1] - chunks[-1][-1][3]  # 다음 상자 윗변 - 앞 상자 아랫변
            if gap > med_h * ROI_VGAP_RATIO:
                chunks.append([b])
            else:
                chunks[-1].append(b)
        chunk = max(chunks, key=len)
        kept.extend((b, f) for b in chunk)
        total_rows += _roi_count_rows(chunk, med_h)
    return kept, med_h, total_rows


def _roi_pick_band(items, med_h):
    """고른 묶음의 상자(모든 장면 합친 것)를 세로 "띠"로 나누고 줄 수 합이 가장 큰 띠를 돌려줍니다.
    같은 xmin 에 있어도 채팅창 위쪽에 떨어진 툴바·제목 글자는 최종 영역에서 빼기 위함입니다."""
    items = sorted(items, key=lambda x: x[0][1])  # ymin 순
    bands = [[items[0]]]
    band_bottom = items[0][0][3]  # 지금까지 띠의 가장 큰 ymax
    for item in items[1:]:
        if item[0][1] - band_bottom > med_h * ROI_BAND_GAP_RATIO:
            bands.append([item])  # 빈칸이 크면 새 띠
            band_bottom = item[0][3]
        else:
            bands[-1].append(item)
            band_bottom = max(band_bottom, item[0][3])
    return max(bands, key=lambda band: _roi_count_rows_by_frame(band, med_h))


def _roi_detect(ocr, video_path):
    """Auto-ROI v2 본체 (WBBPPOCRExtractor.detect_chat_roi_v2 가 부름). 성공하면 (roi, 줄 수 합, 등장 장면 수, 읽은 장면 수), 실패하면 None."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(" ➔ [Auto-ROI v2] 영상을 열 수 없음: 기존 방식으로 대체")
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = total / fps if fps else 0.0

    # 1) 영상 전체에서 고르게 뽑은 장면마다 글자 상자 + 글자 내용을 모은다
    frames_items = []  # 장면별 [(상자, 글자), ...]
    for sec in _roi_sample_times(duration):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(sec * fps))
        ok, frame = cap.read()
        if not ok:
            continue
        try:
            frames_items.append(_roi_ocr_frame(ocr, frame))
        except Exception as e:  # 한 장면이 실패해도 나머지 장면으로 계속한다
            print(f"   ⚠️ [Auto-ROI v2] {sec:.1f}초 장면 분석 실패: {e}")
    cap.release()

    n = len(frames_items)
    if n == 0:
        print(" ➔ [Auto-ROI v2] 읽은 장면이 없음: 기존 방식으로 대체")
        return None

    # 2) 고정 글자(UI) 빼기: 채팅은 계속 올라가며 바뀌므로 같은 자리에 같은 글자가
    #    오래 머물지 않는다. 다른 장면 절반 이상에서 "같은 자리 + 같은 글자"로
    #    나오는 상자는 방송 제목·메뉴 같은 화면 고정 UI 로 보고 뺀다.
    need = ROI_FIXED_RATIO * (n - 1)
    kept = []  # [(상자, 장면번호), ...]
    for i, items in enumerate(frames_items):
        for box, text in items:
            same_count = 0
            if text:  # 글자 내용이 비어 있으면 비교할 수 없으니 고정으로 보지 않는다
                for j, other in enumerate(frames_items):
                    if j != i and any(t == text and _roi_iou(box, b) >= ROI_FIXED_IOU for b, t in other):
                        same_count += 1
            if not (n > 1 and text and same_count >= need):
                kept.append((box, i))

    # 3) 왼쪽 시작 위치(xmin)로 묶기: 채팅은 줄마다 왼쪽 끝이 맞춰져 있어 한 묶음에 모인다.
    #    "바로 앞 상자"가 아니라 "묶음의 첫 상자"와 비교해야 묶음 폭이 끝없이 늘지 않는다.
    groups = []
    for item in sorted(kept, key=lambda x: x[0][0]):
        if groups and item[0][0] - groups[-1][0][0][0] <= ROI_XMIN_GAP:
            groups[-1].append(item)
        else:
            groups.append([item])

    # 4) 상자 수가 많은 묶음 몇 개를 걸러 보고, 점수가 가장 큰 묶음을 채팅으로 고른다.
    #    점수 = 줄 수 합 × (그 묶음이 남아 있는 장면 수 / 읽은 장면 수)
    #    채팅창은 방송 내내 떠 있어서 거의 모든 장면에 나오고, 잠깐 뜬 창(게임 목록 등)은
    #    등장 장면 비율이 낮아 점수가 깎인다.
    best = None
    for g in sorted(groups, key=len, reverse=True)[:ROI_TOP_GROUPS]:
        remain, med_h, rows = _roi_refine_group(g)
        seen_frames = len({f for _, f in remain})
        score = rows * (seen_frames / n)
        if best is None or score > best["score"]:
            best = {"remain": remain, "median_h": med_h, "rows": rows,
                    "seen_frames": seen_frames, "score": score}

    # 5) 줄 수 합이 너무 적으면 채팅을 못 찾은 것으로 본다
    if best is None or best["rows"] < ROI_MIN_ROWS:
        rows = best["rows"] if best else 0
        print(f" ➔ [Auto-ROI v2] 줄 수 합 {rows} < {ROI_MIN_ROWS}: 기존 방식으로 대체")
        return None

    # 6) 같은 묶음 안에서도 위아래로 크게 떨어진 글자(툴바 등)는 빼고 가장 줄이 많은 띠만 남긴다
    band = _roi_pick_band(best["remain"], best["median_h"])

    # 7) 그 띠의 상자를 모두 감싸는 사각형 + 여백 (기존과 같은 (ymin, xmin, ymax, xmax) 순서)
    boxes = [b for b, _ in band]
    xmin = max(0.0, min(b[0] for b in boxes) - ROI_MARGIN_X)
    ymin = max(0.0, min(b[1] for b in boxes) - ROI_MARGIN_Y)
    xmax = min(1.0, max(b[2] for b in boxes) + ROI_MARGIN_X)
    ymax = min(1.0, max(b[3] for b in boxes) + ROI_MARGIN_Y)
    roi = (round(ymin, 2), round(xmin, 2), round(ymax, 2), round(xmax, 2))
    return roi, best["rows"], best["seen_frames"], n



class WBBPPOCRExtractor:
    def __init__(self):
        print("🚀 [PaddleOCR] 한국어 채팅 인식 모델 로딩 중...")

        # [feature/ai-ocr 브랜치에서 채택] 파인튜닝된 인식(rec) 모델 연결
        # models/wbb_rec/ 가 있으면 그걸 쓰고, 없으면(아직 파인튜닝 전 환경)
        # 기본 사전학습 모델로 자동 대체합니다.
        #
        # [버전 주의] PaddleOCR 3.x부터 rec_model_dir/rec_char_dict_path
        # 파라미터가 없어졌습니다. 사전(dict) 정보는 이제 export된 모델의
        # inference.yml 안에 내장되는 방식으로 바뀌어서, 파라미터로 따로
        # 넘길 필요가 없습니다. 모델 폴더 경로는 text_recognition_model_dir
        # 라는 새 이름으로 넘깁니다.
        finetuned_rec_dir = os.path.join(os.path.dirname(__file__), "models", "wbb_rec")

        # [2026-09 재시도] 이전엔 저희 코드가 미리 paddle.device.cuda로
        # GPU 개수를 확인한 뒤 PaddleOCR을 만들었는데, 이게 PaddleOCR
        # 내부의 CUDA 초기화 순서를 저희가 먼저 건드려서 깨뜨렸을
        # 가능성이 높습니다 (paddle.tensor가 아직 준비 안 된 상태에서
        # 접근되는 circular import 증상과 정확히 들어맞습니다).
        # 이번엔 저희가 먼저 검사하지 않고, device="gpu:0"를 PaddleOCR
        # 생성자에 그대로 넘겨서 PaddleOCR 스스로 알아서 초기화하게
        # 두고, 생성자 호출 자체를 통째로 try/except로 감싸서 실패하면
        # (GPU가 없거나, 버전 문제거나) 검증된 CPU 설정으로 폴백합니다.
        gpu_kwargs = dict(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="gpu:0",
            # [Colab T4 세그폴트 회피] 기본 감지 모델(PP-OCRv5_server_det)이
            # T4 GPU에서 종료 코드 -11(SIGSEGV)로 프로세스를 죽입니다.
            # 세그폴트는 아래 try/except로 잡히지 않아 CPU 폴백도 동작하지
            # 않으므로, 가벼운 mobile 감지 모델로 바꿔 문제 자체를 피합니다.
            text_detection_model_name="PP-OCRv5_mobile_det",
            # det 모델 이름을 지정하면 PaddleOCR이 lang="korean"을 무시하므로
            # (기본 중국어 rec 모델로 바뀜), 한국어 rec 모델도 명시해야 합니다.
            text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
            det_db_unclip_ratio=2.0,
            det_db_box_thresh=0.5,
        )
        cpu_kwargs = dict(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            # [PIR/oneDNN 호환성 수정] FLAGS_use_onednn 환경변수는 구버전
            # 방식이라 PaddlePaddle 3.3+의 새 PIR 실행 경로에는 안 먹힙니다.
            # 생성자에 enable_mkldnn=False를 직접 넘겨야
            # "ConvertPirAttribute2RuntimeAttribute not support" 크래시가
            # 사라집니다.
            enable_mkldnn=False,
            # GPU 경로와 같은 감지 모델을 써서, 어느 경로로 초기화되든
            # Auto-ROI/품질 필터 결과가 같게 맞춥니다. (CPU 속도도 더 빠름)
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
            det_db_unclip_ratio=2.0,
            det_db_box_thresh=0.5,
        )

        if os.path.isdir(finetuned_rec_dir):
            gpu_kwargs["text_recognition_model_dir"] = finetuned_rec_dir
            cpu_kwargs["text_recognition_model_dir"] = finetuned_rec_dir
            gpu_kwargs["text_recognition_model_name"] = "korean_PP-OCRv3_mobile_rec"  # 튜닝 모델은 PP-OCRv3 구조라 이름을 맞춤
            cpu_kwargs["text_recognition_model_name"] = "korean_PP-OCRv3_mobile_rec"  # 튜닝 모델은 PP-OCRv3 구조라 이름을 맞춤
            print("🎯 파인튜닝된 채팅 인식 모델(models/wbb_rec)을 사용합니다.")
        else:
            print("ℹ️ 파인튜닝된 모델을 찾지 못해 기본 사전학습 모델을 사용합니다.")

        # [2026-10 수정] OCR 실행 장치 선택 (.env의 OCR_DEVICE)
        #   cpu  : GPU를 아예 시도하지 않고 바로 CPU로 실행
        #   gpu  : GPU로 먼저 시도하고, 실패하면 CPU로 폴백
        #   auto : (기본값) Windows면 cpu, 그 외(Linux/Colab)면 gpu와 같음
        #
        # Windows에서 GPU 시도가 cudnn DLL 로딩 실패(WinError 127)로 끝나면,
        # paddle 모듈이 "반쯤 로딩된" 상태로 남습니다. 그 상태에서 같은
        # 프로세스 안에서 CPU로 다시 만들면 "partially initialized module
        # 'paddle' has no attribute 'tensor' (circular import)"로 CPU까지
        # 실패합니다. 그래서 Windows에서는 처음부터 GPU를 건드리지 않습니다.
        device_pref = os.getenv("OCR_DEVICE", "auto").strip().lower()
        if device_pref == "auto":
            device_pref = "cpu" if platform.system() == "Windows" else "gpu"

        if device_pref == "cpu":
            print("🖥️ CPU로 PaddleOCR을 초기화합니다. (OCR_DEVICE=cpu 또는 Windows 기본값)")
            self.ocr = PaddleOCR(**cpu_kwargs)
            print("✅ PaddleOCR 모델 로딩 완료 (CPU)")
        else:
            try:
                print("🚀 GPU(device=\"gpu:0\")로 PaddleOCR 초기화를 시도합니다...")
                self.ocr = PaddleOCR(**gpu_kwargs)
                print("✅ PaddleOCR GPU 초기화 성공")
            except Exception as e:
                print(f"⚠️ GPU 초기화 실패({type(e).__name__}: {e}) — CPU로 폴백합니다.")
                self.ocr = PaddleOCR(**cpu_kwargs)
                print("✅ PaddleOCR 모델 로딩 완료 (CPU)")

    # ------------------------------------------------------------------
    # [ai-nlp 브랜치에서 채택] Auto-ROI: crop_box를 영상마다 하드코딩하지 않고
    # 초반 몇 초를 스캔해 텍스트가 밀집된 영역(좌/중/우)을 채팅창으로 추정합니다.
    # ------------------------------------------------------------------
    def detect_chat_roi(self, video_path: str, sample_seconds: list = [2.0, 5.0, 10.0]) -> tuple:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("⚠️ [Auto-ROI] 영상을 열 수 없어 기본 우측 영역을 사용합니다.")
            return (0.15, 0.65, 0.95, 0.98)

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        boxes_collected = []

        print("🔍 [Auto-ROI] 화면 내 실시간 채팅창 위치 자동 분석 중...")

        for sec in sample_seconds:
            frame_no = int(sec * fps)
            if frame_no >= total_frames:
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]
            try:
                # predict()는 인식(rec)까지 항상 같이 돌지만, 여기서는 텍스트
                # "위치"만 필요하므로 dt_polys/rec_polys만 사용하고 텍스트
                # 내용 자체는 무시합니다.
                result = self.ocr.predict(frame)
            except Exception as e:
                print(f"   ⚠️ [Auto-ROI] {sec}초 프레임 분석 실패: {e}")
                continue

            for res in result:
                polys = res.get("rec_polys") or res.get("dt_polys") or []
                for poly in polys:
                    xs = [float(pt[0]) for pt in poly]
                    ys = [float(pt[1]) for pt in poly]
                    xmin, xmax = min(xs) / w, max(xs) / w
                    ymin, ymax = min(ys) / h, max(ys) / h
                    boxes_collected.append((xmin, ymin, xmax, ymax))

        cap.release()

        if len(boxes_collected) < 3:
            print(" ➔ [Auto-ROI] 텍스트 밀집도 부족: 기본 스트리밍 UI(우측 영역)로 설정")
            return (0.15, 0.65, 0.95, 0.98)

        x_centers = [(b[0] + b[2]) / 2 for b in boxes_collected]
        left_count = sum(1 for x in x_centers if x < 0.35)
        mid_count = sum(1 for x in x_centers if 0.35 <= x <= 0.65)
        right_count = sum(1 for x in x_centers if x > 0.65)

        if right_count >= left_count and right_count >= mid_count:
            cluster_boxes = [b for b in boxes_collected if (b[0] + b[2]) / 2 > 0.55]
        elif left_count >= right_count and left_count >= mid_count:
            cluster_boxes = [b for b in boxes_collected if (b[0] + b[2]) / 2 < 0.45]
        else:
            cluster_boxes = [b for b in boxes_collected if 0.30 <= (b[0] + b[2]) / 2 <= 0.70]

        if not cluster_boxes:
            cluster_boxes = boxes_collected

        auto_xmin = max(0.0, min(b[0] for b in cluster_boxes) - 0.03)
        auto_xmax = min(1.0, max(b[2] for b in cluster_boxes) + 0.03)
        auto_ymin = max(0.0, min(b[1] for b in cluster_boxes) - 0.05)
        auto_ymax = min(1.0, max(b[3] for b in cluster_boxes) + 0.05)

        detected_roi = (round(auto_ymin, 2), round(auto_xmin, 2), round(auto_ymax, 2), round(auto_xmax, 2))
        print(f"🎯 [Auto-ROI 탐지 성공] 감지된 채팅 영역: Y({detected_roi[0]}~{detected_roi[2]}), "
              f"X({detected_roi[1]}~{detected_roi[3]})")
        return detected_roi

    # ------------------------------------------------------------------
    # [Auto-ROI v2] 영상 전체에서 "방송 내내 떠 있는 채팅 줄 기둥"을 찾습니다.
    # 순서: 장면 20장 OCR → 고정 UI 빼기 → 왼쪽 끝(xmin)으로 묶기 →
    #       높이·세로 연속성으로 거르기 → 점수(줄 수 합 × 등장 장면 비율)로 고르기 →
    #       세로 띠 하나 남기기 → 여백 붙이기.
    # 어느 단계든 실패하면 기존 detect_chat_roi 결과를 그대로 씁니다.
    # ------------------------------------------------------------------
    def detect_chat_roi_v2(self, video_path: str) -> tuple:
        print("🔍 [Auto-ROI v2] 영상 전체 장면에서 채팅창 위치 자동 분석 중...")
        try:
            result = _roi_detect(self.ocr, video_path)
        except Exception as e:  # v2 에서 예상 못 한 오류가 나도 분석 자체는 멈추지 않게 한다
            print(f" ➔ [Auto-ROI v2] 분석 중 오류({type(e).__name__}: {e}): 기존 방식으로 대체")
            return self.detect_chat_roi(video_path)
        if result is None:
            return self.detect_chat_roi(video_path)

        roi, rows, seen_frames, n = result
        print(f"🎯 [Auto-ROI 탐지 성공] 감지된 채팅 영역: Y({roi[0]}~{roi[2]}), "
              f"X({roi[1]}~{roi[3]}) (v2, 줄 수 합 {rows}, 등장 장면 {seen_frames}/{n})")
        return roi

    def _preprocess_chat_image(self, cropped_bgr: np.ndarray) -> np.ndarray:
        """
        이진화 대신 CLAHE로 대비만 개선합니다. 강제 이진화는 얇은 한글
        획을 뭉개 오히려 인식률을 떨어뜨리므로, 회색조 그라데이션은
        그대로 살려 둡니다.

        [중요] CLAHE는 흑백(단일 채널) 이미지만 반환하는데, PaddleX 파이프라인은
        항상 3채널(H, W, 3) BGR 이미지를 기대합니다. 흑백을 그대로 넘기면
        내부에서 "not enough values to unpack (expected 3, got 2)" 에러가 나며
        모든 프레임이 조용히 스킵됩니다. 그래서 마지막에 다시 3채널로 복원합니다.
        """
        gray = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2GRAY)
        # [속도 조정] enable_mkldnn=False로 인한 CPU 추론 속도 저하를 보완하기 위해
        # 확대 배율을 3배(면적 9배)에서 2배(면적 4배)로 낮췄습니다. mkldnn을 다시 켜면
        # 예전에 겪은 ConvertPirAttribute2RuntimeAttribute 크래시가 재발할 수 있어
        # 그쪽 대신 여기서 연산량을 줄이는 쪽을 택했습니다.
        resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(resized)

        # [핵심 수정] PaddleX가 요구하는 3채널 (H, W, 3) 형태로 복원
        return cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)

    def extract_chat_from_video(
        self,
        video_path: str,
        crop_box: tuple = None,
        sample_rate_sec: float = 2.0,
        output_csv_path: str = "extracted_ocr_chats.csv",
        debug_dump_dir: str = None,
        debug_max_dumps: int = 5,
    ):
        """
        crop_box를 None으로 두면 detect_chat_roi()가 자동으로 좌표를 잡습니다.
        직접 좌표를 알고 있다면 (ymin, xmin, ymax, xmax) 튜플로 넘겨서
        자동 탐지를 건너뛸 수 있습니다.

        debug_dump_dir을 지정하면 실제 OCR에 들어가는 크롭/전처리 후 이미지를
        지정 폴더에 몇 장 저장합니다. Auto-ROI가 잡은 영역이 실제로 채팅창이
        맞는지, 전처리 후에도 글자를 읽을 수 있는 상태인지 눈으로 먼저 확인한
        뒤 전체 영상을 돌리는 걸 권장합니다.
        """
        if debug_dump_dir:
            os.makedirs(debug_dump_dir, exist_ok=True)
        debug_dump_count = 0

        if not os.path.exists(video_path):
            print(f"❌ [오류] 영상 파일을 찾을 수 없습니다: {video_path}")
            return []

        if crop_box is None:
            crop_box = self.detect_chat_roi_v2(video_path)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ [오류] 영상을 열 수 없습니다: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            print("❌ [오류] 영상 FPS를 읽을 수 없습니다.")
            cap.release()
            return []

        frame_interval = max(1, int(fps * sample_rate_sec))
        extracted_chats = []
        frame_idx = 0

        ymin, xmin, ymax, xmax = crop_box
        print(f"🎬 [OCR 스캔 시작] 파일: {video_path} (FPS: {fps:.1f}, 샘플링 주기: {sample_rate_sec}초)")
        print(f"   크롭 영역: Y({ymin}~{ymax}), X({xmin}~{xmax})")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                current_time_sec = round(frame_idx / fps, 2)
                h, w = frame.shape[:2]

                crop_y1, crop_y2 = int(h * ymin), int(h * ymax)
                crop_x1, crop_x2 = int(w * xmin), int(w * xmax)

                crop_y1, crop_y2 = max(0, min(crop_y1, h)), max(0, min(crop_y2, h))
                crop_x1, crop_x2 = max(0, min(crop_x1, w)), max(0, min(crop_x2, w))

                if crop_y2 <= crop_y1 or crop_x2 <= crop_x1:
                    frame_idx += 1
                    continue

                cropped_img = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                if cropped_img.size == 0:
                    frame_idx += 1
                    continue

                try:
                    processed_img = self._preprocess_chat_image(cropped_img)
                except Exception as e:
                    print(f" ⚠️ [{current_time_sec}초] 전처리 스킵 (오류: {e})")
                    frame_idx += 1
                    continue

                if debug_dump_dir and debug_dump_count < debug_max_dumps:
                    cv2.imwrite(os.path.join(debug_dump_dir, f"{debug_dump_count:02d}_crop_raw.png"), cropped_img)
                    cv2.imwrite(os.path.join(debug_dump_dir, f"{debug_dump_count:02d}_crop_processed.png"), processed_img)
                    debug_dump_count += 1

                # --------------------------------------------------
                # OCR 실행 및 텍스트 파싱 (PaddleOCR 3.x의 predict() API)
                # --------------------------------------------------
                try:
                    result = self.ocr.predict(processed_img)

                    recognized_texts = []
                    for res in result:
                        texts = res.get("rec_texts", [])
                        scores = res.get("rec_scores", [])
                        for text_content, confidence in zip(texts, scores):
                            text_content = str(text_content).strip()
                            try:
                                confidence = float(confidence)
                            except (TypeError, ValueError):
                                continue
                            if confidence < 0.5 or not text_content:
                                continue

                            # [ai-nlp 브랜치에서 채택] 잡음성 특수문자만 있는
                            # 텍스트는 제외 (Auto-ROI가 UI 테두리를 살짝 물었을 때 방지)
                            clean_chars = [c for c in text_content if c not in NOISE_CHARS]
                            if clean_chars:
                                recognized_texts.append(text_content)

                    if recognized_texts:
                        # [구조 수정] 한 프레임엔 서로 다른 여러 사람의 채팅이 동시에
                        # 찍힙니다. 이걸 전부 합친 뒤 "하나의 문장"인 것처럼 품질을
                        # 판단하면, 짧은 반응이 여러 개 겹치는 진짜 하이프 순간이
                        # "조각난 잡음"으로 오판돼 통째로 삭제될 위험이 있습니다.
                        # 그래서 메시지(감지된 박스) 하나하나를 따로 판단해서,
                        # 잡음으로 보이는 것만 개별로 제거하고 나머지는 살립니다.
                        quality_texts = [t for t in recognized_texts if is_quality_korean_line(t)]
                        dropped_texts = [t for t in recognized_texts if t not in quality_texts]

                        if quality_texts:
                            combined_text = " ".join(quality_texts)
                            extracted_chats.append({
                                "timestamp": current_time_sec,
                                "frame": frame_idx,
                                "chat_text": combined_text
                            })
                            print(f" ➔ [{current_time_sec:>6.2f}초] 정밀 OCR 인식: {combined_text}")
                            if dropped_texts:
                                print(f"    (잡음으로 개별 제외: {dropped_texts})")
                        else:
                            print(f" 🗑️ [{current_time_sec:>6.2f}초] 전부 잡음으로 판단해 제외: {recognized_texts}")

                except Exception as e:
                    print(f" ⚠️ [{current_time_sec}초] 프레임 스킵 (OCR 에러: {e})")

            frame_idx += 1

        cap.release()

        # --------------------------------------------------
        # CSV 파일 저장
        # 인식 결과가 0건이어도 항상 새로 씁니다.
        # (이걸 안 하면 이전 실행 결과 CSV가 그대로 남아있어서,
        #  이번 영상과 무관한 옛날 데이터로 다음 단계가 진행됩니다)
        # --------------------------------------------------
        # 0건이면 pd.DataFrame([])에 컬럼이 하나도 없어서 헤더 없는 빈 파일이
        # 써지고, 다음 단계 read_csv가 "No columns to parse"로 죽습니다.
        # 컬럼을 명시해서 0건이어도 헤더는 항상 남깁니다.
        df = pd.DataFrame(extracted_chats, columns=["timestamp", "frame", "chat_text"])
        df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")

        if extracted_chats:
            print("\n" + "=" * 70)
            print(f"✅ [추출 완료] 총 {len(extracted_chats)}건의 채팅 데이터가 '{output_csv_path}'에 저장되었습니다!")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("⚠️ [경고] 인식된 텍스트가 없습니다. Auto-ROI 결과 또는 crop_box 좌표를 확인하세요.")
            print(f"   (빈 CSV를 새로 기록했습니다: {output_csv_path})")
            print("=" * 70)

        return extracted_chats


if __name__ == "__main__":
    extractor = WBBPPOCRExtractor()

    extractor.extract_chat_from_video(
        video_path="./test_sample.mp4",
        crop_box=None,  # None이면 Auto-ROI가 자동으로 채팅 영역을 잡습니다.
        sample_rate_sec=2.0,
        output_csv_path="extracted_ocr_chats.csv",
        debug_dump_dir="./debug_frames",
    )