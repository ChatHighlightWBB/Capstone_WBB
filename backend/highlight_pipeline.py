import os
import sys
import json
import subprocess

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
        # [수정] OCR(paddle)은 더 이상 여기서 미리 로드하지 않습니다.
        # torch(Whisper/Demucs)와 같은 프로세스에 paddle이 같이 있으면
        # Windows에서 충돌이 나서, ocr_worker_cli.py를 통해 완전히 별도
        # 프로세스로 매번 실행합니다. (아래 run_full_pipeline Step 1 참고)
        self.emotion_generator = WBBEmotionDatasetGenerator(model_dir=model_dir)
        self.stage2_refiner = WBBStage2Refinement(model_dir=model_dir)
        self.clipper = WBBFFmpegClipper()
        print("✅ 모든 AI/NLP/Vision 엔진 로딩 완료!\n")

    # 프론트엔드 진행률 표시에 쓸 단계별 라벨 (server.py에서도 참조)
    STEP_LABELS = {
        1: "채팅 텍스트 인식 중 (OCR)",
        2: "감정 분석 중 (KoBERT)",
        3: "1차 하이라이트 후보 탐지 중",
        4: "스트리머 발화 정밀 검증 중 (Whisper)",
        5: "하이라이트 영상 생성 중 (FFmpeg)",
    }

    def run_full_pipeline(self, video_path: str = "./test_sample.mp4", crop_box: tuple = None,
                           on_progress=None) -> dict:
        """
        [설명] 
        영상 경로를 입력받아 Step 1 ~ Step 5 전 과정을 순차 실행하고 
        시각화 데이터셋(JSON/CSV)과 최종 영상 경로를 반환합니다.

        crop_box를 None으로 두면(기본값) Step 1에서 Auto-ROI가 영상마다
        채팅창 위치를 자동으로 탐지합니다. 특정 방송의 좌표를 이미 알고
        있어서 자동 탐지를 건너뛰고 싶을 때만 명시적으로 값을 넘기세요.

        on_progress(step: int, label: str)를 넘기면 각 단계 시작 시점에
        호출됩니다. server.py가 이걸로 실시간 진행 상황을 클라이언트에
        전달합니다. 넘기지 않으면(None) 기존과 동일하게 동작합니다.
        """
        start_total_time = time.time()

        def _report(step: int):
            if on_progress:
                try:
                    on_progress(step, self.STEP_LABELS[step])
                except Exception:
                    pass  # 진행률 표시 실패가 실제 분석을 막으면 안 됨

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"입력 영상 파일을 찾을 수 없습니다: {video_path}")

        print(f"🎬 [전체 파이프라인 자동 가동] 대상 영상: {video_path}")
        
        # ----------------------------------------------------
        # [Step 1] 영상 프레임 내 채팅 OCR 추출 (PaddleOCR)
        # ----------------------------------------------------
        _report(1)
        ocr_csv_path = "extracted_ocr_chats.csv"
        print("\n▶️ [STEP 1/5] PaddleOCR 실시간 채팅 추출 시작 (별도 프로세스)...")

        # [화면 변화량] VISUAL_FUSION 환경변수: 없거나 "on" 이면 켜짐, "off" 면 꺼짐.
        # 켜짐이면 OCR 워커가 5초 장면마다 화면 변화량을 visual_change.csv 로 같이 남기고,
        # Step 3 에서 1차 후보 점수에 아주 작은 비중(5%)의 보조 신호로 섞습니다.
        visual_on = os.getenv("VISUAL_FUSION", "on").strip().lower() != "off"
        visual_csv_path = "visual_change.csv"

        worker_path = os.path.join(os.path.dirname(__file__), "ocr_worker_cli.py")
        cmd = [sys.executable, worker_path, "--video", video_path, "--output", ocr_csv_path,
               "--sample-rate", "5.0"]
        if crop_box:
            cmd += ["--crop-box", ",".join(str(x) for x in crop_box)]
        if visual_on:
            cmd += ["--visual-output", visual_csv_path]

        # [Windows 인코딩 문제 방지] 콘솔 기본 인코딩(한글 Windows는 보통
        # cp949)으로는 이모지(🚀 등)를 표현할 수 없어서, 자식 프로세스가
        # print()만 해도 UnicodeEncodeError로 죽습니다. 자식 프로세스의
        # 표준출력 인코딩과 파이썬 자체 I/O 인코딩을 UTF-8로 강제합니다.
        worker_env = os.environ.copy()
        worker_env["PYTHONIOENCODING"] = "utf-8"
        worker_env["PYTHONUTF8"] = "1"

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=worker_env,
        )
        # 워커 프로세스의 출력을 그대로 이어서 보여줘서, 기존 로그와
        # 이어지는 것처럼 보이게 합니다 (Auto-ROI 탐지 로그, 프레임별
        # 인식 로그 등이 그대로 여기 찍힙니다).
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f"OCR 워커 프로세스 실패 (종료 코드 {result.returncode})")

        # ----------------------------------------------------
        # [Step 2] KoBERT 7대 감정 정량화 및 시계열 데이터셋 생성
        # ----------------------------------------------------
        _report(2)
        emotion_csv_path = "video_emotion_timeseries.csv"
        emotion_json_path = "video_emotion_timeseries.json"
        print("\n▶️ [STEP 2/5] KoBERT 7대 감정 확률 분석 및 시계열 데이터셋 덤프...")
        self.emotion_generator.generate_dataset(
            input_csv_path=ocr_csv_path,
            output_csv_path=emotion_csv_path,
            output_json_path=emotion_json_path,
            video_path=video_path
        )

        # ----------------------------------------------------
        # [Step 3] 30초 Sliding Window 및 1차 후보 클립 추출
        # ----------------------------------------------------
        _report(3)
        stage1_json_path = "stage1_candidates.json"
        print("\n▶️ [STEP 3/5] 30초 Sliding Window 1차 하이라이트 후보 탐지...")

        # [채팅+음성 융합] AUDIO_FUSION 환경변수: 없거나 "on" 이면 켜짐, "off" 면 꺼짐.
        # 켜짐이면 스트리머 목소리 크기(1초 dB)를 구해 1차 후보 점수에 섞습니다.
        # 음량 계산이 실패해도 분석 전체가 멈추지 않게 채팅 단독으로 진행합니다.
        audio_db_per_sec = None
        # [피치·템포] PITCH_TEMPO_FUSION 환경변수: 없거나 "on" 이면 켜짐, "off" 면 꺼짐(AUDIO_FUSION 이 켜져 있을 때만).
        # 켜짐이면 음량과 함께 피치·템포를 구해 목소리 점수(음량 80%+피치 10%+템포 10%)로 섞습니다.
        # 실패하면 분석을 멈추지 않고 아래 기존 방식(음량만)으로 다시 계산합니다.
        voice_features = None
        if (os.getenv("AUDIO_FUSION", "on").strip().lower() != "off"
                and os.getenv("PITCH_TEMPO_FUSION", "on").strip().lower() != "off"):
            try:
                from audio_energy import compute_voice_features_per_sec
                audio_start = time.time()
                features = compute_voice_features_per_sec(video_path)
                if not features["rms_db"]:  # 오디오 트랙이 없는 영상 등
                    raise ValueError("음량 값이 0개입니다(오디오 트랙 없음?)")
                audio_db_per_sec = features["rms_db"]
                voice_features = features
                print(f" ➔ 목소리 음량·피치·템포 계산 완료: {len(audio_db_per_sec)}초 분량 "
                      f"({time.time() - audio_start:.1f}초 소요)")
            except Exception as e:
                print(f"⚠️ 피치·템포 계산 실패 → 음량만 사용: {e}")
                audio_db_per_sec = None
                voice_features = None
        # 피치·템포를 이미 구했으면 건너뛰고, 꺼져 있거나 실패했으면 예전과 똑같이 음량만 계산합니다.
        if voice_features is None and os.getenv("AUDIO_FUSION", "on").strip().lower() != "off":
            try:
                from audio_energy import compute_loudness_per_sec
                audio_start = time.time()
                audio_db_per_sec = compute_loudness_per_sec(video_path, voice_band=True)
                if not audio_db_per_sec:  # 오디오 트랙이 없는 영상 등
                    raise ValueError("음량 값이 0개입니다(오디오 트랙 없음?)")
                print(f" ➔ 목소리 음량 계산 완료: {len(audio_db_per_sec)}초 분량 "
                      f"({time.time() - audio_start:.1f}초 소요)")
            except Exception as e:
                print(f"⚠️ 음량 계산 실패 → 채팅 단독으로 진행: {e}")
                audio_db_per_sec = None

        # [화면 변화량] 채팅+음성 융합일 때만 보조로 섞습니다(채팅 단독 방식은 그대로 둠).
        # 파일이 없거나 0건이어도 분석은 멈추지 않고 채팅+음성으로 진행합니다.
        visual_samples = None
        if visual_on and audio_db_per_sec is not None:
            try:
                import pandas as pd
                vdf = pd.read_csv(visual_csv_path)
                visual_samples = [(float(t), float(v)) for t, v in zip(vdf["timestamp"], vdf["value"])]
                if not visual_samples:
                    raise ValueError("화면 변화량 값이 0개입니다")
                print(f" ➔ 화면 변화량 읽기 완료: {len(visual_samples)}개")
            except Exception as e:
                print(f"⚠️ 화면 변화량 없음 → 채팅+음성으로 진행: {e}")
                visual_samples = None

        detector = WBBSlidingWindowDetector(json_path=emotion_json_path)
        stage1_candidates = detector.detect_candidate_windows(
            window_size=30.0,
            step_size=5.0,
            output_json=stage1_json_path,
            audio_db_per_sec=audio_db_per_sec,
            visual_samples=visual_samples,
            voice_features=voice_features
        )

        final_candidates_json = "final_highlight_candidates.json"

        # 채팅이 0건이거나 임계점을 넘는 구간이 없으면 Step 4~5를 건너뛰고
        # "하이라이트 0개"로 정상 종료합니다. (실패가 아니라 결과가 없는 것)
        # empty_reason으로 프론트가 사용자에게 보여줄 안내 문구를 고릅니다.
        if not stage1_candidates:
            empty_reason = "no_chats" if not detector.time_series else "no_candidates"
            with open(final_candidates_json, "w", encoding="utf-8") as jf:
                json.dump(
                    {
                        "metadata": {
                            "source_video": video_path,
                            "total_highlights_count": 0,
                            "total_highlight_duration_sec": 0.0,
                            "empty_reason": empty_reason,
                        },
                        "highlights": [],
                    },
                    jf, ensure_ascii=False, indent=2,
                )

            total_elapsed = round(time.time() - start_total_time, 2)
            print("\n" + "=" * 80)
            print(f"ℹ️ [파이프라인 조기 종료] 하이라이트 후보 없음({empty_reason}) — "
                  f"Step 4~5 생략. 총 소요 시간: {total_elapsed}초")
            print("=" * 80)
            return {
                "status": "success",
                "elapsed_time_sec": total_elapsed,
                "final_video": None,
                "highlight_clips": [],
                "emotion_timeseries_json": emotion_json_path,
                "final_candidates_json": final_candidates_json,
            }

        # ----------------------------------------------------
        # [Step 4] 2차 정밀 검증 (Whisper STT + 스트리머 발화 감정 분석)
        # ----------------------------------------------------
        _report(4)
        print("\n▶️ [STEP 4/5] Whisper STT 스트리머 음성 2차 정밀 검증...")
        self.stage2_refiner.refine_candidates(
            video_path=video_path,
            stage1_json=stage1_json_path,
            output_json=final_candidates_json
        )

        # ----------------------------------------------------
        # [Step 5] FFmpeg 무인코딩 영상 클리핑 및 최종 병합
        # ----------------------------------------------------
        _report(5)
        final_video_path = "final_highlight.mp4"
        print("\n▶️ [STEP 5/5] FFmpeg 무인코딩 고속 클리핑 및 병합...")
        self.clipper.video_path = video_path
        highlight_clip_paths = self.clipper.cut_and_merge_highlights(
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
            "highlight_clips": highlight_clip_paths or [],
            "emotion_timeseries_json": emotion_json_path,
            "final_candidates_json": final_candidates_json
        }

if __name__ == "__main__":
    pipeline = WBBAutoHighlightPipeline(model_dir="./kobert_wbb_model")
    pipeline.run_full_pipeline(
        video_path="./test_sample.mp4",
        crop_box=None  # Auto-ROI가 채팅 영역을 자동으로 탐지합니다.
    )