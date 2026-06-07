from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import yt_dlp
import streamlink
import math

# 1. FastAPI 애플리케이션 핵심 객체 선언
app = FastAPI(
    title="와바바 (WBB) 핵심 통합 백엔드",
    description="6월 로드맵: 듀얼 파싱 엔진 및 병렬 개발용 mock 하이라이트 API"
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
def check_server_status():
    return {"status": "online", "project": "WBB (와바바)"}

# 4. 확정된 설계 원칙 4번: 멀티 엔진 스트림 수집 API (괴물쥐 VOD 파싱 성공본)
@app.post("/api/v1/stream-metadata")
def extract_stream_metadata(request: StreamUrlRequest):
    url = request.url
    ydl_opts = {'skip_download': True, 'quiet': True}
    
    # SOOP TV / 아프리카TV 주소 진입 시 보조 엔진 우회 로직
    if "soop" in url or "afreeca" in url:
        try:
            session = streamlink.Streamlink()
            streams = session.streams(url)
            return {
                "status": "success",
                "engine": "streamlink",
                "platform_data": {"title": "SOOP 라이브 스트림", "streamer": "SOOP BJ", "duration_sec": "LIVE", "thumbnail": None}
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
            
    # 유튜브 / 치지직 주소 진입 시 메인 엔진 가동 및 null 버그 보완 로직
    else:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                streamer_name = info_dict.get("channel") or info_dict.get("uploader") or info_dict.get("creator")
                
                return {
                    "status": "success",
                    "engine": "yt-dlp",
                    "platform_data": {
                        "title": info_dict.get("title"),
                        "streamer": streamer_name,
                        "duration_sec": info_dict.get("duration"),
                        "thumbnail": info_dict.get("thumbnail")
                    }
                }
        except Exception as e:
            return {"status": "error", "message": f"yt-dlp 파싱 실패: {str(e)}"}

# 5. 확정된 설계 원칙 5번: 7~8월 알고리즘 선제 대응을 위한 Mock 하이라이트 API
@app.get("/api/v1/mock-highlight-windows", response_model=List[HighlightTimelineResponse])
def get_mock_highlight_windows():
    """
    [설명] 팀장님이 데이터셋을 크롤링하여 KoBERT 모델을 준비하는 동안,
    나머지 팀원(프론트엔드 담당)이 요약 리포트 UI 대시보드와 Chart.js 연동을 
    막힘없이 개발할 수 있도록 30초 Sliding Window 구조의 가짜 점수를 계산해 반환하는 인프라입니다.
    """
    mock_timeline = []
    
    # 2시간(7200초) 분량을 30초 단위 슬라이딩 윈도우로 시뮬레이션하는 루프
    for sec in range(0, 7200, 30):
        # 수학 함수를 활용하여 시각화 그래프 렌더링에 적합한 연속적인 난수 피크 생성
        mock_chat_density = abs(math.sin(sec / 500)) * 50  
        mock_emotion_intensity = abs(math.cos(sec / 300)) * 0.8  
        
        # 제안서 기준 가중치 결합 알고리즘 선제 공식 적용 (채팅 화력 60% + 감정 밀도 40%)
        weighted_score = round((mock_chat_density * 0.6) + (mock_emotion_intensity * 100 * 0.4), 2)
        
        # 기준점(Adaptive Threshold) 45점 이상만 하이라이트 후보군으로 필터링
        if weighted_score >= 45.0:
            mock_timeline.append({
                "timestamp_start_sec": sec,
                "timestamp_end_sec": sec + 30,
                "calculated_score": weighted_score
            })
            
    # 정렬 연산 수행 후 상위 10개 핵심 클립만 확정하여 반환
    mock_timeline.sort(key=lambda x: x["calculated_score"], reverse=True)
    return mock_timeline[:10]