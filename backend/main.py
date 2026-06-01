from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime

app = FastAPI(
    title="와바바 (WBB) API 서버",
    description="KoBERT와 PP-OCRv3를 활용한 멀티모달 분석 기반 스트리밍 하이라이트 요약 플랫폼 API",
    version="1.0.0"
)

# --- 1. 요청 데이터 규격 정의 (Pydantic 모델) ---
class AnalyzeRequest(BaseModel):
    video_url: HttpUrl  # 사용자가 입력한 스트리밍 영상 URL

# --- 2. 응답 데이터 규격 정의 (합의된 Dummy JSON 스펙 반영) ---
class VideoInfo(BaseModel):
    video_id: str
    platform: str
    status: str
    total_duration_sec: int

class TimeSeriesData(BaseModel):
    timestamp: str
    chat_count: int
    kobert_score: float
    visual_score: float
    librosa_energy: float
    is_reaction_peak: bool
    top_keywords: List[str]

class FinalHighlight(BaseModel):
    rank: int
    start_time: str
    end_time: str
    highlight_score: float
    summary_reason: str
    streamer_stt_text: str
    streamer_emotion: str
    clip_url: str

class AnalyzeResponse(BaseModel):
    video_info: VideoInfo
    time_series_data: List[TimeSeriesData]
    final_highlights: List[FinalHighlight]


# --- 3. 백그라운드에서 가동될 AI 분석 파이프라인 시뮬레이터 ---
def fake_ai_analysis_task(video_url: str):
    """
    [6월 개발 목표] yt-dlp + Streamlink 파이프라인이 들어올 자리입니다.
    현재는 백그라운드 가동 로그만 출력하는 시뮬레이터 역할을 합니다.
    """
    print(f"[AI 분석 시작] 타겟 URL: {video_url}")
    print("[1차 분석 진행 중] 360p 프록시 다운로드 및 PP-OCRv3, KoBERT, Librosa 가동...")
    print("[2차 분석 진행 중] 후보 구간 대상 Demucs 목소리 분리 및 Whisper STT 정밀 검증...")
    print("[분석 완료] MongoDB Atlas에 결과 적재 완료.")


# --- 4. API 엔드포인트 구현 ---

@app.post("/api/v1/analyze", response_model=AnalyzeResponse, status_code=202)
async def start_analysis(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    [POST /analyze] 영상 요약 분석 요청 엔드포인트
    대용량 영상 처리를 위해 비동기 백그라운드 태스크로 AI 엔진을 구동하고,
    프론트엔드 유저 인터페이스(UI) 연결을 위해 즉시 합의된 구조의 가짜 데이터를 반환합니다.
    """
    # 1. URL 식별 및 플랫폼 자동 감지 파싱 로직 (초안)
    url_str = str(request.video_url)
    if "youtube.com" in url_str or "youtu.be" in url_str:
        platform = "youtube"
    elif "chzzk.naver.com" in url_str:
        platform = "chzzk"
    elif "sooply.co.kr" in url_str or "afreecatv.com" in url_str:
        platform = "soop"
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 영상 플랫폼 URL입니다.")

    # 2. AI 분석 작업을 백그라운드 태스크로 등록 (서버 다운 방지)
    background_tasks.add_task(fake_ai_analysis_task, url_str)

    # 3. 합의된 구조의 가짜 데이터 즉시 리턴 (프론트엔드와 병렬 개발 가능)
    return {
        "video_info": {
            "video_id": "wbb_sample_20260601",
            "platform": platform,
            "status": "ANALYZING",  # 현재 분석 중임을 표시
            "total_duration_sec": 7200  # 예시: 2시간
        },
        "time_series_data": [
            {
                "timestamp": "00:00:30",
                "chat_count": 150,
                "kobert_score": 0.88,
                "visual_score": 0.75,
                "librosa_energy": 0.82,
                "is_reaction_peak": True,
                "top_keywords": ["대박", "ㅋㅋㅋ", "헉"]
            }
        ],
        "final_highlights": [
            {
                "rank": 1,
                "start_time": "01:20:10",
                "end_time": "01:21:40",
                "highlight_score": 0.95,
                "summary_reason": "스트리머 리액션 + 시청자 채팅 화력 집중",
                "streamer_stt_text": "와! 이걸 이렇게 깬다고? 진짜 말도 안 돼!",
                "streamer_emotion": "기쁨",
                "clip_url": "/api/v1/clips/uuid_01.mp4"
            }
        ]
    }

@app.get("/api/v1/analyze/{video_id}", response_model=AnalyzeResponse)
async def get_analysis_result(video_id: str):
    """
    [GET /analyze/{video_id}] 분석 결과 조회 엔드포인트
    추후 MongoDB Atlas와 연동되어 실제 저장된 데이터를 가져오게 됩니다.
    """
    # 임시 조회 기능 (우선 COMPLETED 상태의 더미 데이터 반환)
    return {
        "video_info": {
            "video_id": video_id,
            "platform": "chzzk",
            "status": "COMPLETED",
            "total_duration_sec": 7200
        },
        "time_series_data": [
            {
                "timestamp": "00:00:30",
                "chat_count": 150,
                "kobert_score": 0.88,
                "visual_score": 0.75,
                "librosa_energy": 0.82,
                "is_reaction_peak": True,
                "top_keywords": ["대박", "ㅋㅋㅋ", "헉"]
            }
        ],
        "final_highlights": [
            {
                "rank": 1,
                "start_time": "01:20:10",
                "end_time": "01:21:40",
                "highlight_score": 0.95,
                "summary_reason": "스트리머 리액션 + 시청자 채팅 화력 집중",
                "streamer_stt_text": "와! 이걸 이렇게 깬다고? 진짜 말도 안 돼!",
                "streamer_emotion": "기쁨",
                "clip_url": "/api/v1/clips/uuid_01.mp4"
            }
        ]
    }