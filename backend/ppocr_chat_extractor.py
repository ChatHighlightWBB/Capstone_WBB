"""
=============================================================================
[와바바(WBB)] 1단계: PP-OCRv3 텍스트 밀도 기반 Auto-ROI 자동 채팅 추출기
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

# [Windows DLL 충돌 방지] PaddleOCR 내부 albumentations가 torch를 뒤늦게
# 불러오며 발생하는 DLL 충돌(WinError 127)을 막기 위해, 파일 최상단에서
# 먼저 torch를 메모리에 적재합니다.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import torch  # noqa: F401  (import 자체가 목적, 사용은 안 함)

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


class WBBPPOCRExtractor:
    def __init__(self):
        print("🚀 [PP-OCRv3] 한국어 문자 인식 모델 로딩 중...")

        self.ocr = PaddleOCR(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            det_db_unclip_ratio=2.0,
            det_db_box_thresh=0.5,
        )
        print("✅ PaddleOCR 모델 로딩 완료")

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

    def _preprocess_chat_image(self, cropped_bgr: np.ndarray) -> np.ndarray:
        """
        이진화 대신 CLAHE로 대비만 개선합니다. PP-OCRv3는 CRNN 기반이라
        자연스러운 회색조 그라데이션으로 학습돼 있어, 강제 이진화는
        얇은 한글 획을 뭉개 오히려 인식률을 떨어뜨립니다.
        """
        gray = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(resized)

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
            crop_box = self.detect_chat_roi(video_path)

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
                        combined_text = " ".join(recognized_texts)
                        extracted_chats.append({
                            "timestamp": current_time_sec,
                            "frame": frame_idx,
                            "chat_text": combined_text
                        })
                        print(f" ➔ [{current_time_sec:>6.2f}초] 정밀 OCR 인식: {combined_text}")

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
        df = pd.DataFrame(extracted_chats)
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