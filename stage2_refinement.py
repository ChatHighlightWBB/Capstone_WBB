"""
=============================================================================
[와바바(WBB)] 4단계: 2차 정밀 검증 (스트리머 음성 분리 + Whisper STT + KoBERT)
- 담당자: 송태섭 (책임개발자)
- 핵심 패치:
  1. Whisper 디바이스 GPU(CUDA) 가속 자동 할당 (CPU 병목 해결)
  2. Demucs 음성 분리 성공 여부(demucs_success) 메타데이터 기록
- 입력: stage1_candidates.json, 원본 비디오 파일
- 출력: final_highlight_candidates.json, final_highlight_candidates.csv
=============================================================================
"""

import os
import json
import subprocess
import torch
import whisper
import pandas as pd
import numpy as np
from automated_dataset_generator import WBBEmotionDatasetGenerator


class WBBStage2Refinement:
    def __init__(self, model_dir: str = "./kobert_wbb_model"):
        # [패치 1] GPU 가속 자동 적용 (NVIDIA CUDA 우선 할당)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 [Step 4] 2차 정밀 검증 엔진 로딩 중... (연산 디바이스: {self.device.upper()})")
        
        # Whisper STT 로딩
        self.whisper_model = whisper.load_model("base", device=self.device)
        
        # KoBERT 감정 분석기 로딩
        self.kobert_gen = WBBEmotionDatasetGenerator(model_dir=model_dir)
        print("✅ [Step 4] Whisper & KoBERT 로딩 완료")

    def _separate_vocals_demucs(self, audio_clip_path: str, output_dir: str = "./temp_separated") -> tuple:
        """
        Demucs CLI를 통해 스트리머 목소리(vocals.wav)를 분리합니다.
        실패 시 (False, 원본 경로)를 반환하여 상태를 투명하게 기록합니다.
        """
        os.makedirs(output_dir, exist_ok=True)
        cmd = ["demucs", "--two-stems=vocals", "-o", output_dir, audio_clip_path]
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            # Demucs 출력 기본 경로: {output_dir}/htdemucs/{clip_name}/vocals.wav
            clip_name = os.path.splitext(os.path.basename(audio_clip_path))[0]
            vocals_path = os.path.join(output_dir, "htdemucs", clip_name, "vocals.wav")
            
            if os.path.exists(vocals_path):
                return True, vocals_path
            return False, audio_clip_path
        except Exception as e:
            print(f" ⚠️ [Demucs 경고] 보컬 분리 실패 (원인: {e}). 원본 오디오로 폴백합니다.")
            return False, audio_clip_path

    def refine_candidates(
        self, 
        video_path: str,
        stage1_json: str = "stage1_candidates.json", 
        output_json: str = "final_highlight_candidates.json",
        output_csv: str = "final_highlight_candidates.csv",
        top_k: int = 10
    ):
        if not os.path.exists(stage1_json):
            raise FileNotFoundError(f"❌ '{stage1_json}' 파일이 없습니다.")

        with open(stage1_json, "r", encoding="utf-8") as f:
            stage1_data = json.load(f)

        candidate_clips = stage1_data.get("candidate_clips", [])
        if not candidate_clips:
            print("⚠️ 1차 후보 클립이 비어 있습니다.")
            return []

        os.makedirs("./temp_clips", exist_ok=True)
        refined_results = []

        print(f"\n🔍 [Step 4] 총 {len(candidate_clips)}개 후보 클립 스트리머 발화 정밀 검증 시작")

        for idx, clip in enumerate(candidate_clips, 1):
            start_t = clip["start_time"]
            end_t = clip["end_time"]
            dur = clip["duration"]

            # A. 임시 오디오 클립 추출 (WAV)
            temp_audio = f"./temp_clips/temp_cand_{idx}.wav"
            cmd_extract = [
                "ffmpeg", "-y", "-ss", str(start_t), "-to", str(end_t),
                "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                temp_audio
            ]
            subprocess.run(cmd_extract, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # B. Demucs 보컬 분리 시도
            demucs_ok, target_audio = self._separate_vocals_demucs(temp_audio)

            # C. Whisper STT 변환
            stt_result = self.whisper_model.transcribe(target_audio, language="ko")
            speech_text = stt_result.get("text", "").strip()

            # D. KoBERT 2차 발화 감정 분석
            streamer_joy = 0.0
            top_emo = "중립"
            if speech_text:
                top_emo, probs = self.kobert_gen.predict_emotion(speech_text)
                streamer_joy = float(probs[0] * 100.0)

            # 최종 점수 = 1차 시청자 점수(50%) + 2차 스트리머 발화 기쁨(50%)
            final_score = round((clip["window_score"] * 0.5) + (streamer_joy * 0.5), 2)

            refined_results.append({
                "clip_id": idx,
                "start_time": start_t,
                "end_time": end_t,
                "duration": dur,
                "final_score": final_score,
                "stage1_score": clip["window_score"],
                "streamer_joy": round(streamer_joy, 2),
                "speech_text": speech_text,
                "streamer_emotion": top_emo,
                "demucs_applied": demucs_ok  # [패치 2] 분리 성공 여부 투명 기록
            })
            print(f" ➔ [{idx}/{len(candidate_clips)}] {start_t}초~{end_t}초 | STT: '{speech_text[:25]}' | 최종점수: {final_score}")

        # 점수 상위 top_k(10개) 선정 후 시간순 재정렬
        top_candidates = sorted(refined_results, key=lambda x: x["final_score"], reverse=True)[:top_k]
        final_highlights = sorted(top_candidates, key=lambda x: x["start_time"])

        payload = {
            "metadata": {
                "source_video": video_path,
                "total_stage1_evaluated": len(candidate_clips),
                "final_selected_count": len(final_highlights)
            },
            "highlight_clips": final_highlights
        }

        with open(output_json, "w", encoding="utf-8") as jf:
            json.dump(payload, jf, ensure_ascii=False, indent=2)

        pd.DataFrame(final_highlights).to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"✅ [Step 4 완료] 상위 {len(final_highlights)}개 최종 하이라이트 확정 -> '{output_json}'")
        return final_highlights


if __name__ == "__main__":
    refiner = WBBStage2Refinement()
    refiner.refine_candidates(video_path="test_sample_game.mp4")