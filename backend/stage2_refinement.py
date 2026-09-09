"""
=============================================================================
[와바바(WBB)] 4단계: 2차 정밀 검증 (Demucs 보컬 분리 + Whisper STT + KoBERT 감정 평가)
- 담당자: 송태섭 (책임개발자)
- 핵심 로직:
  1. 1차 후보 구간 오디오를 FFmpeg로 추출
  2. Demucs(htdemucs 모델)를 가동하여 배경음/효과음을 제거하고 순수 목소리(vocals.wav) 분리
  3. 분리된 vocals.wav를 Whisper에 전달하여 정밀 한국어 텍스트(STT) 획득
  4. KoBERT로 발화 감정 분석 후 상위 Top-K 및 최대 15분 상한선 통제
=============================================================================
"""

import os
import json
import subprocess
import torch
import pandas as pd
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification

class WBBStage2Refinement:
    def __init__(self, model_dir: str = "./kobert_wbb_model"):
        print("🧠 [1/3] 2차 검증용 KoBERT 및 Whisper STT 모델 로딩 중...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.emotion_labels = ["기쁨", "당황", "분노", "불안", "상처", "슬픔", "중립"]

        try:
            from tokenization_kobert import KoBERTTokenizer
            self.tokenizer = KoBERTTokenizer.from_pretrained(model_dir)
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)

        if os.path.exists(model_dir) and os.path.isdir(model_dir):
            try:
                self.kobert = AutoModelForSequenceClassification.from_pretrained(model_dir)
            except Exception:
                self.kobert = AutoModelForSequenceClassification.from_pretrained("skt/kobert-base-v1", num_labels=7)
        else:
            self.kobert = AutoModelForSequenceClassification.from_pretrained("skt/kobert-base-v1", num_labels=7)

        self.kobert.to(self.device)
        self.kobert.eval()
        self.vocab_size = getattr(self.kobert.config, "vocab_size", 8002)

        import whisper
        self.whisper_model = whisper.load_model("base", device="cpu")
        print("✅ 2차 검증 엔진 로딩 완료")

    def _extract_clip_audio(self, video_path: str, start_time: float, duration: float, output_wav: str):
        """FFmpeg를 사용해 비디오에서 해당 구간의 오디오를 16kHz 모노 WAV로 추출"""
        os.makedirs(os.path.dirname(output_wav) or ".", exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-t", str(duration),
            "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_wav
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    def _separate_vocals_demucs(self, input_wav: str, output_dir: str) -> str:
        """
        Demucs 경량 모델(htdemucs)을 실행하여 배경음을 제거하고 vocals.wav 경로를 반환합니다.
        실행 실패 시 원본 WAV 경로로 안전하게 Fallback(우회)합니다.
        """
        try:
            # Demucs CLI 실행 (보컬과 비보컬 2트랙 분리 옵션 적용으로 속도 향상)
            cmd = [
                "demucs",
                "--two-stems=vocals",
                "-n", "htdemucs",
                "-o", output_dir,
                input_wav
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # Demucs 결과 파일 표준 경로: {output_dir}/htdemucs/{파일명}/vocals.wav
            filename = os.path.splitext(os.path.basename(input_wav))[0]
            vocals_path = os.path.join(output_dir, "htdemucs", filename, "vocals.wav")
            
            if os.path.exists(vocals_path):
                return vocals_path
            return input_wav
        except Exception as e:
            print(f"⚠️ Demucs 분리 실패(원본 오디오 사용): {e}")
            return input_wav

    def analyze_streamer_speech_emotion(self, text: str) -> dict:
        """스트리머 발화 텍스트의 감정을 KoBERT로 분석"""
        clean_text = str(text).strip()
        if not clean_text:
            return {"dominant_emotion": "중립", "joy_score": 0.0}

        inputs = self.tokenizer(clean_text, return_tensors="pt", truncation=True, max_length=64, padding=True)
        inputs["input_ids"] = torch.clamp(inputs["input_ids"], min=0, max=self.vocab_size - 1)
        
        if "token_type_ids" in inputs:
            inputs["token_type_ids"] = torch.zeros_like(inputs["input_ids"])
            
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.kobert(**inputs)
            probs = F.softmax(outputs.logits, dim=-1).squeeze().cpu().numpy()

        joy_score = round(float(probs[0]) * 100, 2)
        dominant_idx = int(probs.argmax())
        return {
            "dominant_emotion": self.emotion_labels[dominant_idx],
            "joy_score": joy_score
        }

    def refine_candidates(self, video_path: str = "./test_sample.mp4", 
                          stage1_json: str = "stage1_candidates.json",
                          top_k: int = 10,
                          max_total_seconds: float = 900.0,
                          output_json: str = "final_highlight_candidates.json"):
        if not os.path.exists(stage1_json):
            raise FileNotFoundError(f"'{stage1_json}' 파일이 없습니다.")

        with open(stage1_json, "r", encoding="utf-8") as f:
            stage1_data = json.load(f)

        candidates = stage1_data.get("candidate_clips", [])
        if not candidates:
            print("⚠️ 1차 후보 클립이 비어 있습니다.")
            return []

        print("=" * 70)
        print(f"🎙️ [2차 정밀 검증 및 Top-{top_k} 선별 시작] 총 {len(candidates)}개 후보 대상")
        print("=" * 70)

        evaluated_clips = []
        temp_audio_dir = "./temp_separated"
        os.makedirs(temp_audio_dir, exist_ok=True)

        for idx, clip in enumerate(candidates):
            start = clip["start_time"]
            duration = clip["duration"]
            end = clip["end_time"]
            stage1_score = clip["window_score"]

            raw_wav_path = os.path.join(temp_audio_dir, f"clip_{idx}_{int(start)}.wav")
            
            # 1. 1차 후보 구간 통오디오 추출
            self._extract_clip_audio(video_path, start, duration, raw_wav_path)
            
            # 2. Demucs로 순수 목소리(vocals.wav) 분리
            clean_vocals_path = self._separate_vocals_demucs(raw_wav_path, temp_audio_dir)

            # 3. 분리된 목소리 트랙으로 Whisper STT 수행
            stt_result = self.whisper_model.transcribe(clean_vocals_path, language="ko")
            spoken_text = stt_result.get("text", "").strip()

            # 4. 발화 감정 분석
            emotion_res = self.analyze_streamer_speech_emotion(spoken_text)
            speech_joy = emotion_res["joy_score"]

            # 최종 점수 계산 (1차 점수 70% + 2차 발화 점수 30%)
            final_score = round((stage1_score * 0.7) + (speech_joy * 0.3), 2)

            item = {
                "start_time": start,
                "end_time": end,
                "duration": duration,
                "stage1_chat_score": stage1_score,
                "streamer_speech_text": spoken_text if spoken_text else "(음성 발화 없음)",
                "streamer_speech_emotion": emotion_res["dominant_emotion"],
                "streamer_joy_score": speech_joy,
                "final_highlight_score": final_score
            }
            evaluated_clips.append(item)
            print(f" ➔ [{idx+1}/{len(candidates)}] {start}초~{end}초 | STT: \"{spoken_text[:25]}\" | 최종 점수: {final_score}")

        sorted_clips = sorted(evaluated_clips, key=lambda x: x["final_highlight_score"], reverse=True)
        final_selected = []
        accumulated_sec = 0.0

        for clip in sorted_clips:
            if len(final_selected) >= top_k:
                break
            if (accumulated_sec + clip["duration"]) <= max_total_seconds or len(final_selected) == 0:
                final_selected.append(clip)
                accumulated_sec += clip["duration"]

        final_selected = sorted(final_selected, key=lambda x: x["start_time"])
        for idx, c in enumerate(final_selected):
            c["rank"] = idx + 1

        final_payload = {
            "metadata": {
                "source_video": video_path,
                "top_k_limit": top_k,
                "max_duration_cap_sec": max_total_seconds,
                "total_highlights_count": len(final_selected),
                "total_highlight_duration_sec": round(accumulated_sec, 2)
            },
            "highlights": final_selected
        }

        with open(output_json, "w", encoding="utf-8") as jf:
            json.dump(final_payload, jf, ensure_ascii=False, indent=2)

        pd.DataFrame(final_selected).to_csv("final_highlight_candidates.csv", index=False, encoding="utf-8-sig")

        print("\n" + "=" * 70)
        print(f"✅ [최종 확정] 총 {len(final_selected)}개 클립 확정 (총 요약 길이: {accumulated_sec:.1f}초)")
        print(f" ➔ 결과 파일: '{output_json}', 'final_highlight_candidates.csv'")
        print("=" * 70)
        return final_selected

if __name__ == "__main__":
    refiner = WBBStage2Refinement()
    refiner.refine_candidates()