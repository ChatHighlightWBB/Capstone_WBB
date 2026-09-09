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

        self.ocr = PaddleOCR(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            det_db_unclip_ratio=2.0,
            det_db_box_thresh=0.5,
        )
        print("✅ PaddleOCR 모델 로딩 완료")

    def extract_chat_from_video(self, video_path: str, crop_box: tuple, sample_rate_sec: float = 1.0,
                                 output_csv_path: str = "extracted_ocr_chats.csv",
                                 debug_dump_dir: str = None, debug_max_dumps: int = 5):
        """
        debug_dump_dir을 지정하면 실제 OCR에 들어가는 크롭/전처리 후 이미지를
        지정 폴더에 몇 장 저장합니다. crop_box 좌표가 채팅창을 제대로 잡고 있는지,
        전처리 후에도 글자가 읽을 수 있는 상태인지 눈으로 먼저 확인한 뒤
        전체 영상을 돌리는 걸 권장합니다.
        """
        if debug_dump_dir:
            os.makedirs(debug_dump_dir, exist_ok=True)
        debug_dump_count = 0

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
                # OpenCV 전처리 (이진화 대신 CLAHE로 대비만 개선)
                # --------------------------------------------------
                try:
                    gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
                    resized = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    processed_img = clahe.apply(resized)
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
            print("⚠️ [경고] 인식된 텍스트가 없습니다. 채팅창 위치(crop_box) 좌표를 다시 확인하세요.")
            print(f"   (빈 CSV를 새로 기록했습니다: {output_csv_path})")
            print("=" * 70)

        return extracted_chats


if __name__ == "__main__":
    extractor = WBBPPOCRExtractor()
    TEST_VIDEO = "./test_sample.mp4"

    extractor.extract_chat_from_video(
        video_path=TEST_VIDEO,
        crop_box=(0.15, 0.65, 0.60, 0.98),
        sample_rate_sec=1.0,
        output_csv_path="extracted_ocr_chats.csv",
        debug_dump_dir="./debug_frames",
    )