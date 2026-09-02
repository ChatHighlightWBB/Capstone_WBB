import os
import sys

# ==============================================================================
# [핵심 수정 1] Windows C++ DLL 충돌(WinError 127) 방어 코드
# PaddleOCR과 PyTorch 간 OpenMP 라이브러리 충돌을 막기 위해 반드시 최상단 선언
# ==============================================================================
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"

# PyTorch 엔진을 최우선으로 메모리에 로드하여 shm.dll 로딩 실패 원천 차단
import torch
import time

# 개별 AI/비전/오디오 모듈 임포트
from ppocr_chat_extractor import WBBPPOCRExtractor
from automated_dataset_generator import WBBEmotionDatasetGenerator
from sliding_window_nlp import WBBSlidingWindowDetector
from stage2_refinement import WBBStage2Refinement
from ffmpeg_clipper import WBBFFmpegClipper

class WBBAutoHighlightPipeline:
    """
    [설명]
    사용자가 영상을 업로드했을 때 1차/2차 멀티모달 분석부터 최종 영상 클리핑까지 
    자동으로 전 과정을 수행하는 와바바(WBB) 올인원 파이프라인 클래스
    """
    def __init__(self, model_dir: str = "./kobert_wbb_model"):
        print("=" * 80)
        print("🚀 [와바바 WBB] 멀티모달 자동 하이라이트 파이프라인 엔진 초기화 중...")
        print("=" * 80)
        
        # 1. 각 단계별 인퍼런스 엔진 로드
        self.ocr_extractor = WBBPPOCRExtractor()
        self.emotion_generator = WBBEmotionDatasetGenerator(model_dir=model_dir)
        self.stage2_refiner = WBBStage2Refinement(model_dir=model_dir)
        self.clipper = WBBFFmpegClipper()
        print("✅ 모든 AI/NLP/Vision 엔진 로딩 완료!\n")

    def run_full_pipeline(self, video_path: str = "./test_sample.mp4", crop_box: tuple = (0.15, 0.65, 0.60, 0.98)) -> dict:
        """
        [설명] 
        영상 경로를 입력받아 Step 1 ~ Step 5 전 과정을 순차 실행하고 
        시각화 데이터셋(JSON/CSV)과 최종 영상 경로를 반환합니다.
        """
        start_total_time = time.time()
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"입력 영상 파일을 찾을 수 없습니다: {video_path}")

        print(f"🎬 [전체 파이프라인 자동 가동] 대상 영상: {video_path}")
        
        # ----------------------------------------------------
        # [Step 1] 영상 프레임 내 채팅 OCR 추출 (PP-OCRv3)
        # ----------------------------------------------------
        ocr_csv_path = "extracted_ocr_chats.csv"
        print("\n▶️ [STEP 1/5] PP-OCRv3 실시간 채팅 추출 시작...")
        self.ocr_extractor.extract_chat_from_video(
            video_path=video_path,
            crop_box=crop_box,
            sample_rate_sec=1.0,
            output_csv_path=ocr_csv_path
        )

        # ----------------------------------------------------
        # [Step 2] KoBERT 7대 감정 정량화 및 시계열 데이터셋 생성
        # ----------------------------------------------------
        emotion_csv_path = "video_emotion_timeseries.csv"
        emotion_json_path = "video_emotion_timeseries.json"
        print("\n▶️ [STEP 2/5] KoBERT 7대 감정 확률 분석 및 시계열 데이터셋 덤프...")
        self.emotion_generator.generate_dataset(
            input_csv_path=ocr_csv_path,
            output_csv_path=emotion_csv_path,
            output_json_path=emotion_json_path
        )

        # ----------------------------------------------------
        # [Step 3] 30초 Sliding Window 및 1차 후보 클립 추출
        # ----------------------------------------------------
        stage1_json_path = "stage1_candidates.json"
        print("\n▶️ [STEP 3/5] 30초 Sliding Window 1차 하이라이트 후보 탐지...")
        detector = WBBSlidingWindowDetector(json_path=emotion_json_path)
        detector.detect_candidate_windows(
            window_size=30.0,
            step_size=5.0,
            output_json=stage1_json_path
        )

        # ----------------------------------------------------
        # [Step 4] 2차 정밀 검증 (Whisper STT + 스트리머 발화 감정 분석)
        # ----------------------------------------------------
        final_candidates_json = "final_highlight_candidates.json"
        print("\n▶️ [STEP 4/5] Whisper STT 스트리머 음성 2차 정밀 검증...")
        self.stage2_refiner.refine_candidates(
            video_path=video_path,
            stage1_json=stage1_json_path,
            output_json=final_candidates_json
        )

        # ----------------------------------------------------
        # [Step 5] FFmpeg 무인코딩 영상 클리핑 및 최종 병합
        # ----------------------------------------------------
        final_video_path = "final_highlight.mp4"
        print("\n▶️ [STEP 5/5] FFmpeg 무인코딩 고속 클리핑 및 병합...")
        self.clipper.video_path = video_path
        self.clipper.cut_and_merge_highlights(
            json_path=final_candidates_json,
            output_video=final_video_path
        )

        total_elapsed = round(time.time() - start_total_time, 2)
        print("\n" + "=" * 80)
        print(f"🎉 [파이프라인 전체 완료] 총 소요 시간: {total_elapsed}초")
        print(f" 1. 최종 하이라이트 영상 : {final_video_path}")
        print(f" 2. 시각화용 감정 데이터셋: {emotion_json_path}, {emotion_csv_path}")
        print(f" 3. 최종 구간 메타데이터  : {final_candidates_json}")
        print("=" * 80)

        return {
            "status": "success",
            "elapsed_time_sec": total_elapsed,
            "final_video": final_video_path,
            "emotion_timeseries_json": emotion_json_path,
            "final_candidates_json": final_candidates_json
        }

if __name__ == "__main__":
    pipeline = WBBAutoHighlightPipeline(model_dir="./kobert_wbb_model")
    pipeline.run_full_pipeline(
        video_path="./test_sample.mp4",
        crop_box=(0.15, 0.65, 0.60, 0.98)
    )