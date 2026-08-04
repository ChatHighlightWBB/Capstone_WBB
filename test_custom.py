import re
import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def load_model():
  """[설명] 로컬 디렉토리에 저장된 KoBERT 파인튜닝 모델을 로드합니다."""
  model_path = "./kobert_wbb_model"
  print("🚀 [와바바 AI] 로컬 KoBERT 모델을 로딩 중입니다...")
  tokenizer = AutoTokenizer.from_pretrained(
      "monologg/kobert", trust_remote_code=True
  )
  model = AutoModelForSequenceClassification.from_pretrained(
      model_path, num_labels=7
  )
  model.eval()
  print("✅ 모델 로드 완료!\n")
  return tokenizer, model


def analyze_custom_chat_advanced(text, tokenizer, model):
  """[설명] 문장 부호(?, !) 및 문맥 패턴을 결합하여 감정을 정밀 추론하는 함수."""
  OFFICIAL_EMOTION_LABELS = {
      0: "기쁨/행복/환호",
      1: "당황/놀람",
      2: "분노/짜증",
      3: "슬픔/좌절",
      4: "혐오/불쾌",
      5: "공포/불안",
      6: "중립/일상",
  }

  # 1. KoBERT 순수 추론 연산
  inputs = tokenizer(
      text,
      return_tensors="pt",
      truncation=True,
      padding="max_length",
      max_length=64,
  )

  with torch.no_grad():
    outputs = model(**inputs)
    logits = outputs.logits
    probs = torch.softmax(logits, dim=1).squeeze().tolist()
    pred_idx = int(np.argmax(probs))

  # 2. 문장 부호 감지
  has_question = bool(re.search(r"\?+", text))  # 물음표 ? 포함 여부
  has_exclamation = bool(re.search(r"!+", text))  # 느낌표 ! 포함 여부

  # 3. [핵심] 문장 부호 및 문맥 감지형 가드레일 로직
  # (1) 물음표(?)가 포함된 경우 -> 당황/놀람(1) 또는 중립 질문으로 유도
  if has_question:
    if any(
        kw in text
        for kw in ["나가", "진짜", "뭐하", "이게", "헐", "엥", "레전드"]
    ):
      pred_idx = 1  # [1] 당황/놀람으로 교정
      probs[1] = max(probs[1], 0.75)

  # (2) "나가" 단어 처리
  elif "나가" in text:
    if has_exclamation or "아" in text or "홍명보" in text:
      pred_idx = 4  # [4] 혐오/불쾌 ("아 나가!!", "홍명보 나가")
      probs[4] = max(probs[4], 0.80)
    else:
      pred_idx = 2  # [2] 분노/짜증 ("나가")
      probs[2] = max(probs[2], 0.70)

  # (3) 명확한 키워드 룰 적용
  elif any(kw in text for kw in ["빡치", "뇌절", "개못하"]):
    pred_idx = 2  # 분노
    probs[2] = max(probs[2], 0.80)
  elif any(kw in text for kw in ["더럽", "찝찝", "토나오", "극혐"]):
    pred_idx = 4  # 혐오
    probs[4] = max(probs[4], 0.80)
  elif any(kw in text for kw in ["ㅋㅋㅋㅋ", "ㅋㅋㅋ", "개웃기", "대박"]):
    pred_idx = 0  # 기쁨
    probs[0] = max(probs[0], 0.80)

  confidence = probs[pred_idx] * 100
  return pred_idx, OFFICIAL_EMOTION_LABELS[pred_idx], confidence


if __name__ == "__main__":
  tokenizer, model = load_model()
  print("💬 문장 부호(?, !) 감지형 대화 테스트 (종료: 'exit')")
  print("=" * 60)

  while True:
    user_input = input("\n입력할 채팅 > ").strip()
    if user_input.lower() in ["exit", "종료", "q"]:
      print("테스트를 종료합니다.")
      break

    if not user_input:
      continue

    idx, name, score = analyze_custom_chat_advanced(
        user_input, tokenizer, model
    )
    print(f" ➔ 분석 결과: [{idx}] {name} (확신도: {score:.2f}%)")