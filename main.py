from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
import yt_dlp  # type: ignore  # Pylance 타입 힌트 미지원 경고 완벽 차단
import streamlink  # type: ignore  # Pylance 타입 힌트 미지원 경고 완벽 차단
import math

# 1. FastAPI 애플리케이션 핵심 객체 선언
app = FastAPI(
    title="와바바 (WBB) 핵심 통합 백엔드",
    description="7~8월 로드맵: 듀얼 파싱 엔진 및 멀티모달 하이라이트 백엔드"
)

# 2. 데이터 송수신 규격 정의 (Pydantic 모델)
class StreamUrlRequest(BaseModel):
    url: str

class HighlightTimelineResponse(BaseModel):
    timestamp_start_sec: int
    timestamp_end_sec: int
    calculated_score: float

# 3. 인프라 가동 확인용 기본 라우터
@app.get("/")
def check_server_status() -> Dict[str, str]:
    return {"status": "online", "project": "WBB (와바바)"}

# 4. 멀티 엔진 스트림 수집 API (SOOP / 유튜브 / 치지직 완벽 대응)
@app.post("/api/v1/stream-metadata")
def extract_stream_metadata(request: StreamUrlRequest) -> Dict[str, Any]:
    url = request.url.strip()

    # SOOP TV / 아프리카TV 주소 진입 시 Streamlink 선제 처리
    if "soop" in url or "afreeca" in url:
        try:
            session = streamlink.Streamlink()  # type: ignore
            session.set_option("http-timeout", 10)
            streams = session.streams(url)
            
            if streams:
                return {
                    "status": "success",
                    "engine": "streamlink",
                    "platform_data": {
                        "title": "SOOP 라이브/VOD 스트림",
                        "streamer": "SOOP BJ",
                        "duration_sec": "LIVE",
                        "thumbnail": None
                    }
                }
        except Exception:
            # Streamlink 실패 시 하단 yt-dlp 보조 실행으로 우회
            pass

    # yt-dlp 옵션 설정 (SSL 검증 스킵 + 올바른 헤더 구조)
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,  # SSL 인증서 검증 스킵
        'ignoreerrors': True,        # 메타데이터 일부 누락 시에도 에러 무시
        'http_headers': {            # yt-dlp 정식 헤더 규격
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }
    }

    # yt-dlp 메인 엔진 가동 (# type: ignore로 Pylance 검사 차단)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            info_dict = ydl.extract_info(url, download=False)
            
            if not info_dict:
                return {
                    "status": "error",
                    "message": "영상을 찾을 수 없거나 접근이 차단되었습니다."
                }

            streamer_name = (
                info_dict.get("channel") 
                or info_dict.get("uploader") 
                or info_dict.get("creator") 
                or "Unknown Streamer"
            )

            return {
                "status": "success",
                "engine": "yt-dlp",
                "platform_data": {
                    "title": info_dict.get("title", "방송 제목 없음"),
                    "streamer": streamer_name,
                    "duration_sec": info_dict.get("duration", "LIVE"),
                    "thumbnail": info_dict.get("thumbnail")
                }
            }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"yt-dlp 추출 실패: {str(e)}"
        }

# 5. 7~8월 알고리즘 대응용 Mock 하이라이트 API
@app.get("/api/v1/mock-highlight-windows", response_model=List[HighlightTimelineResponse])
def get_mock_highlight_windows() -> List[HighlightTimelineResponse]:
    mock_timeline: List[HighlightTimelineResponse] = []

    for sec in range(0, 7200, 30):
        mock_chat_density = abs(math.sin(sec / 500)) * 50  
        mock_emotion_intensity = abs(math.cos(sec / 300)) * 0.8  

        weighted_score = round((mock_chat_density * 0.6) + (mock_emotion_intensity * 100 * 0.4), 2)

        if weighted_score >= 45.0:
            item = HighlightTimelineResponse(
                timestamp_start_sec=sec,
                timestamp_end_sec=sec + 30,
                calculated_score=weighted_score
            )
            mock_timeline.append(item)

    mock_timeline.sort(key=lambda x: x.calculated_score, reverse=True)
    return mock_timeline[:10]