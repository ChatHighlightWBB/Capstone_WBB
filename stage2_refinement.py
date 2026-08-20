import os
import subprocess
from typing import Dict
import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import whisper


class WBBStage2RefinementEngine:
  """[설명] 와바바(WBB) 제안서 4.3 규격: Demucs 보컬 분리 + Whisper STT + KoBERT 2차 정밀 검증 엔진.

  1차 하이라이트 후보 클립에서 게임 소음을 제거하고 스트리머 목소리만 추출하여
  감정을 판정합니다.
  """

  def __init__(self, kobert_model_path: str = "./kobert_wbb_model"):
    print("🚀 [와바바 Stage 2 Engine] 2차 정밀 검증 AI 모델 로딩 중...")

    # 1. Whisper 모델 로드 (base보다 한국어 인식률이 월등히 높은 small 모델 사용)
    # GPU(CUDA) 가용 시 GPU로 자동 할당, 없을 시 CPU 모드 구동
    self.device = "cuda" if torch.cuda.is_available() else "cpu"
    self.whisper_model = whisper.load_model("small", device=self.device)

    # 2. KoBERT 모델 메모리 로드
    self.tokenizer = AutoTokenizer.from_pretrained(
        "monologg/kobert", trust_remote_code=True
    )
    self.kobert = AutoModelForSequenceClassification.from_pretrained(
        kobert_model_path, num_labels=7
    )
    self.kobert.eval()

    self.labels = {
        0: "기쁨/행복/환호",
        1: "당황/놀람",
        2: "분노/짜증",
        3: "슬픔/좌절",
        4: "혐오/불쾌",
        5: "공포/불안",
        6: "중립/일상",
    }

    # 게임 방송 특화 Whisper 사전 프롬프트 (인식률 향상 힌트)
    self.gaming_prompt = (
        "스트리머 게임 방송 실시간 대화, 배틀그라운드, 롤, 치지직, 유튜브, 감탄사,"
        " 비속어, 신조어, 헐, 대박, 레전드, 아악, 개웃기네, 미쳤다"
    )

  def extract_vocals_with_demucs(self, clip_path: str) -> str:
    """[핵심] Demucs AI를 실행하여 영상에서 총소리/배경음을 제거하고 스트리머 목소리(vocals.wav)만 추출합니다."""
    clip_name = os.path.splitext(os.path.basename(clip_path))[0]
    output_dir = "./temp_separated"
    vocal_path = os.path.join(
        output_dir, "htdemucs", clip_name, "vocals.wav"
    )

    # 이미 분리된 보컬 파일이 존재하면 재사용 (처리 속도 최적화)
    if os.path.exists(vocal_path):
      return vocal_path

    print(
        f"🎧 [Demucs 보컬 분리] '{clip_name}' 영상에서 배경음/효과음 제거"
        " 중..."
    )
    cmd = [
        "demucs",
        "--two-stems=vocals",  # 보컬과 배경음(No Vocals) 2개로만 고속 분리
        "-n",
        "htdemucs",  # 경량 고성능 기본 분리 모델
        "-o",
        output_dir,
        clip_path,
    ]

    try:
      subprocess.run(
          cmd,
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
      )
      if os.path.exists(vocal_path):
        print("✅ 보컬 분리 완료 (vocals.wav 확보)")
        return vocal_path
    except Exception as e:
      print(
          f"⚠️ Demucs 분리 실패 (원음으로 대체 진행): {str(e)}"
      )

    return clip_path  # 분리 실패 시 원본 영상 파일 경로 반환 (Fallback)

  def analyze_streamer_speech(self, clip_path: str) -> Dict:
    """[핵심] 보컬 분리 음성을 바탕으로 Whisper STT 및 KoBERT 2차 감정 검증 수행"""
    if not os.path.exists(clip_path):
      raise FileNotFoundError(f"'{clip_path}' 클립 파일이 없습니다.")

    # 1. Demucs를 통한 순수 목소리(vocals.wav) 추출
    audio_target = self.extract_vocals_with_demucs(clip_path)

    # 2. Whisper STT 실행 (프롬프트 주입 및 beam_size=3 설정으로 정확도 향상)
    print(
        f"🎙️ [Whisper STT] '{os.path.basename(audio_target)}' 음성 텍스트"
        " 변환 중..."
    )
    stt_result = self.whisper_model.transcribe(
        audio_target,
        language="ko",
        initial_prompt=self.gaming_prompt,
        beam_size=3,  # 문맥 탐색 정밀도 향상
        fp16=(self.device == "cuda"),
    )

    transcribed_text = stt_result.get("text", "").strip()

    if not transcribed_text:
      return {
          "clip_path": clip_path,
          "speech_text": "(음성 발화 없음)",
          "streamer_emotion_idx": 6,
          "streamer_emotion_name": self.labels[6],
          "streamer_emotion_score": 0.0,
          "emotion_strength": 0.0,
          "is_verified": False,
      }

    # 3. KoBERT 모델을 통한 감정 점수 산출
    inputs = self.tokenizer(
        transcribed_text,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=128,
    )

    with torch.no_grad():
      outputs = self.kobert(**inputs)
      probs = torch.softmax(outputs.logits, dim=1).squeeze().tolist()
      pred_idx = int(np.argmax(probs))

    # 감정 강도: 중립(6번)을 제외한 유의미 감정(0~5번) 확률의 합계
    emotion_strength = sum(probs[0:6])
    # 2차 검증 통과 기준: 일상 잡담(중립)이 아니고 뚜렷한 감정이 나타난 경우
    is_verified = emotion_strength > 0.45

    return {
        "clip_path": clip_path,
        "speech_text": transcribed_text,
        "streamer_emotion_idx": pred_idx,
        "streamer_emotion_name": self.labels[pred_idx],
        "streamer_emotion_score": round(float(probs[pred_idx] * 100), 2),
        "emotion_strength": round(float(emotion_strength), 4),
        "is_verified": is_verified,
    }


# 단독 검증 실행 루틴
if __name__ == "__main__":
  engine = WBBStage2RefinementEngine()

  TEST_CLIP_PATH = "./temp_clips/clip_test_1.mp4"

  if not os.path.exists(TEST_CLIP_PATH):
    print(f"⚠️ '{TEST_CLIP_PATH}' 파일이 없습니다. 'python ffmpeg_clipper.py'를 먼저 실행해 주세요.")
  else:
    result = engine.analyze_streamer_speech(TEST_CLIP_PATH)

    print("\n🎯 [개선된 2차 스트리머 발화 정밀 검증 결과]")
    print("=" * 75)
    print(f"🎬 검증 대상 클립: {result['clip_path']}")
    print(f"🗣️ 추출된 발화 내용: \"{result['speech_text']}\"")
    print(
        f"🎭 스트리머 감정 판정: [{result['streamer_emotion_idx']}]"
        f" {result['streamer_emotion_name']}"
    )
    print(f"📊 감정 확신도: {result['streamer_emotion_score']}%")
    print(f"🔥 감정 강도 (Non-Neutral Score): {result['emotion_strength']}")
    print(
        "✅ 2차 검증 판정:"
        f" {'[통과] 최종 하이라이트 확정' if result['is_verified'] else '[탈락] 단순 일상 대화'}"
    )