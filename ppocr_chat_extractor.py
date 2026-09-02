import os
import cv2
import pandas as pd
import numpy as np
import logging

from paddleocr import PaddleOCR

# PaddleOCR 내부 로그 최소화
logging.getLogger("ppocr").setLevel(logging.ERROR)

class WBBPPOCRExtractor:
    def __init__(self):
        print("🚀 [PP-OCRv3] 한국어 문자 인식 모델 로딩 중...")
        
        # 안정적인 PaddleOCR 2.10.0 구동 설정
        self.ocr = PaddleOCR(
            lang="korean",
            use_angle_cls=True,
            use_gpu=False
        )
        print("✅ PaddleOCR 모델 로딩 완료")

    def extract_chat_from_video(self, video_path: str, crop_box: tuple, sample_rate_sec: float = 1.0, output_csv_path: str = "extracted_ocr_chats.csv"):
        if not os.path.exists(video_path):
            print(f"❌ [오류] 영상 파일을 찾을 수 없습니다: {video_path}")
            return []

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

        print(f"🎬 [OCR 고도화 스캔 시작] 파일: {video_path} (FPS: {fps:.1f})")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                current_time_sec = round(frame_idx / fps, 2)
                h, w = frame.shape[:2]
                
                # 1. 좌표 변환 및 안전 범위 처리
                ymin, xmin, ymax, xmax = crop_box
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

                # --------------------------------------------------
                # [핵심 고도화] OpenCV 고급 전처리 파이프라인
                # --------------------------------------------------
                try:
                    # A. 흑백 변환
                    gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
                    
                    # B. 2배 확대 (INTER_CUBIC 보간법으로 폰트 계단 현상 최소화)
                    resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                    
                    # C. 적응형 이진화 (Adaptive Thresholding)
                    # 반투명 채팅창의 배경 명암 변화를 극복하기 위해 주변 픽셀 평균값 기준으로 글자 분리
                    thresh = cv2.adaptiveThreshold(
                        resized, 255, 
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                        cv2.THRESH_BINARY, 
                        11, 2
                    )
                    
                    # D. 형태학적 연산 (Morphology - 노이즈 제거 및 획 굵게 보정)
                    kernel = np.ones((1, 1), np.uint8)
                    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
                    processed_img = cv2.dilate(opening, kernel, iterations=1)

                except Exception as e:
                    print(f" ⚠️ [{current_time_sec}초] 전처리 스킵 (오류: {e})")
                    frame_idx += 1
                    continue

                # --------------------------------------------------
                # OCR 실행 및 텍스트 파싱
                # --------------------------------------------------
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
                        if not isinstance(text_info, (tuple, list)) or len(text_info) < 2:
                            continue

                        text_content = str(text_info[0]).strip()
                        
                        try:
                            confidence = float(text_info[1])
                        except (TypeError, ValueError):
                            continue

                        # 신뢰도 50% 이상만 유효 텍스트로 인정
                        if confidence >= 0.5 and text_content:
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

        # CSV 파일 저장
        if extracted_chats:
            df = pd.DataFrame(extracted_chats)
            df.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
            print("\n" + "=" * 70)
            print(f"✅ [추출 완료] 총 {len(extracted_chats)}건의 채팅 데이터가 '{output_csv_path}'에 저장되었습니다!")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("⚠️ [경고] 인식된 텍스트가 없습니다. 채팅창 위치(crop_box) 좌표를 다시 확인하세요.")
            print("=" * 70)

        return extracted_chats

if __name__ == "__main__":
    extractor = WBBPPOCRExtractor()
    TEST_VIDEO = "./test_sample.mp4"
    
    extractor.extract_chat_from_video(
        video_path=TEST_VIDEO,
        crop_box=(0.15, 0.65, 0.60, 0.98),
        sample_rate_sec=1.0,
        output_csv_path="extracted_ocr_chats.csv"
    )