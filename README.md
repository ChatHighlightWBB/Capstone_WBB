# 🌊 와바바 (WBB) — Watch the Best Bit

> KoBERT와 PP-OCRv3를 활용한 멀티모달 분석 기반 스트리밍 하이라이트 요약 웹 플랫폼
> A Multi-modal Streaming Highlight Summarization Web Platform using KoBERT and PP-OCRv3

신한대학교 소프트웨어융합학과 2026년도 캡스톤 디자인 프로젝트

## 팀 소개

| 역할 | 이름 |
|---|---|
| 팀장 / AI 파이프라인 | 송태섭 |
| 팀원 / OCR·백엔드 | 김관식 |
| 팀원 / 프론트엔드 | 고유찬 |

## 이게 뭐 하는 서비스인가요

몇 시간짜리 방송(유튜브·치지직·SOOP)을 그냥 다 보기엔 시간이 아깝잖아요. 채팅·화면·음성을 동시에 읽어서, **시청자가 진짜로 반응한 순간만** 자동으로 찾아 요약 영상으로 만들어드립니다.

- 링크 넣거나 파일 올리기만 하면 끝, 회원가입도 편집도 필요 없음
- 채팅창을 OCR로 직접 읽어서, 플랫폼 API 없이도 어떤 방송이든 동일하게 동작
- 채팅(텍스트) + 화면 변화(시각) + 음성 에너지(청각)를 함께 분석해서 "진짜 하이라이트"만 골라냄

## 핵심 기능

### AI 분석 파이프라인 (5단계)

| 단계 | 하는 일 | 사용 모델/도구 |
|---|---|---|
| 1 | 영상 프레임에서 채팅 텍스트 인식 | PP-OCRv3 (자체 파인튜닝) + Auto-ROI 자동 위치 탐지 |
| 2 | 채팅 감정 분석 (7가지 감정) | KoBERT (자체 파인튜닝) |
| 3 | 30초 슬라이딩 윈도우로 1차 하이라이트 후보 탐지 | 적응형 동적 임계점(Adaptive Threshold) |
| 4 | 스트리머 발화 기반 2차 정밀 검증 | Demucs(보컬 분리) + Whisper(STT) + KoBERT |
| 5 | 최종 하이라이트 클리핑 및 병합 | FFmpeg (무인코딩 Stream Copy) |

### 웹 서비스 기능

- **실시간 진행 상황 표시**: 분석 중 화면에 현재 몇 단계인지, 얼마나 걸렸는지 실시간으로 표시
- **결과 대시보드**: 와바바 스코어, 시간대별 감정 그래프("와바바 포인트" 하이라이트 마커 포함), 하이라이트별 개별 클립·채팅 로그
- **다운로드**: 전체 요약 영상 또는 하이라이트별 개별 클립 다운로드
- **최근 분석 내역**: 로그인 없이 브라우저에 최근 4시간 내 분석 기록 저장, video_id로 결과 페이지 바로가기
- **설정**: 라이트/다크 모드, 채팅창 위치 드래그 지정(Auto-ROI 보정), 알림, 데이터 보관 기간 안내
- **자동 데이터 삭제**: 로그인 없는 서비스 특성상, 4시간 지난 분석 결과는 자동으로 삭제

## 기술 스택

**Backend**: FastAPI, MongoDB(Motor), yt-dlp/Streamlink(다운로드), PaddleOCR, PyTorch, Whisper, Demucs, FFmpeg
**Frontend**: React, Vite, React Router, Recharts
**AI Models**: 자체 파인튜닝 KoBERT(감정 분석), 자체 파인튜닝 PP-OCRv3(한국어 채팅 인식)

## 프로젝트 구조

Capstone_WBB/
├── backend/
│ ├── server.py # FastAPI 서버, API 엔드포인트
│ ├── highlight_pipeline.py # 5단계 파이프라인 오케스트레이션
│ ├── ocr_worker_cli.py # OCR 전용 독립 실행 워커 (프로세스 격리)
│ ├── ppocr_chat_extractor.py # Step 1: OCR 채팅 추출
│ ├── automated_dataset_generator.py # Step 2: 감정 분석
│ ├── sliding_window_nlp.py # Step 3: 1차 하이라이트 탐지
│ ├── stage2_refinement.py # Step 4: Whisper+Demucs 정밀 검증
│ ├── ffmpeg_clipper.py # Step 5: 영상 클리핑
│ ├── chzzk_direct_downloader.py # 치지직 API 직접 다운로드 (yt-dlp 우회)
│ ├── soop_direct_downloader.py # SOOP 브라우저 자동화 다운로드
│ └── archive_data/ # KoBERT 학습용 라벨링 데이터
└── frontend/
└── src/
├── pages/ # Home, Result, Settings
└── components/ # Sidebar, Topbar, EmotionChart, HighlightCard 등


## 시작하기

### 백엔드

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

`.env` 파일 생성:
MONGODB_URL=mongodb://localhost:27017
DB_NAME=wbb_db
KOBERT_MODEL_DIR=./kobert_wbb_model
RETENTION_HOURS=4
`kobert_wbb_model/`, `models/wbb_rec/`(파인튜닝된 모델)은 용량 문제로 git에 포함되지 않았습니다 — 별도로 전달받아 `backend/` 안에 배치해야 합니다.

```powershell
.\run.ps1
```

### 프론트엔드

```powershell
cd frontend
npm install
npm run dev
```

## 알려진 제약사항

- **URL 자동 다운로드가 불안정합니다**: 유튜브(PO Token 정책 강화), 치지직(yt-dlp DASH 파서 버그), SOOP(streamlink가 VOD 미지원)이 각각 다른 이유로 자주 실패합니다. **파일 업로드 방식이 항상 안정적**이라 이쪽을 기본 경로로 권장합니다.
- **GPU 가속(PaddleOCR)이 이 환경에서는 CPU로 동작**: paddlepaddle-gpu와 PyTorch(CUDA)를 같은 프로세스에서 동시에 쓸 때 Windows에서 DLL 충돌이 발생해, OCR은 CPU로 안정적으로 실행됩니다.

## 라이선스

신한대학교 소프트웨어융합학과 2026년도 캡스톤 디자인 프로젝트 3조
