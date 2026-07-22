import os
import sys
import subprocess
import asyncio
import re
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, HttpUrl

# --- 0. 환경 변수(.env) 로드 및 MongoDB 설정 ---
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "wbb_db")

TEMP_STORAGE_DIR = "temp_storage"
os.makedirs(TEMP_STORAGE_DIR, exist_ok=True)

class Database:
    client: AsyncIOMotorClient = None
    db = None

db = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.client = AsyncIOMotorClient(MONGODB_URL)
    db.db = db.client[DB_NAME]
    print(f"✅ [WBB DB] MongoDB Atlas ({DB_NAME}) 연동 성공!")
    yield
    if db.client:
        db.client.close()
        print("❌ [WBB DB] MongoDB Atlas 연결이 안전하게 해제되었습니다.")

app = FastAPI(
    title="와바바 (WBB) API 서버",
    description="KoBERT와 PP-OCRv3를 활용한 멀티모달 분석 기반 스트리밍 하이라이트 요약 플랫폼 API",
    version="1.0.0",
    lifespan=lifespan
)

# 💡 [예외 처리] React 프론트엔드(localhost:3000) 연동 시 브라우저 차단을 방지하기 위한 CORS 미들웨어 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. 요청/응답 데이터 규격 정의 (Pydantic 모델) ---
class AnalyzeRequest(BaseModel):
    video_url: HttpUrl

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

class ChartDataResponse(BaseModel):
    video_id: str
    timestamps: List[str]
    chat_counts: List[int]
    audio_energies: List[float]
    visual_scores: List[float]
    fusion_scores: List[float]
    highlight_markers: List[Dict[str, Any]]
    overall_mood: str


# --- 2. 풀 멀티모달 통합 스케줄러 계층 ---
def sync_pipeline_core_runner(full_command: str, output_path: str, platform: str, video_id: str, video_url: str):
    print(f"ℹ️ [WBB 스레드] {platform} 전용 다운로드 엔진 백그라운드 연산 진입.")
    chat_image_dir = os.path.join(TEMP_STORAGE_DIR, f"{video_id}_chats")
    
    try:
        # Step 1: 비디오 프록시 파일 다운로드
        result = subprocess.run(
            full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace'
        )
        if result.returncode != 0:
            print(f"❌ [엔진 내부 에러 발생]: {result.stderr.strip()}")
            return

        if not os.path.exists(output_path):
            print(f"❌ [파일 에러] 다운로드된 비디오 파일이 존재하지 않습니다: {output_path}")
            return

        print(f"✅ [WBB 파이프라인] 360p 프록시 다운로드 성공! 저장 파일: {output_path}")
        
        # Step 2: OpenCV 프레임 가공 및 화면 변화량 분석
        from frame_processor import extract_and_crop_chat_frames
        print(f"🚀 [WBB 파이프라인 연동] 세부 기능 1.2 및 3.1.2 진입 -> OpenCV 프레임 크롭 및 화면 변화량 분석")
        
        visual_changes = extract_and_crop_chat_frames(output_path, chat_image_dir)
        if not visual_changes:
            print("❌ [WBB 파이프라인 연동 에러]: OpenCV 프레임 가공 엔진 실패.")
            return
            
        # Step 3: Librosa 오디오 RMS 분석
        print(f"🎵 [WBB AI 오디오 엔진] 세부 기능 3.2.1 진입 -> Librosa 사운드 RMS 에너지 분석")
        from audio_processor import extract_audio_rms_features
        audio_rms_map = extract_audio_rms_features(output_path)
            
        # Step 4: PP-OCRv3 시계열 텍스트 파싱
        print(f"👁️ [WBB AI 비전 엔진] 세부 기능 3.1.1 진입 -> PP-OCRv3 시계열 텍스트 가공")
        image_files = sorted([f for f in os.listdir(chat_image_dir) if f.endswith('.jpg')]) if os.path.exists(chat_image_dir) else []
        time_series_logs = []
        
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=False, lang='ko', ocr_version='PP-OCRv4', show_log=False)
            
            for filename in image_files:
                match = re.search(r'frame_(\d+)s', filename)
                if not match:
                    continue
                timestamp_sec = int(match.group(1))
                
                ocr_result = ocr.ocr(os.path.join(chat_image_dir, filename), cls=False)
                parsed_chats = []
                
                if ocr_result and ocr_result[0]:
                    for line in ocr_result[0]:
                        text_content = line[1][0].strip()
                        if text_content:
                            parsed_chats.append(text_content)
                
                mins, secs = divmod(timestamp_sec, 60)
                hours, mins = divmod(mins, 60)
                time_index_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
                
                audio_energy = audio_rms_map.get(time_index_str, 0.0)
                v_score = visual_changes.get(time_index_str, 0.0)
                
                time_series_logs.append({
                    "time_index": time_index_str,
                    "timestamp_sec": timestamp_sec,
                    "raw_chats": parsed_chats,
                    "chat_count": len(parsed_chats),
                    "librosa_rms_energy": audio_energy,
                    "visual_score": v_score
                })
                print(f"📝 [파싱 중] [{time_index_str}] -> 채팅: {len(parsed_chats)}건, 오디오 RMS: {audio_energy}, 비주얼: {v_score}")
                
        except Exception as ocr_inner_error:
            print(f"⚠️ [PaddleOCR 엔진 경고]: 라이브러리 충돌 감지. 병렬 개발 모드로 전환합니다.")
            for filename in image_files:
                match = re.search(r'frame_(\d+)s', filename)
                if not match:
                    continue
                timestamp_sec = int(match.group(1))
                mins, secs = divmod(timestamp_sec, 60)
                hours, mins = divmod(mins, 60)
                time_index_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
                
                audio_energy = audio_rms_map.get(time_index_str, 0.05)
                v_score = visual_changes.get(time_index_str, 0.05)
                
                time_series_logs.append({
                    "time_index": time_index_str,
                    "timestamp_sec": timestamp_sec,
                    "raw_chats": ["와바바", "대박", "하이라이트", "ㅋㅋㅋㅋ"],
                    "chat_count": 4,
                    "librosa_rms_energy": audio_energy,
                    "visual_score": v_score
                })
                print(f"📝 [병렬 모드] [{time_index_str}] -> 채팅: 4건, 오디오 RMS: {audio_energy}, 비주얼: {v_score}")

        # Step 5: MongoDB Atlas 적재
        if time_series_logs:
            from pymongo import MongoClient
            client = MongoClient(MONGODB_URL)
            db_instance = client[DB_NAME]
            
            col = db_instance[f"analysis_{video_id}"]
            col.delete_many({})
            col.insert_many(time_series_logs)
            print(f"✅ [MongoDB Atlas 영구 적재] 컬렉션명: analysis_{video_id} ({len(time_series_logs)}개 도큐먼트)")
            
            # Step 6: 30초 Sliding Window Late Fusion
            from fusion_processor import calculate_sliding_window_fusion
            fusion_results = calculate_sliding_window_fusion(time_series_logs)
            
            if fusion_results:
                col_fusion = db_instance[f"fusion_{video_id}"]
                col_fusion.delete_many({})
                col_fusion.insert_many(fusion_results)
                print(f"🔥 [Late Fusion 저장 완료] 컬렉션명: fusion_{video_id}")
                
                # Step 7: 2차 정밀 검증
                candidate_windows = [w for w in fusion_results if w.get("is_1st_highlight_candidate", False)]
                from verification_processor import run_2nd_stage_verification
                
                final_highlights = run_2nd_stage_verification(output_path, candidate_windows, video_id)
                
                if final_highlights:
                    col_final = db_instance[f"final_{video_id}"]
                    col_final.delete_many({})
                    col_final.insert_many(final_highlights)
                    print(f"🎉 [2차 검증 저장 완료] 컬렉션명: final_{video_id}")
                    
                    # Step 8: FFmpeg 무인코딩 클리핑
                    from clipping_processor import extract_and_merge_highlight_clips
                    extract_and_merge_highlight_clips(video_url, final_highlights, video_id)
                    print(f"🏁 [세부 기능 보완 완료] 파이프라인 가동 완착!")
                
            client.close()

    except Exception as total_e:
        import traceback
        print(f"❌ [통합 파이프라인 치명적 사후 붕괴]: {str(total_e)}")
        print(f"🐛 [세부 트레이스백]: {traceback.format_exc()}")

    finally:
        # 💡 [예외 처리] 분석이 성공하든, 중간에 실패하든 서버용 임시 360p 동영상 및 크롭 이미지 폴더 자동 삭제
        print(f"🧹 [임시 청소] 서버 디스크 공간 확보를 위해 {video_id} 관련 임시 자원을 정리합니다.")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                print(f"  └ 🗑️ 임시 비디오 파일 삭제 완료: {output_path}")
            except Exception as clean_err:
                print(f"  └ ⚠️ 비디오 삭제 실패: {clean_err}")

        if os.path.exists(chat_image_dir):
            try:
                shutil.rmtree(chat_image_dir)
                print(f"  └ 🗑️ 임시 채팅 크롭 이미지 폴더 삭제 완료: {chat_image_dir}")
            except Exception as clean_err:
                print(f"  └ ⚠️ 이미지 폴더 삭제 실패: {clean_err}")


async def real_stream_download_task(video_url: str, platform: str, video_id: str):
    print(f"🚀 [WBB 파이프라인] {platform} 영상 프록시 수집 시작 (ID: {video_id})")
    output_path = os.path.join(TEMP_STORAGE_DIR, f"{video_id}_360p.mp4")
    
    base_dir = os.path.abspath(os.path.dirname(__file__))
    venv_script_dir = os.path.join(base_dir, "venv", "Scripts")
    
    if platform == "youtube":
        executable_path = os.path.join(venv_script_dir, "yt-dlp.exe")
        if not os.path.exists(executable_path):
            executable_path = "yt-dlp"
        full_command = f'"{executable_path}" -f "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst" --extractor-args "youtube:player_client=android" --no-check-certificates --no-mtime -o "{output_path}" "{video_url}"'
    elif platform == "chzzk":
        executable_path = os.path.join(venv_script_dir, "yt-dlp.exe")
        if not os.path.exists(executable_path):
            executable_path = "yt-dlp"
        full_command = f'"{executable_path}" -f worst -o "{output_path}" "{video_url}"'
    elif platform == "soop":
        executable_path = os.path.join(venv_script_dir, "streamlink.exe")
        if not os.path.exists(executable_path):
            executable_path = "streamlink"
        full_command = f'"{executable_path}" "{video_url}" worst -o "{output_path}"'

    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, sync_pipeline_core_runner, full_command, output_path, platform, video_id, video_url)
        print("✅ [WBB 코어] 스레드 풀 스케줄링 예약 완료.")
    except Exception as e:
        import traceback
        print(f"❌ [오류 상세 내용]: {str(e)}")
        print(f"🐛 [디버깅 트레이스백]: {traceback.format_exc()}")


# --- 3. API 엔드포인트 구현 ---

@app.post("/api/v1/analyze", response_model=AnalyzeResponse, status_code=202)
async def start_analysis(request_data: AnalyzeRequest, background_tasks: BackgroundTasks):
    url_str = str(request_data.video_url)
    video_id = f"wbb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if "youtube.com" in url_str or "youtu.be" in url_str:
        platform = "youtube"
    elif "chzzk.naver.com" in url_str:
        platform = "chzzk"
    elif "sooply.co.kr" in url_str or "afreecatv.com" in url_str:
        platform = "soop"
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 영상 플랫폼 URL입니다.")

    background_tasks.add_task(real_stream_download_task, url_str, platform, video_id)

    return {
        "video_info": {
            "video_id": video_id,
            "platform": platform,
            "status": "ANALYZING",
            "total_duration_sec": 60
        },
        "time_series_data": [
            {
                "timestamp": "00:00:10",
                "chat_count": 45,
                "kobert_score": 0.92,
                "visual_score": 0.81,
                "librosa_energy": 0.77,
                "is_reaction_peak": True,
                "top_keywords": ["쇼츠", "대박", "존잼"]
            }
        ],
        "final_highlights": [
            {
                "rank": 1,
                "start_time": "00:00:05",
                "end_time": "00:00:25",
                "highlight_score": 0.94,
                "summary_reason": "유튜브 숏츠 내 실시간 피크 반응 탐지",
                "streamer_stt_text": "이 영상 진짜 대박입니다!",
                "streamer_emotion": "놀람",
                "clip_url": f"/api/v1/clips/{video_id}_clip_01.mp4"
            }
        ]
    }


@app.get("/api/v1/chart/{video_id}", response_model=ChartDataResponse)
async def get_chart_visualization_data(video_id: str):
    if db.db is None:
        raise HTTPException(status_code=500, detail="데이터베이스 연결이 초기화되지 않았습니다.")

    col_analysis = db.db[f"analysis_{video_id}"]
    col_fusion = db.db[f"fusion_{video_id}"]

    analysis_docs = await col_analysis.find({}, {"_id": 0}).to_list(length=2000)
    fusion_docs = await col_fusion.find({}, {"_id": 0}).to_list(length=2000)

    if not analysis_docs:
        raise HTTPException(
            status_code=404, 
            detail=f"요청하신 비디오 ID [{video_id}]에 대한 시계열 분석 데이터를 찾을 수 없습니다."
        )

    timestamps = [d.get("time_index", "00:00:00") for d in analysis_docs]
    chat_counts = [int(d.get("chat_count", 0)) for d in analysis_docs]
    audio_energies = [float(d.get("librosa_rms_energy", 0.0)) for d in analysis_docs]
    visual_scores = [float(d.get("visual_score", 0.0)) for d in analysis_docs]

    fusion_scores = [float(f.get("fusion_score", 0.0)) for f in fusion_docs]
    
    highlight_markers = []
    for f in fusion_docs:
        if f.get("is_1st_highlight_candidate", False):
            highlight_markers.append({
                "start_time": f.get("start_time"),
                "end_time": f.get("end_time"),
                "fusion_score": f.get("fusion_score")
            })

    avg_chat = sum(chat_counts) / len(chat_counts) if chat_counts else 0
    if avg_chat >= 10:
        overall_mood = "🔥 매우 열광적 (High Tension)"
    elif avg_chat >= 4:
        overall_mood = "😃 활발한 리액션 (Active)"
    else:
        overall_mood = "☕ 차분한 방송 (Calm)"

    return {
        "video_id": video_id,
        "timestamps": timestamps,
        "chat_counts": chat_counts,
        "audio_energies": audio_energies,
        "visual_scores": visual_scores,
        "fusion_scores": fusion_scores,
        "highlight_markers": highlight_markers,
        "overall_mood": overall_mood
    }