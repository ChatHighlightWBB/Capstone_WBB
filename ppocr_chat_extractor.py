"""
=============================================================================
[와바바(WBB)] 1단계: PP-OCRv3 텍스트 밀도 기반 Auto-ROI 자동 채팅 추출기
- 담당자: 송태섭 (책임개발자)
- 핵심 패치: Windows DLL 충돌(WinError 127) 원천 방지를 위한 Import 순서 강제화
=============================================================================
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# [핵심 해결] PaddleOCR 내부 albumentations가 torch를 뒤늦게 불러오며 발생하는 
# DLL 충돌을 막기 위해, 무조건 파일 최상단에서 torch를 먼저 메모리에 적재합니다.
import torch

import cv2
import pandas as pd
import numpy as np
import logging
from paddleocr import PaddleOCR

# PaddleOCR 내부 디버그 로그 숨김
logging.getLogger("ppocr").setLevel(logging.ERROR)


class WBBPPOCRExtractor:
    def __init__(self):
        print("🚀 [PP-OCRv3] 한국어 문자 인식 엔진 로딩 중...")
        self.ocr = PaddleOCR(
            lang="korean",
            use_angle_cls=True,
            use_gpu=False
        )
        print("✅ [PP-OCRv3] 모델 로딩 완료")

    def detect_chat_roi(self, video_path: str, sample_seconds: list = [2.0, 5.0, 10.0]) -> tuple:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("⚠️ 영상을 열 수 없어 기본 우측 영역을 사용합니다.")
            return (0.2, 0.65, 0.95, 0.98)

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
            results = self.ocr.ocr(frame, det=True, rec=False, cls=False)
            if results and results[0]:
                for box in results[0]:
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
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

        cluster_boxes = []
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
        print(f"🎯 [Auto-ROI 탐지 성공] 감지된 채팅 영역: Y({detected_roi[0]}~{detected_roi[2]}), X({detected_roi[1]}~{detected_roi[3]})")
        return detected_roi

    def preprocess_chat_image(self, cropped_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(resized)

    def extract_chat_from_video(
        self, 
        video_path: str, 
        crop_box: tuple = None, 
        sample_rate_sec: float = 2.0, 
        output_csv_path: str = "extracted_ocr_chats.csv"
    ):
        if not os.path.exists(video_path):
            print(f"❌ [오류] 영상 파일을 찾을 수 없습니다: {video_path}")
            return []

        if crop_box is None:
            crop_box = self.detect_chat_roi(video_path)

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            print("❌ [오류] 영상 FPS를 읽을 수 없습니다.")
            cap.release()
            return []

        frame_interval = max(1, int(fps * sample_rate_sec))
        extracted_chats = []
        frame_idx = 0

        ymin, xmin, ymax, xmax = crop_box
        print(f"🎬 [OCR 스캔 시작] 대상: {video_path} (샘플링 주기: {sample_rate_sec}초)")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                current_time_sec = round(frame_idx / fps, 2)
                h, w = frame.shape[:2]

                crop_y1, crop_y2 = int(h * ymin), int(h * ymax)
                crop_x1, crop_x2 = int(w * xmin), int(w * xmax)

                cropped_img = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                if cropped_img.size == 0:
                    frame_idx += 1
                    continue

                processed_img = self.preprocess_chat_image(cropped_img)

                try:
                    result = self.ocr.ocr(processed_img, cls=True)
                    if not result or not result[0]:
                        frame_idx += 1
                        continue

                    recognized_texts = []
                    for line in result[0]:
                        if not isinstance(line, list) or len(line) < 2:
                            continue
                        text_info = line[1]
                        text_content = str(text_info[0]).strip()
                        confidence = float(text_info[1])

                        if confidence >= 0.5 and len(text_content) >= 1:
                            clean_chars = [c for c in text_content if c not in "+-=;_~`|"]
                            if len(clean_chars) > 0:
                                recognized_texts.append(text_content)

                    if recognized_texts:
                        combined_text = " ".join(recognized_texts)
                        extracted_chats.append({
                            "timestamp": current_time_sec,
                            "frame": frame_idx,
                            "chat_text": combined_text
                        })
                        print(f" ➔ [{current_time_sec:>6.2f}초] 정밀 OCR 인식: {combined_text}")

                except Exception:
                    pass

            frame_idx += 1

        cap.release()

        if extracted_chats:
            df = pd.DataFrame(extracted_chats)
            df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
            print("\n" + "=" * 70)
            print(f"✅ [추출 완료] 총 {len(extracted_chats)}건의 채팅 데이터가 '{output_csv_path}'에 저장되었습니다!")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("⚠️ [경고] 유효한 텍스트가 감지되지 않았습니다.")
            print("=" * 70)

        return extracted_chats


if __name__ == "__main__":
    extractor = WBBPPOCRExtractor()
    extractor.extract_chat_from_video(
        video_path="test_sample_game.mp4",
        crop_box=None,
        sample_rate_sec=2.0,
        output_csv_path="extracted_ocr_chats.csv"
    )