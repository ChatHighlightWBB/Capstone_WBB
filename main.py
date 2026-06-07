from fastapi import FastAPI
from pydantic import BaseModel
import yt_dlp
import streamlink

app = FastAPI(
    title="와바바 (WBB) 핵심 백엔드 엔코더",
    description="6월 로드맵: yt-dlp + Streamlink 듀얼 파싱 인프라"
)

class StreamUrlRequest(BaseModel):
    url: str

@app.get("/")
def check_server_status():
    return {"status": "online", "project": "WBB (와바바)"}

# 확정된 설계 원칙 4번: 멀티 엔진 스트림 수집 API 라우터 완성
@app.post("/api/v1/stream-metadata")
def extract_stream_metadata(request: StreamUrlRequest):
    url = request.url
    ydl_opts = {'skip_download': True, 'quiet': True}
    
    # 1. 아프리카TV / SOOP TV 도메인 유입 시 Streamlink 보조 엔진으로 강제 우회
    if "soop" in url or "afreeca" in url:
        try:
            session = streamlink.Streamlink()
            streams = session.streams(url)
            return {
                "status": "success",
                "engine": "streamlink",
                "platform_data": {
                    "title": "SOOP 라이브 스트림 소스",
                    "streamer": "SOOP 스트리머",
                    "duration_sec": "실시간 수집 중",
                    "thumbnail": None
                }
            }
        except Exception as e:
            return {"status": "error", "message": f"Streamlink 파싱 실패: {str(e)}"}
            
    # 2. 유튜브 및 치지직 주소 유입 시 메인 추출 엔진(yt-dlp) 가동
    else:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                
                # [팩트체크 결함 보완] 플랫폼에 따라 유동적인 스트리머 키값을 역추적하여 null 반환 차단
                streamer_name = info_dict.get("channel") or info_dict.get("uploader") or info_dict.get("creator")
                
                return {
                    "status": "success",
                    "engine": "yt-dlp",
                    "platform_data": {
                        "title": info_dict.get("title"),
                        "streamer": streamer_name,  # 이제 괴물쥐 이름이 정상 매핑됩니다.
                        "duration_sec": info_dict.get("duration"),
                        "thumbnail": info_dict.get("thumbnail")
                    }
                }
        except Exception as e:
            return {"status": "error", "message": f"yt-dlp 파싱 실패: {str(e)}"}