import os
import re
from typing import List
from fastapi import FastAPI, HTTPException
import numpy as np
from pydantic import BaseModel
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# 1. FastAPI 애플리케이션 초기화
app = FastAPI(
    title="와바바(WBB) AI 분석 백엔드 API",
    description="KoBERT 7대 감정 분석 및 멀티모달 하이라이트 요약 백엔드",
    version="1.0.0",
)

# 2. 노션 공식 명세 기준 7대 감정 매핑 딕셔너리
OFFICIAL_EMOTION_LABELS = {
    0: "기쁨/행복/환호",
    1: "당황/놀람",
    2: "분노/짜증",
    3: "슬픔/좌절",
    4: "혐오/불쾌",
    5: "공포/불안",
    6: "중립/일상",
}

tokenizer = None
model = None


# 3. 서버 가동 시 KoBERT 모델 메모리 로드
@app.on_event("startup")
def load_ai_model():
  """FastAPI 백엔드 서버가 시작될 때 로컬 KoBERT 파인튜닝 모델을 메모리(RAM)에 로드합니다."""
  global tokenizer, model
  local_model_path = "./kobert_wbb_model"

  if not os.path.exists(local_model_path):
    print(f"⚠️ 경고: '{local_model_path}' 경로에 학습된 모델이 없습니다.")
    return

  print("🚀 [와바바 백엔드] 파인튜닝된 KoBERT AI 모델을 메모리에 로드 중...")
  try:
    tokenizer = AutoTokenizer.from_pretrained(
        "monologg/kobert", trust_remote_code=True
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        local_model_path, num_labels=7
    )
    model.eval()
    print("✅ KoBERT 모델 및 정밀 가드레일 엔진 로드 완료!")
  except Exception as e:
    print(f"❌ 모델 로드 중 에러 발생: {str(e)}")


# Pydantic 데이터 검증 규격
class ChatAnalyzeRequest(BaseModel):
  chat_messages: List[str]


class ChatEmotionResult(BaseModel):
  chat: str
  pred_label_idx: int
  pred_label_name: str
  confidence: float
  all_probabilities: List[float]


@app.get("/")
def read_root():
  return {
      "status": "online",
      "service": "와바바(WBB) 멀티모달 스트리밍 하이라이트 플랫폼",
      "model_loaded": model is not None,
  }


@app.post("/api/v1/analyze-chats", response_model=List[ChatEmotionResult])
def analyze_chat_emotions(payload: ChatAnalyzeRequest):
  """[핵심 API] KoBERT 추론 + 문장 부호 정규식 가드레일이 적용된 실시간 감정 분석 API."""
  global tokenizer, model

  if model is None or tokenizer is None:
    raise HTTPException(
        status_code=500, detail="AI 모델이 메모리에 로드되지 않았습니다."
    )

  results = []

  for chat in payload.chat_messages:
    chat_text = str(chat).strip()
    if not chat_text:
      continue

    # 1. KoBERT 모델 신경망 추론
    inputs = tokenizer(
        chat_text,
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

    # 2. 정규식을 통한 문장 부호 및 단독 특수문자 패턴 검사
    clean_text = re.sub(r"[^\w\s]", "", chat_text).strip()  # 특수문자 제거 텍스트
    only_punctuation = len(clean_text) == 0  # 텍스트 없이 순수 특수문자만 존재하는지 여부
    has_question = bool(re.search(r"\?+", chat_text))  # 물음표 포함 여부
    has_exclamation = bool(re.search(r"!+", chat_text))  # 느낌표 포함 여부

    # 3. [핵심] 정밀 가드레일 및 라벨/확률 보정 알고리즘
    # (A) 텍스트 없이 순수 '???' 나 '?' 만 있는 경우 -> [1] 당황/놀람 처리
    if only_punctuation and has_question:
      pred_idx = 1
      probs = [0.05, 0.85, 0.02, 0.02, 0.02, 0.02, 0.02]

    # (B) 텍스트 없이 순수 '!!!' 나 '!' 만 있는 경우 -> [0] 기쁨/환호 처리
    elif only_punctuation and has_exclamation:
      pred_idx = 0
      probs = [0.85, 0.05, 0.02, 0.02, 0.02, 0.02, 0.02]

    # (C) 텍스트 + 물음표 조합 (예: "와 이건 오바 아니냐??", "대박이야??") -> [1] 당황/놀람
    elif has_question and any(
        kw in chat_text
        for kw in ["오바", "진짜", "대박", "뭐하", "이게", "헐", "엥", "레전드", "나가"]
    ):
      pred_idx = 1
      probs[1] = max(probs[1], 0.75)

    # (D) 단어별 맥락 보정 (예: "대박이네", "대박!") -> [0] 기쁨/환호
    elif "대박" in chat_text and not has_question:
      pred_idx = 0
      probs[0] = max(probs[0], 0.85)

    # (E) 명확한 부정 키워드 가드레일
    elif any(kw in chat_text for kw in ["빡치", "뇌절", "개못하"]):
      pred_idx = 2  # 분노
      probs[2] = max(probs[2], 0.80)
    elif any(kw in chat_text for kw in ["더럽", "찝찝", "토나오", "극혐"]):
      pred_idx = 4  # 혐오
      probs[4] = max(probs[4], 0.80)

    confidence = float(probs[pred_idx] * 100)

    results.append(
        ChatEmotionResult(
            chat=chat_text,
            pred_label_idx=pred_idx,
            pred_label_name=OFFICIAL_EMOTION_LABELS[pred_idx],
            confidence=round(confidence, 2),
            all_probabilities=[round(float(p), 4) for p in probs],
        )
    )

  return results