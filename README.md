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

<pre> ```Capstone_WBB/
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
└── components/ # Sidebar, Topbar, EmotionChart, HighlightCard 등 ``` </pre>


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

---

## 변경 사항 (2026-10-03, 커밋 `3b7d6da`)

이전 버전(`d4d5cb5`)과 비교해 달라진 점입니다.

### 프론트엔드

**새로 추가**
- **마스코트 "바바"** (`Mascot.jsx`, `BabaSays.jsx`): 채팅 말풍선 모양 캐릭터. 표정(happy / excited / thinking / oops / working)에 따라 사이드바, 히어로, 분석 진행 화면, 결과 화면에서 안내 말풍선을 띄웁니다.
- **바바 소개 섹션** (`BabaIntro.jsx`): 홈 화면 하단에 추가되고, 사이드바에 "바바 소개" 링크가 생겼습니다.
- **시작 안내 화면** (`WelcomeOverlay.jsx`): 페이지를 처음 열면 뜹니다. "하루 동안 보지 않기"를 고르면 24시간 동안 다시 뜨지 않습니다. 여기서 "시작하기"를 누르면 그 뒤로 예시 영상에 마우스를 올렸을 때 소리가 바로 나옵니다.
- **오류 대처 방법 페이지** (`/help`, `Help.jsx`): 화면에 뜬 오류 문구별로 해결 방법을 정리했습니다. 사이드바 하단과 분석 실패 화면에서 바로 이동할 수 있습니다.
- **이용약관·개인정보처리방침 페이지** (`/terms`, `/privacy`, `Legal.jsx`): 푸터에 링크를 추가했습니다.
- **예시 영상** (`frontend/public/videos/short1~6.mp4`): 히어로 캐러셀의 회색 자리표시자를 실제 짧은 영상으로 바꿨습니다.

**수정**
- **분석 진행 화면**: 단계마다 바바가 지금 하는 일을 말풍선으로 알려줍니다. 3분이 넘으면 "닫지 말고 기다려 달라"는 안내가 추가로 뜹니다.
- **결과 화면**
  - 와바바 스코어에 따라 바바가 한마디 합니다.
  - 결과가 4시간 뒤 사라진다는 안내를 추가했습니다.
  - 하이라이트가 0개이거나 분석에 실패하면 바바가 이유와 오류 대처 페이지 링크를 보여줍니다.
- **홈 화면 문구**
  - 히어로·기능 소개·이용 방법 문구를 실제로 구현된 동작에 맞게 다시 썼습니다.
  - 이용 방법 단계 칩에 마우스를 올리면 상세 설명이 나옵니다.
- **사이드바·푸터**: 로고를 마스코트로 바꾸고, 푸터에 학과와 팀 정보를 넣었습니다. 다른 페이지에서 푸터 메뉴를 누르면 홈으로 돌아가 해당 섹션으로 이동합니다.
- `App.css`: 위 컴포넌트에 쓰는 스타일을 추가했습니다(약 +500줄).

**제거·되돌아간 부분** (확인이 필요합니다)
- **업로드 전 미리보기와 채팅창 드래그 지정 기능(커밋 `110ad10`)이 빠졌습니다.**
  - `UploadForm.jsx`의 미리보기 UI와 `videoFrame.js`가 삭제돼, 파일을 고르면 바로 업로드됩니다.
  - 홈 화면 "이용 방법"에는 아직 "미리보기 화면에서 드래그해 직접 정할 수 있다"는 문구가 남아 있습니다.
- **API 요청에서 `ngrok-skip-browser-warning` 헤더가 빠졌습니다.** ngrok으로 서버를 공개하면 응답 대신 경고 페이지가 올 수 있습니다.

### 백엔드

- **OCR 워커의 cuDNN 충돌 수정** (`ocr_worker_cli.py`)
  - 증상: paddlex가 modelscope를 통해 torch를 불러오고, torch(cuDNN 9.10)와 paddle(cuDNN 9.5)이 부딪혀 `WinError 127 (cudnn_cnn64_9.dll)`로 OCR이 실패했습니다.
  - 수정: OCR 워커 프로세스에서만 torch를 불러오지 못하게 막았습니다.
- **한글 사용자 폴더 경로 문제 수정** (`ppocr_chat_extractor.py`)
  - 증상: Paddle 추론 엔진이 `C:\Users\<한글이름>\.paddlex` 경로의 모델 파일을 열지 못했습니다.
  - 수정: 사용자 폴더 이름이 영문이 아니면 모델 캐시로 `backend/models/paddlex_cache`를 씁니다.
- **OCR 실행 장치 선택(`OCR_DEVICE`) 추가**: `.env`에서 `cpu` / `gpu` / `auto` 중 고릅니다. 기본값 `auto`는 Windows에서 CPU, 그 외에서 GPU를 먼저 시도합니다.
- **하이라이트 0개 처리 복구** (`highlight_pipeline.py`): 1차 후보가 없으면 4~5단계를 건너뛰고 "하이라이트 0개"로 정상 종료합니다. 이전에는 `final_highlight_candidates.json` 파일이 없다는 오류로 분석이 실패했습니다.
- **만료 파일 정리 강화** (`server.py`): 보관 시간이 지나면 합친 요약 영상뿐 아니라 하이라이트별 개별 클립(`{video_id}_highlight_*.mp4`)도 지웁니다. DB 기록 없이 남은 옛날 파일도 함께 정리합니다.
- **되돌아간 부분** (확인이 필요합니다)
  - **Linux/Colab에서 OCR을 같은 프로세스로 실행하던 분기(커밋 `f0679c3`)가 빠졌습니다.** 이제 모든 OS에서 OCR을 별도 프로세스로 실행합니다.
  - **KoBERT 토크나이저 로딩**(`automated_dataset_generator.py`, `stage2_refinement.py`)이 `monologg/kobert` 대신 `kobert_wbb_model` 폴더의 토크나이저를 쓰는 방식으로 돌아갔습니다. 현재 PC에서는 한글이 `[UNK]` 없이 정상적으로 토큰화되는 것을 확인했습니다.
