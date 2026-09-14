"""
=============================================================================
[와바바(WBB)] AI 분석 백엔드 API (FastAPI)
- 담당자: 송태섭 (책임개발자)
- 핵심 패치: 
  1. 원본 KoBERT NLP 정규식 가드레일 로직 완벽 유지
  2. React 프론트엔드 연동을 위한 CORS 미들웨어 추가
  3. 제안서 스펙 변경 반영: yt-dlp 기반 프록시 영상 다운로드 해상도 480p 상향 적용
  4. UUID가 적용된 1~5단계 멀티모달 하이라이트 파이프라인 연결
=============================================================================
"""
import os
import re
import subprocess
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from pydantic import BaseModel
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# UUID 기반 전체 파이프라인 임포트
from highlight_pipeline import WBBAutoHighlightPipeline

# 1. FastAPI 애플리케이션 초기화
app = FastAPI(
    title="와바바(WBB) AI 분석 백엔드 API",
    description="KoBERT 7대 감정 분석 및 멀티모달 하이라이트 요약 백엔드",
    version="1.0.0",
)

# [추가] React 프론트엔드 연동을 위한 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
        tokenizer = AutoTokenizer.from_pretrained("monologg/kobert", trust_remote_code=True)
        model = AutoModelForSequenceClassification.from_pretrained(local_model_path, num_labels=7)
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

# 프론트엔드 연동용 URL 분석 DTO
class VideoAnalyzeRequest(BaseModel):
    video_url: str

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "와바바(WBB) 멀티모달 스트리밍 하이라이트 플랫폼",
        "model_loaded": model is not None,
    }


# =====================================================================
# [유지됨] 송태섭 님이 작성하신 KoBERT 추론 + 문장 부호 정규식 가드레일 API
# =====================================================================
@app.post("/api/v1/analyze-chats", response_model=List[ChatEmotionResult])
def analyze_chat_emotions(payload: ChatAnalyzeRequest):
    global tokenizer, model

    if model is None or tokenizer is None:
        raise HTTPException(status_code=500, detail="AI 모델이 메모리에 로드되지 않았습니다.")

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
        clean_text = re.sub(r"[^\w\s]", "", chat_text).strip()
        only_punctuation = len(clean_text) == 0
        has_question = bool(re.search(r"\?+", chat_text))
        has_exclamation = bool(re.search(r"!+", chat_text))

        # 3. [핵심] 정밀 가드레일 및 라벨/확률 보정 알고리즘
        if only_punctuation and has_question:
            pred_idx = 1
            probs = [0.05, 0.85, 0.02, 0.02, 0.02, 0.02, 0.02]
        elif only_punctuation and has_exclamation:
            pred_idx = 0
            probs = [0.85, 0.05, 0.02, 0.02, 0.02, 0.02, 0.02]
        elif has_question and any(kw in chat_text for kw in ["오바", "진짜", "대박", "뭐하", "이게", "헐", "엥", "레전드", "나가"]):
            pred_idx = 1
            probs[1] = max(probs[1], 0.75)
        elif "대박" in chat_text and not has_question:
            pred_idx = 0
            probs[0] = max(probs[0], 0.85)
        elif any(kw in chat_text for kw in ["빡치", "뇌절", "개못하"]):
            pred_idx = 2
            probs[2] = max(probs[2], 0.80)
        elif any(kw in chat_text for kw in ["더럽", "찝찝", "토나오", "극혐"]):
            pred_idx = 4
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

# =====================================================================
# [신규 추가] 프론트엔드에서 영상 URL을 던졌을 때 실행되는 메인 파이프라인 API
# =====================================================================
@app.post("/api/v1/analyze-video")
def analyze_streaming_video(payload: VideoAnalyzeRequest):
    """프록시 기반 480p 영상 다운로드 및 1~5단계 자동화 파이프라인 실행 API"""
    target_url = payload.video_url
    
    os.makedirs("./test_videos", exist_ok=True)
    download_path = "./test_videos/downloaded_proxy_480p.mp4"

    print(f"\n📥 [수집] URL 파싱 시작: {target_url}")
    
    # [수정됨] yt-dlp 해상도 480p 고정 다운로드 로직 적용
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
        "-o", download_path,
        target_url
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ [수집] 480p 프록시 영상 다운로드 완료")
    except subprocess.CalledProcessError:
        print("⚠️ yt-dlp 추출 실패, Streamlink 듀얼 파싱(보조 엔진) 가동이 필요합니다.")
        raise HTTPException(status_code=400, detail="영상 다운로드 실패 (비공개 영상이거나 지원하지 않는 플랫폼입니다)")

    print("🚀 [분석] 멀티모달 하이라이트 파이프라인(1~5단계) 가동...")
    
    # 앞서 수정했던 UUID 기반 안전한 파이프라인 가동
    pipeline = WBBAutoHighlightPipeline(target_video_path=download_path)
    result = pipeline.run_full_pipeline()

    return {
        "status": "success",
        "message": "480p 영상 분석 및 하이라이트 추출 완료",
        "data": result
    }