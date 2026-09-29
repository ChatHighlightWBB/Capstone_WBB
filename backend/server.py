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
import traceback
import faulthandler
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, HttpUrl
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from highlight_pipeline import WBBAutoHighlightPipeline

# torch 등 네이티브 코드에서 access violation 같은 크래시가 나면 파이썬 예외가
# 아니라서 traceback 없이 프로세스가 죽습니다. 그때라도 모든 스레드의 파이썬
# 스택을 stderr에 남겨서 어느 단계에서 죽었는지 알 수 있게 합니다.
faulthandler.enable()

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

# 유튜브 다운로드용 yt-dlp 실행 파일. venv(Python 3.9)에는 2025.10.14까지만
# 설치돼서, Python 없이 도는 최신 standalone exe를 backend/bin/에 두고 씁니다.
# (경로 없이 "yt-dlp"만 쓰면 PATH에 먼저 잡힌 다른 venv의 구버전이 실행됨)
YTDLP_BIN = os.getenv(
    "YTDLP_BIN", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "yt-dlp.exe")
)

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

# video_id -> {"step": int, "total_steps": int, "label": str}
# 파이프라인은 백그라운드 스레드에서 동기적으로 도는데, 그 안에서 매번
# MongoDB(비동기)를 갱신하긴 번거로워서 간단한 메모리 딕셔너리로 실시간
# 진행 상황만 별도로 들고 있습니다. (서버 재시작하면 사라지지만, 어차피
# 진행 중이던 작업도 재시작하면 이어지지 않으므로 문제 없음)
PROGRESS: Dict[str, Dict[str, Any]] = {}

# 분석(Step 1~5 + 결과 저장)은 한 번에 하나만 돌립니다. 파이프라인 객체
# (Whisper/KoBERT)를 여러 스레드가 동시에 쓰면 충돌해서 서버가 죽고,
# 중간 파일도 작업마다 같은 이름이라 서로 덮어쓰기 때문입니다.
# Python 3.9의 asyncio.Lock은 생성 시점의 이벤트 루프에 묶여서, 모듈에서
# 바로 만들면 uvicorn 루프와 어긋나 대기 시 RuntimeError가 납니다 → lifespan에서 생성.
ANALYSIS_LOCK: Optional[asyncio.Lock] = None

# 파이프라인 모듈들이 작업 폴더(backend/)에 고정된 이름으로 쓰는 중간 산출물.
# 이전 작업 것이 남아 있으면 다음 작업 결과에 그대로 섞여 들어갑니다.
PIPELINE_TEMP_FILES = [
    "extracted_ocr_chats.csv",
    "video_emotion_timeseries.csv",
    "video_emotion_timeseries.json",
    "stage1_candidates.csv",
    "stage1_candidates.json",
    "final_highlight_candidates.csv",
    "final_highlight_candidates.json",
    "final_highlight.mp4",
]
PIPELINE_TEMP_DIRS = ["temp_clips", "temp_separated"]

scheduler = AsyncIOScheduler()


def _clear_pipeline_temp_files():
    """
    이전 작업의 중간 파일을 지웁니다. 폴더 자체는 남기고 안의 내용만 지웁니다.
    (temp_clips는 서버 시작 시 WBBFFmpegClipper가 한 번만 만들기 때문에
    폴더째 지우면 다음 Step 5에서 클립을 쓸 곳이 없어집니다.)
    """
    for path in PIPELINE_TEMP_FILES:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"⚠️ [정리] {path} 삭제 실패: {e}")

    for dir_path in PIPELINE_TEMP_DIRS:
        if not os.path.isdir(dir_path):
            continue
        for name in os.listdir(dir_path):
            entry = os.path.join(dir_path, name)
            try:
                if os.path.isdir(entry):
                    shutil.rmtree(entry)
                else:
                    os.remove(entry)
            except OSError as e:
                print(f"⚠️ [정리] {entry} 삭제 실패: {e}")


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

    global pipeline, ANALYSIS_LOCK
    ANALYSIS_LOCK = asyncio.Lock()  # 실행 중인 uvicorn 루프 안에서 생성 (위 ANALYSIS_LOCK 주석 참고)

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
    # [설정 화면 연동] 사용자가 Auto-ROI 결과가 안 맞아서 직접 좌표를
    # 지정하고 싶을 때 넘깁니다. (ymin, xmin, ymax, xmax) 0~1 비율.
    # 안 넘기면 서버 기본값(.env의 CHAT_CROP_BOX 또는 Auto-ROI)을 씁니다.
    crop_box: Optional[List[float]] = None


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
    step: Optional[int] = None
    total_steps: Optional[int] = None
    step_label: Optional[str] = None


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
    clip_url: Optional[str] = None


class HighlightMetadata(BaseModel):
    source_video: str
    top_k_limit: Optional[int] = None  # 하이라이트 0개로 조기 종료하면 없음
    max_duration_cap_sec: Optional[float] = None  # 〃
    total_highlights_count: int
    total_highlight_duration_sec: float
    empty_reason: Optional[str] = None  # "no_chats" | "no_candidates" (하이라이트 0개일 때만)


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
    if "sooplive.co.kr" in url_str or "sooplive.com" in url_str or "afreecatv.com" in url_str:
        return "soop"
    raise HTTPException(status_code=400, detail="지원하지 않는 영상 플랫폼 URL입니다.")


def build_download_command(platform: str, video_url: str, output_path: str) -> str:
    """
    분석용으로 지나치게 고화질을 받을 필요는 없지만, 'worst'는 채팅 글씨가
    안 보일 정도로 낮아서 480p 캡 정도로 절충합니다.

    [주의] 아래 두 실험은 "확실한 해결책"이 아니라 "밑져야 본전인 시도"입니다.
    유튜브/치지직 문제 모두 yt-dlp 라이브러리 자체의 최신 이슈라 100% 보장은
    없습니다. 실패하면 결국 파일 업로드로 안내하는 게 맞습니다.
    """
    if platform == "youtube":
        # android 클라이언트는 이제 GVS PO Token 없이는 https 포맷을 안 주고,
        # 영상+음성 통합 포맷(format 18)도 대부분 사라져서 "best[...]"는
        # "Requested format is not available"로 실패합니다.
        # → 기본 클라이언트 + node(JS 챌린지)로 HLS 영상/음성을 따로 받아 병합.
        # -S "res:480"은 짧은 변 기준이라 가로 854x480, Shorts 480x854가 됩니다.
        # (360p는 채팅 글씨가 작아 OCR이 놓치는 경우가 있어 480으로 올림)
        return (
            f'"{YTDLP_BIN}" --js-runtimes node '
            f'-f "bv*[protocol^=m3u8]+ba[protocol^=m3u8]/bv*+ba/b" -S "res:480" '
            f'--merge-output-format mp4 '
            f'--no-check-certificates --no-mtime -o "{output_path}" "{video_url}"'
        )
    if platform == "chzzk":
        # [실험 2] DASH 대신 HLS(m3u8) 포맷을 우선 시도합니다.
        # KeyError('sourceURL')는 CHZZK의 DASH 매니페스트 파서에만 있는
        # 버그라, HLS 포맷을 받을 수 있으면 이 버그 자체를 피해갈 수 있습니다.
        # (치지직이 HLS를 아예 안 주는 영상이면 여전히 실패합니다)
        return (
            f'yt-dlp -f "best[protocol^=m3u8][height<=480]/best[height<=480]/worst" '
            f'--no-check-certificates --no-mtime '
            f'--extractor-args "chzzk:no_api=true" -o "{output_path}" "{video_url}"'
        )
    if platform == "soop":
        return f'streamlink "{video_url}" "480p,best" -o "{output_path}"'
    raise ValueError(f"알 수 없는 플랫폼: {platform}")


# --- 3. 실제 AI 파이프라인 실행 백그라운드 태스크 ---

async def _finalize_success(video_id: str, result_meta: dict):
    """파이프라인 결과 JSON을 읽어 DB에 저장하고 최종 영상을 outputs/로 이동"""
    with open(result_meta["emotion_timeseries_json"], "r", encoding="utf-8") as f:
        emotion_timeseries = json.load(f)
    with open(result_meta["final_candidates_json"], "r", encoding="utf-8") as f:
        highlight_result = json.load(f)

    # 하이라이트가 0개면 병합 영상이 없어서(final_video=None) URL도 비워둡니다.
    # (예전처럼 항상 URL을 넣으면 프론트에 404 나는 빈 플레이어가 뜹니다)
    final_video_url = None
    final_video_dest = os.path.join(OUTPUT_DIR, f"{video_id}_highlight.mp4")
    if result_meta.get("final_video") and os.path.exists(result_meta["final_video"]):
        shutil.move(result_meta["final_video"], final_video_dest)
        final_video_url = f"/files/{video_id}_highlight.mp4"

    # [추가] 병합 영상 말고, 하이라이트별 개별 클립도 outputs/로 옮겨서
    # 각각 따로 재생할 수 있게 clip_url을 붙입니다. highlight_clips 리스트는
    # final_candidates_json의 "highlights" 배열과 같은 순서로 만들어집니다.
    clip_paths = result_meta.get("highlight_clips", [])
    highlights_list = highlight_result.get("highlights", [])
    for idx, clip_src in enumerate(clip_paths):
        if idx >= len(highlights_list):
            break
        if not os.path.exists(clip_src):
            continue
        rank = highlights_list[idx].get("rank", idx + 1)
        clip_dest = os.path.join(OUTPUT_DIR, f"{video_id}_highlight_{rank}.mp4")
        shutil.move(clip_src, clip_dest)
        highlights_list[idx]["clip_url"] = f"/files/{video_id}_highlight_{rank}.mp4"

    await db.db["jobs"].update_one(
        {"video_id": video_id},
        {
            "$set": {
                "status": JobStatus.DONE.value,
                "updated_at": datetime.utcnow(),
                "elapsed_time_sec": result_meta["elapsed_time_sec"],
                "emotion_timeseries": emotion_timeseries,
                "highlight_result": highlight_result,
                "final_video_url": final_video_url,
            }
        },
    )
    print(f"🎉 [WBB] {video_id} 분석 완료 ({result_meta['elapsed_time_sec']}초, "
          f"하이라이트 {len(highlights_list)}개)")


async def _set_status(video_id: str, status: "JobStatus", **extra):
    await db.db["jobs"].update_one(
        {"video_id": video_id},
        {"$set": {"status": status.value, "updated_at": datetime.utcnow(), **extra}},
    )


async def _run_pipeline_exclusively(video_id: str, video_path: str, crop_box_override=None):
    """
    Step 1~5 + 결과 저장을 ANALYSIS_LOCK 안에서 한 번에 하나씩 실행합니다.
    앞 작업이 분석 중이면 queued("분석 대기 중") 상태로 차례를 기다립니다.
    _finalize_success도 락 안에 둬야 합니다 — 공용 이름의 결과 JSON과
    final_highlight.mp4를 읽고 옮기는 동안 다음 작업이 덮어쓰면 안 되기 때문입니다.
    """
    if pipeline is None:
        raise RuntimeError(
            f"AI 파이프라인이 로드되지 않았습니다. {KOBERT_MODEL_DIR} 경로의 "
            f"파인튜닝된 KoBERT 모델을 확인하세요."
        )

    loop = asyncio.get_running_loop()

    def _on_progress(step: int, label: str):
        PROGRESS[video_id] = {"step": step, "total_steps": 5, "label": label}

    effective_crop_box = tuple(crop_box_override) if crop_box_override else CHAT_CROP_BOX

    if ANALYSIS_LOCK.locked():
        print(f"⏳ [{video_id}] 앞선 분석이 끝날 때까지 대기합니다.")
    await _set_status(video_id, JobStatus.QUEUED)

    async with ANALYSIS_LOCK:
        # 락을 잡은 뒤에 지워야 합니다. 락 밖에서 지우면 지금 돌고 있는
        # 앞 작업의 중간 파일을 지워버릴 수 있습니다.
        _clear_pipeline_temp_files()
        await _set_status(video_id, JobStatus.ANALYZING)
        result_meta = await loop.run_in_executor(
            None,
            lambda: pipeline.run_full_pipeline(
                video_path=video_path, crop_box=effective_crop_box, on_progress=_on_progress
            ),
        )
        await _finalize_success(video_id, result_meta)


async def run_analysis_job(video_url: str, platform: str, video_id: str, crop_box_override=None):
    output_path = os.path.join(TEMP_STORAGE_DIR, f"{video_id}_480p.mp4")

    try:
        # Step 0: 스트림 다운로드 (프록시용 저화질)
        await _set_status(video_id, JobStatus.DOWNLOADING)
        command = build_download_command(platform, video_url, output_path)
        loop = asyncio.get_running_loop()
        dl_start = datetime.now()
        print(f"⬇️ [{video_id}] 다운로드 시작: {dl_start.strftime('%H:%M:%S.%f')[:-3]} ({platform})")

        # [추가] 재시도 로직: 특히 CHZZK는 "재인코딩 중", API 일시 오류 등으로
        # 첫 시도에 실패해도 몇 초 뒤 재시도하면 성공하는 경우가 흔합니다.
        MAX_DOWNLOAD_RETRIES = 3
        result = None
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, errors="replace",
                ),
            )
            if result.returncode == 0 and os.path.exists(output_path):
                break
            # 포맷 자체가 없는 경우는 다시 시도해도 결과가 같으므로 바로 포기합니다.
            if "Requested format is not available" in (result.stderr or ""):
                print(f"⚠️ [{video_id}] 요청한 포맷이 없어 재시도하지 않습니다.")
                break
            print(f"⚠️ [{video_id}] 다운로드 시도 {attempt}/{MAX_DOWNLOAD_RETRIES} 실패 "
                  f"(종료 코드 {result.returncode}). "
                  f"{'재시도합니다...' if attempt < MAX_DOWNLOAD_RETRIES else '포기합니다.'}")
            if attempt < MAX_DOWNLOAD_RETRIES:
                await asyncio.sleep(5 * attempt)  # 5초, 10초 간격으로 점점 늘려가며 재시도

        if result.returncode != 0 or not os.path.exists(output_path):
            # [추가] yt-dlp/streamlink가 끝까지 실패하면, 마지막 수단으로
            # 플랫폼 자체 API/브라우저 자동화 직접 다운로더를 시도합니다.
            print(f"⚠️ [{video_id}] yt-dlp/streamlink 전체 실패 — 직접 다운로드 방식으로 최종 시도합니다.")
            direct_success = False
            if platform == "chzzk":
                from chzzk_direct_downloader import download_chzzk_vod_direct
                direct_success = await loop.run_in_executor(
                    None, lambda: download_chzzk_vod_direct(video_url, output_path)
                )
            elif platform == "soop":
                from soop_direct_downloader import download_soop_vod_direct
                direct_success = await loop.run_in_executor(
                    None, lambda: download_soop_vod_direct(video_url, output_path)
                )

            if not direct_success:
                raise RuntimeError(
                    f"{platform} 스트림 다운로드 실패 (표준 방식 {attempt}회 + "
                    f"직접 다운로드 방식 모두 실패). 파일 업로드를 이용해주세요. "
                    f"stderr: {result.stderr[-500:] if result.stderr else 'N/A'}"
                )

        dl_end = datetime.now()
        dl_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"⬇️ [{video_id}] 다운로드 완료: {dl_end.strftime('%H:%M:%S.%f')[:-3]} "
              f"(걸린 시간 {(dl_end - dl_start).total_seconds():.1f}초, "
              f"시도 {attempt}회, {dl_size_mb:.1f}MB)")

        # Step 1~5: 실제 AI 파이프라인 (OCR → KoBERT → SlidingWindow → Whisper/Demucs → FFmpeg)
        # 다운로드는 락 밖에서 끝냈고, 분석만 차례를 기다려서 한 번에 하나씩 돕니다.
        await _run_pipeline_exclusively(video_id, output_path, crop_box_override)

    except Exception as e:
        print(f"❌ [WBB] {video_id} 분석 실패: {e}")
        traceback.print_exc()
        await _set_status(video_id, JobStatus.FAILED, error=str(e))

    finally:
        PROGRESS.pop(video_id, None)
        # 디스크 정리 (원본/480p 임시 파일만 삭제, 결과물은 outputs/에 보존)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


async def run_analysis_job_from_file(video_path: str, video_id: str, crop_box_override=None):
    try:
        await _run_pipeline_exclusively(video_id, video_path, crop_box_override)

    except Exception as e:
        print(f"❌ [WBB] {video_id} 분석 실패: {e}")
        traceback.print_exc()
        await _set_status(video_id, JobStatus.FAILED, error=str(e))

    finally:
        PROGRESS.pop(video_id, None)
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except OSError:
                pass


# --- 4. REST API 엔드포인트 ---

@app.get("/api/v1/info")
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "와바바(WBB) 멀티모달 스트리밍 하이라이트 플랫폼",
        "ai_pipeline_loaded": pipeline is not None,
        "retention_hours": RETENTION_HOURS,
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

    background_tasks.add_task(run_analysis_job, url_str, platform, video_id, request_data.crop_box)

    return AnalyzeAcceptedResponse(
        video_id=video_id,
        status=JobStatus.QUEUED,
        message="분석이 큐에 등록되었습니다. GET /api/v1/result/{video_id} 로 진행 상태를 확인하세요.",
    )


@app.post("/api/v1/analyze-upload", response_model=AnalyzeAcceptedResponse, status_code=202)
async def start_analysis_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    crop_box: Optional[str] = Form(None),
):
    video_id = f"wbb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    saved_path = os.path.join(TEMP_STORAGE_DIR, f"{video_id}_upload.mp4")

    with open(saved_path, "wb") as f:
        f.write(await file.read())

    # "0.15,0.65,0.6,0.98" 형태의 콤마 구분 문자열로 넘어옵니다.
    parsed_crop_box = None
    if crop_box:
        try:
            parsed_crop_box = [float(x) for x in crop_box.split(",")]
        except ValueError:
            pass  # 형식이 잘못되면 그냥 기본값(Auto-ROI/.env)으로 진행

    await db.db["jobs"].insert_one(
        {
            "video_id": video_id,
            "platform": "upload",
            "status": JobStatus.QUEUED.value,
            "created_at": datetime.utcnow(),
        }
    )

    background_tasks.add_task(run_analysis_job_from_file, saved_path, video_id, parsed_crop_box)

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

    progress = PROGRESS.get(video_id)

    return AnalyzeResultResponse(
        video_info=VideoInfo(
            video_id=doc["video_id"],
            platform=doc["platform"],
            status=doc["status"],
            elapsed_time_sec=doc.get("elapsed_time_sec"),
            error=doc.get("error"),
            step=progress["step"] if progress else None,
            total_steps=progress["total_steps"] if progress else None,
            step_label=progress["label"] if progress else None,
        ),
        emotion_timeseries=doc.get("emotion_timeseries"),
        highlight_result=doc.get("highlight_result"),
        final_video_url=doc.get("final_video_url"),
    )