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
import sys
import json
import subprocess
import torch
import pandas as pd
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from cancel_utils import check_cancel  # [분석 취소] 후보마다 사용자가 멈췄는지 확인

KOBERT_TOKENIZER_ID = "monologg/kobert"

# 2차 검증(Demucs+Whisper)은 후보 1개당 약 50초(CPU)이고 그중 Demucs 가 86~88%.
# 최종은 최대 10개라 1차 점수 상위 12개만 검증(2개 여유).
# 2026-10-13 토크 방송 13개 후보 시험에서 K=10·11·12 모두 최종 10개 동일.
# 발화 기쁨이 커서 11·12등이 뒤집힐 여지는 남김.
# 환경변수 STAGE2_TOP_K 로 바꿀 수 있고, 0 이하면 전부 검증합니다.
STAGE2_TOP_K_DEFAULT = 12


def _select_stage2_candidates(candidates, top_k) -> list:
    """
    1차 후보 중 2차 검증에 보낼 후보만 고릅니다.
    - top_k 가 0 이하이거나 후보 수가 top_k 이하면 그대로 돌려줍니다(전부 검증).
    - 아니면 1차 점수(window_score)가 큰 순으로 top_k 개를 고르고(점수가 같으면
      앞 시각 우선), 원래처럼 시간 순(start_time)으로 다시 정렬해 돌려줍니다.
    """
    if top_k <= 0 or len(candidates) <= top_k:
        return candidates
    ranked = sorted(candidates, key=lambda c: (-c["window_score"], c["start_time"]))
    return sorted(ranked[:top_k], key=lambda c: c["start_time"])


def load_kobert_tokenizer():
    """monologg/kobert 토크나이저 로드: 로컬 HF 캐시 우선, 캐시에 없을 때만 다운로드"""
    try:
        return AutoTokenizer.from_pretrained(KOBERT_TOKENIZER_ID, trust_remote_code=True, local_files_only=True)
    except Exception:
        return AutoTokenizer.from_pretrained(KOBERT_TOKENIZER_ID, trust_remote_code=True)


def _collapse_repeats(text, max_repeat=3):
    """
    Whisper가 같은 단어를 끝없이 반복하는 경우("아이고 아이고 아이고 ...")를 정리합니다.
    공백으로 나눈 단어 기준으로, 앞뒤 문장부호를 뺀 같은 단어가 연달아 max_repeat 번을
    넘게 나오면 max_repeat 번까지만 남깁니다. (반복이 감정 분석과 화면 표시를 망치지 않게)
    """
    punct = ".,!?~…·'\"()[]{}<>-:;"
    result = []
    prev_key = None
    run = 0
    for word in text.split():
        key = word.strip(punct) or word  # 문장부호만 있는 단어는 그대로 비교
        if key == prev_key:
            run += 1
        else:
            prev_key = key
            run = 1
        if run <= max_repeat:
            result.append(word)
    return " ".join(result)


class WBBStage2Refinement:
    def __init__(self, model_dir: str = "./kobert_wbb_model"):
        print("🧠 [1/3] 2차 검증용 KoBERT 및 Whisper STT 모델 로딩 중...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.emotion_labels = ["기쁨", "당황", "분노", "슬픔", "혐오", "공포", "평상"]

        if os.path.exists(model_dir) and os.path.isdir(model_dir):
            # 학습 때 monologg/kobert 에 채팅 표현 9개(ㅋㅋㅋㅋ, ㄹㅈㄷ 등)를 추가한 토크나이저를 썼음.
            # 추가 토큰이 든 모델 폴더면 그 토크나이저를 써야 학습 때와 같게 읽음(2026-10-12 검증셋 macro-F1 0.410→0.449).
            # 옛 모델 폴더(추가 토큰 없음, 저장된 tokenizer.json 이 한글을 [UNK] 로 깨뜨림)는 monologg 유지.
            if os.path.exists(os.path.join(model_dir, "added_tokens.json")):
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True, local_files_only=True)
                    print(f"🔤 KoBERT 토크나이저: 모델 폴더(추가 토큰 {len(self.tokenizer) - 8002}개)")
                except Exception as e:
                    print(f"⚠️ 모델 폴더 토크나이저 불러오기 실패 → monologg/kobert 로 대체(학습 때와 달라 감정 정확도가 떨어질 수 있음): {e}")
                    self.tokenizer = load_kobert_tokenizer()
            else:
                self.tokenizer = load_kobert_tokenizer()
                print("🔤 KoBERT 토크나이저: monologg/kobert")
            try:
                self.kobert = AutoModelForSequenceClassification.from_pretrained(model_dir)
            except Exception:
                self.kobert = AutoModelForSequenceClassification.from_pretrained("skt/kobert-base-v1", num_labels=7)
        else:
            self.tokenizer = AutoTokenizer.from_pretrained("skt/kobert-base-v1", trust_remote_code=True)
            self.kobert = AutoModelForSequenceClassification.from_pretrained("skt/kobert-base-v1", num_labels=7)

        self.kobert.to(self.device)
        self.kobert.eval()
        self.vocab_size = getattr(self.kobert.config, "vocab_size", 8002)

        import whisper
        self.whisper_model = whisper.load_model("base", device=self.device)
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
            # [수정] "demucs"를 명령어 이름으로 바로 부르면, venv/Scripts가
            # PATH에 없는 환경(예: run.ps1이 venv의 python.exe를 직접 지정해서
            # 실행하는 경우)에서 WinError 2(파일을 찾을 수 없음)가 납니다.
            # sys.executable(지금 실행 중인 파이썬)을 통해 -m demucs로 부르면
            # PATH 상태와 무관하게 항상 정확한 venv의 demucs를 찾습니다.
            cmd = [
                sys.executable, "-m", "demucs",
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
            return {"dominant_emotion": "평상", "joy_score": 0.0}

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
                          output_json: str = "final_highlight_candidates.json",
                          cancel_event=None):
        if not os.path.exists(stage1_json):
            raise FileNotFoundError(f"'{stage1_json}' 파일이 없습니다.")

        with open(stage1_json, "r", encoding="utf-8") as f:
            stage1_data = json.load(f)

        candidates = stage1_data.get("candidate_clips", [])
        if not candidates:
            print("⚠️ 1차 후보 클립이 비어 있습니다.")
            return []

        # 2차 검증은 후보마다 오래 걸리므로 1차 점수 상위 K개만 보냅니다.
        # STAGE2_TOP_K 가 숫자가 아니면 기본값을 쓰고, 0 이하면 전부 검증합니다.
        try:
            stage2_top_k = int(os.getenv("STAGE2_TOP_K", STAGE2_TOP_K_DEFAULT))
        except ValueError:
            stage2_top_k = STAGE2_TOP_K_DEFAULT
        original_count = len(candidates)
        candidates = _select_stage2_candidates(candidates, stage2_top_k)
        if len(candidates) < original_count:
            print(f" ➔ 2차 검증: 1차 상위 {stage2_top_k}개만 ({original_count}개 중 {original_count - len(candidates)}개 제외)")

        print("=" * 70)
        print(f"🎙️ [2차 정밀 검증 및 Top-{top_k} 선별 시작] 총 {len(candidates)}개 후보 대상")
        print("=" * 70)

        evaluated_clips = []
        temp_audio_dir = "./temp_separated"
        os.makedirs(temp_audio_dir, exist_ok=True)

        for idx, clip in enumerate(candidates):
            # [분석 취소] 후보 1개에 수십 초가 걸려서, 후보마다 시작 전에 멈췄는지 확인합니다(None 이면 그냥 지나감).
            check_cancel(cancel_event)
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
            # condition_on_previous_text=False, temperature=0: 이전 문장에 끌려가 외국어가 섞이는 현상을 줄입니다.
            # 10-11 게임 방송 4구간 시험에서 외국 문자 15.9% → 0%, 시간 87초 → 27초.
            stt_result = self.whisper_model.transcribe(clean_vocals_path, language="ko",
                                                       condition_on_previous_text=False, temperature=0)
            spoken_text = stt_result.get("text", "").strip()
            spoken_text = _collapse_repeats(spoken_text)

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