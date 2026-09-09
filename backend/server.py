"""
와바바 (WBB) - 통합 백엔드 서버
=================================================
[통합 내역]
- feature/backend 브랜치: FastAPI 뼈대, MongoDB Atlas 연동, CORS, yt-dlp/Streamlink
  듀얼 파싱 다운로드 로직을 그대로 재사용합니다.
- feature/ai-nlp 브랜치: 실제 동작하는 5단계 AI 파이프라인
  (highlight_pipeline.WBBAutoHighlightPipeline)을 그대로 재사용합니다.

[핵심 변경점]
기존 backend/main.py의 sync_pipeline_core_runner()는 KoBERT/PP-OCRv3/Demucs/Whisper를
전혀 쓰지 않고 하드코딩된 더미 채팅("와바바","대박","ㅋㅋㅋㅋ")과
"채팅 0.4 + 오디오 0.3 + 비전 0.3" 고정 가중치로만 결과를 만들어내고 있었습니다.

이 파일은 그 더미 로직을 걷어내고, 실제로 동작이 검증된
WBBAutoHighlightPipeline.run_full_pipeline()을 호출해서 나온 결과 JSON
(video_emotion_timeseries.json, final_highlight_candidates.json)을
그대로 MongoDB에 적재하고 API 응답으로 반환합니다.

미사용 상태였던 backend/ocr_processor.py, fusion_processor.py,
verification_processor.py, clipping_processor.py는 더 이상 필요하지 않습니다.
(OCR은 ppocr_chat_extractor.py, Fusion/정제는 sliding_window_nlp.py +
stage2_refinement.py, 클리핑은 ffmpeg_clipper.py가 이미 대체합니다.)
"""

import os
import json
import shutil
import asyncio
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, HttpUrl
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from highlight_pipeline import WBBAutoHighlightPipeline

# --- 0. 환경 변수(.env) 로드 및 경로 설정 ---
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "wbb_db")
KOBERT_MODEL_DIR = os.getenv("KOBERT_MODEL_DIR", "./kobert_wbb_model")
# CHAT_CROP_BOX를 .env에 명시하면 그 고정 좌표를 쓰고, 비워두면(기본값)
# highlight_pipeline.py의 Auto-ROI가 영상마다 채팅창 위치를 자동으로 탐지합니다.
_crop_box_env = os.getenv("CHAT_CROP_BOX", "").strip()
CHAT_CROP_BOX = tuple(float(x) for x in _crop_box_env.split(",")) if _crop_box_env else None

# 로그인 없이 "일시적 내역"만 남기는 정책 — 이 시간이 지난 작업은
# MongoDB 문서와 outputs/의 mp4 파일이 함께 자동 삭제됩니다.
RETENTION_HOURS = float(os.getenv("RETENTION_HOURS", "4"))

TEMP_STORAGE_DIR = "temp_storage"
OUTPUT_DIR = "outputs"  # 최종 하이라이트 영상 및 결과 JSON 보관용 (React가 접근)
os.makedirs(TEMP_STORAGE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class Database:
    client: Optional[AsyncIOMotorClient] = None
    db = None


db = Database()

# AI 파이프라인은 모델 로딩 비용이 크므로(KoBERT + PP-OCRv3) 서버 시작 시 1회만 로드합니다.
pipeline: Optional[WBBAutoHighlightPipeline] = None

scheduler = AsyncIOScheduler()


async def cleanup_expired_jobs():
    """
    RETENTION_HOURS(기본 4시간)가 지난 작업을 찾아 MongoDB 문서와
    outputs/의 mp4 파일을 함께 삭제합니다.

    로그인 없이 "일시적으로만 남는 내역"을 구현하기 위한 정리 작업입니다.
    MongoDB TTL 인덱스만 걸면 문서는 지워지지만 실제 mp4 파일은 그대로
    남아 디스크가 계속 찰 수 있어서, 문서와 파일을 한 곳에서 같이 지웁니다.
    """
    if db.db is None:
        return

    cutoff = datetime.utcnow() - timedelta(hours=RETENTION_HOURS)
    expired_cursor = db.db["jobs"].find({"created_at": {"$lt": cutoff}})

    deleted_count = 0
    async for doc in expired_cursor:
        video_id = doc.get("video_id")

        final_video_path = os.path.join(OUTPUT_DIR, f"{video_id}_highlight.mp4")
        if os.path.exists(final_video_path):
            try:
                os.remove(final_video_path)
            except OSError as e:
                print(f"⚠️ [정리] {final_video_path} 삭제 실패: {e}")

        await db.db["jobs"].delete_one({"_id": doc["_id"]})
        deleted_count += 1

    if deleted_count:
        print(f"🧹 [자동 정리] {RETENTION_HOURS}시간 경과한 작업 {deleted_count}건 삭제 완료")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.client = AsyncIOMotorClient(MONGODB_URL)
    db.db = db.client[DB_NAME]
    print(f"✅ [WBB DB] MongoDB Atlas ({DB_NAME}) 연동 성공!")

    global pipeline
    try:
        print("🚀 [WBB AI] KoBERT + PP-OCRv3 + Demucs + Whisper 파이프라인 로딩 중...")
        pipeline = WBBAutoHighlightPipeline(model_dir=KOBERT_MODEL_DIR)
        print("✅ [WBB AI] 파이프라인 로딩 완료. 분석 요청을 받을 준비가 되었습니다.")
    except Exception as e:
        # 모델 파일이 없는 개발 환경에서도 서버 자체는 뜨도록 허용하되,
        # /api/v1/analyze 호출 시점에 명확한 에러를 반환합니다.
        print(f"⚠️ [WBB AI] 파이프라인 로딩 실패: {e}")
        print(f"   ./{KOBERT_MODEL_DIR} 경로에 파인튜닝된 KoBERT 모델이 있는지 확인하세요.")
        pipeline = None

    # 15분마다 만료된 작업을 확인해서 정리 (4시간 지난 항목이 최대 15분
    # 늦게 지워질 수 있다는 뜻 — 더 촘촘하게 하려면 minutes 값을 줄이세요)
    scheduler.add_job(cleanup_expired_jobs, "interval", minutes=15, id="cleanup_expired_jobs")
    scheduler.start()
    print(f"🧹 [자동 정리] {RETENTION_HOURS}시간 보관 정책 활성화 (15분마다 확인)")

    yield

    scheduler.shutdown(wait=False)
    if db.client:
        db.client.close()
        print("❌ [WBB DB] MongoDB Atlas 연결이 안전하게 해제되었습니다.")


app = FastAPI(
    title="와바바 (WBB) API 서버",
    description="KoBERT와 PP-OCRv3를 활용한 멀티모달 분석 기반 스트리밍 하이라이트 요약 플랫폼 API",
    version="2.0.0",
    lifespan=lifespan,
)

# React 프론트엔드 연동용 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 최종 하이라이트 mp4를 프론트엔드가 <video src="/files/xxx.mp4">로 바로 재생할 수 있게 정적 서빙
app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")


# --- 1. Pydantic 요청/응답 스키마 ---
# (실제 highlight_pipeline.py가 만들어내는 JSON 구조를 그대로 반영합니다.
#  이전 버전 스키마(kobert_score/visual_score/librosa_energy 등)는 파이프라인이
#  실제로 생성하지 않는 필드였으므로 걷어냈습니다.)

class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"


class AnalyzeRequest(BaseModel):
    video_url: HttpUrl


class AnalyzeAcceptedResponse(BaseModel):
    video_id: str
    status: JobStatus
    message: str


class VideoInfo(BaseModel):
    video_id: str
    platform: str
    status: JobStatus
    elapsed_time_sec: Optional[float] = None
    error: Optional[str] = None


class EmotionTimePoint(BaseModel):
    timestamp: float
    chat_text: str
    top_emotion: str
    joy_pct: float
    embarrass_pct: float
    anger_pct: float
    anxiety_pct: float
    hurt_pct: float
    sadness_pct: float
    neutral_pct: float


class EmotionTimeseries(BaseModel):
    total_chats_analyzed: int
    recommended_joy_threshold: float
    time_series_data: List[EmotionTimePoint]


class HighlightItem(BaseModel):
    rank: int
    start_time: float
    end_time: float
    duration: float
    stage1_chat_score: float
    streamer_speech_text: str
    streamer_speech_emotion: str
    streamer_joy_score: float
    final_highlight_score: float


class HighlightMetadata(BaseModel):
    source_video: str
    top_k_limit: int
    max_duration_cap_sec: float
    total_highlights_count: int
    total_highlight_duration_sec: float


class HighlightResult(BaseModel):
    metadata: HighlightMetadata
    highlights: List[HighlightItem]


class AnalyzeResultResponse(BaseModel):
    video_info: VideoInfo
    emotion_timeseries: Optional[EmotionTimeseries] = None
    highlight_result: Optional[HighlightResult] = None
    final_video_url: Optional[str] = None


# --- 2. 플랫폼 자동 감지 및 스트림 다운로드 (feature/backend 로직 재사용) ---

def detect_platform(url_str: str) -> str:
    if "youtube.com" in url_str or "youtu.be" in url_str:
        return "youtube"
    if "chzzk.naver.com" in url_str:
        return "chzzk"
    if "sooplive.co.kr" in url_str or "afreecatv.com" in url_str:
        return "soop"
    raise HTTPException(status_code=400, detail="지원하지 않는 영상 플랫폼 URL입니다.")


def build_download_command(platform: str, video_url: str, output_path: str) -> str:
    """분석 단계는 서버 자원 절약을 위해 저화질(360p 수준)로 다운로드합니다."""
    if platform == "youtube":
        return (
            f'yt-dlp -f "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst" '
            f'--extractor-args "youtube:player_client=android" '
            f'--no-check-certificates --no-mtime -o "{output_path}" "{video_url}"'
        )
    if platform == "chzzk":
        return (
            f'yt-dlp -f "worst" --no-check-certificates --no-mtime '
            f'--extractor-args "chzzk:no_api=true" -o "{output_path}" "{video_url}"'
        )
    if platform == "soop":
        return f'streamlink "{video_url}" worst -o "{output_path}"'
    raise ValueError(f"알 수 없는 플랫폼: {platform}")


# --- 3. 실제 AI 파이프라인 실행 백그라운드 태스크 ---

async def _finalize_success(video_id: str, result_meta: dict):
    """파이프라인 결과 JSON을 읽어 DB에 저장하고 최종 영상을 outputs/로 이동"""
    with open(result_meta["emotion_timeseries_json"], "r", encoding="utf-8") as f:
        emotion_timeseries = json.load(f)
    with open(result_meta["final_candidates_json"], "r", encoding="utf-8") as f:
        highlight_result = json.load(f)

    final_video_dest = os.path.join(OUTPUT_DIR, f"{video_id}_highlight.mp4")
    if os.path.exists(result_meta["final_video"]):
        shutil.move(result_meta["final_video"], final_video_dest)

    await db.db["jobs"].update_one(
        {"video_id": video_id},
        {
            "$set": {
                "status": JobStatus.DONE.value,
                "updated_at": datetime.utcnow(),
                "elapsed_time_sec": result_meta["elapsed_time_sec"],
                "emotion_timeseries": emotion_timeseries,
                "highlight_result": highlight_result,
                "final_video_url": f"/files/{video_id}_highlight.mp4",
            }
        },
    )
    print(f"🎉 [WBB] {video_id} 분석 완료 ({result_meta['elapsed_time_sec']}초)")


async def _set_status(video_id: str, status: "JobStatus", **extra):
    await db.db["jobs"].update_one(
        {"video_id": video_id},
        {"$set": {"status": status.value, "updated_at": datetime.utcnow(), **extra}},
    )


async def run_analysis_job(video_url: str, platform: str, video_id: str):
    output_path = os.path.join(TEMP_STORAGE_DIR, f"{video_id}_360p.mp4")

    try:
        # Step 0: 스트림 다운로드 (프록시용 저화질)
        await _set_status(video_id, JobStatus.DOWNLOADING)
        command = build_download_command(platform, video_url, output_path)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, errors="replace",
            ),
        )
        if result.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(
                f"{platform} 스트림 다운로드 실패 (yt-dlp/Streamlink 종료 코드 {result.returncode}). "
                f"stderr: {result.stderr[-500:] if result.stderr else 'N/A'}"
            )

        # Step 1~5: 실제 AI 파이프라인 (OCR → KoBERT → SlidingWindow → Whisper/Demucs → FFmpeg)
        if pipeline is None:
            raise RuntimeError(
                f"AI 파이프라인이 로드되지 않았습니다. {KOBERT_MODEL_DIR} 경로의 "
                f"파인튜닝된 KoBERT 모델을 확인하세요."
            )

        await _set_status(video_id, JobStatus.ANALYZING)
        result_meta = await loop.run_in_executor(
            None,
            lambda: pipeline.run_full_pipeline(video_path=output_path, crop_box=CHAT_CROP_BOX),
        )

        await _finalize_success(video_id, result_meta)

    except Exception as e:
        print(f"❌ [WBB] {video_id} 분석 실패: {e}")
        await _set_status(video_id, JobStatus.FAILED, error=str(e))

    finally:
        # 디스크 정리 (원본/360p 임시 파일만 삭제, 결과물은 outputs/에 보존)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


async def run_analysis_job_from_file(video_path: str, video_id: str):
    try:
        if pipeline is None:
            raise RuntimeError(
                f"AI 파이프라인이 로드되지 않았습니다. {KOBERT_MODEL_DIR} 경로를 확인하세요."
            )

        await _set_status(video_id, JobStatus.ANALYZING)
        loop = asyncio.get_running_loop()
        result_meta = await loop.run_in_executor(
            None,
            lambda: pipeline.run_full_pipeline(video_path=video_path, crop_box=CHAT_CROP_BOX),
        )

        await _finalize_success(video_id, result_meta)

    except Exception as e:
        print(f"❌ [WBB] {video_id} 분석 실패: {e}")
        await _set_status(video_id, JobStatus.FAILED, error=str(e))

    finally:
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except OSError:
                pass


# --- 4. REST API 엔드포인트 ---

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "와바바(WBB) 멀티모달 스트리밍 하이라이트 플랫폼",
        "ai_pipeline_loaded": pipeline is not None,
    }


@app.post("/api/v1/analyze", response_model=AnalyzeAcceptedResponse, status_code=202)
async def start_analysis(request_data: AnalyzeRequest, background_tasks: BackgroundTasks):
    url_str = str(request_data.video_url)
    platform = detect_platform(url_str)
    video_id = f"wbb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    await db.db["jobs"].insert_one(
        {
            "video_id": video_id,
            "platform": platform,
            "video_url": url_str,
            "status": JobStatus.QUEUED.value,
            "created_at": datetime.utcnow(),
        }
    )

    background_tasks.add_task(run_analysis_job, url_str, platform, video_id)

    return AnalyzeAcceptedResponse(
        video_id=video_id,
        status=JobStatus.QUEUED,
        message="분석이 큐에 등록되었습니다. GET /api/v1/result/{video_id} 로 진행 상태를 확인하세요.",
    )


@app.post("/api/v1/analyze-upload", response_model=AnalyzeAcceptedResponse, status_code=202)
async def start_analysis_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    video_id = f"wbb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    saved_path = os.path.join(TEMP_STORAGE_DIR, f"{video_id}_upload.mp4")

    with open(saved_path, "wb") as f:
        f.write(await file.read())

    await db.db["jobs"].insert_one(
        {
            "video_id": video_id,
            "platform": "upload",
            "status": JobStatus.QUEUED.value,
            "created_at": datetime.utcnow(),
        }
    )

    background_tasks.add_task(run_analysis_job_from_file, saved_path, video_id)

    return AnalyzeAcceptedResponse(
        video_id=video_id,
        status=JobStatus.QUEUED,
        message="업로드된 영상 분석이 큐에 등록되었습니다.",
    )


@app.get("/api/v1/result/{video_id}", response_model=AnalyzeResultResponse)
async def get_analysis_result(video_id: str):
    doc = await db.db["jobs"].find_one({"video_id": video_id})
    if not doc:
        raise HTTPException(status_code=404, detail="존재하지 않는 video_id 입니다.")

    return AnalyzeResultResponse(
        video_info=VideoInfo(
            video_id=doc["video_id"],
            platform=doc["platform"],
            status=doc["status"],
            elapsed_time_sec=doc.get("elapsed_time_sec"),
            error=doc.get("error"),
        ),
        emotion_timeseries=doc.get("emotion_timeseries"),
        highlight_result=doc.get("highlight_result"),
        final_video_url=doc.get("final_video_url"),
    )