# 와바바(WBB) — 4개 zip 병합 결과

`frontend.zip`, `feature-backend.zip`, `feature-ai-nlp.zip`, `feature-ai-ocr.zip` 4개를
검토해서 병합했습니다. 실제로 빌드/문법 검증까지 마쳤습니다.

## 각 zip에서 무엇을 가져왔나

| 소스 | 가져온 것 | 안 가져온 것 |
|---|---|---|
| (기존 검증본, integration/e2e-working-v1과 동일) | 백엔드 전체 뼈대 — 버그 수정된 `server.py`, `highlight_pipeline.py`, Auto-ROI 병합된 `ppocr_chat_extractor.py` | — |
| `feature-ai-ocr.zip` | **파인튜닝된 OCR 인식 모델** (`inference/wbb_rec/*` → `backend/models/wbb_rec/`), `wbb_chat_dict.txt` | `ai_model/ocr/ocr_test.py`는 `print()` 한 줄뿐이라 안 가져옴 |
| `feature-ai-nlp.zip` | (참고만 함) | `ppocr_chat_extractor.py`가 구버전(`use_gpu` 버그, `.ocr()` 구API)이라 안 씀 — 검증본 유지 |
| `feature-backend.zip` | (참고만 함) | 여전히 더미 로직, 죽은 코드(ocr_processor.py 등 4개 미사용) — 안 씀 |
| `frontend.zip` | 프론트엔드 전체 (Footer 빼고) | `Footer.jsx`가 없어서 추가, `api.js`에 배포용 `API_BASE` 환경변수 처리가 없어서 교체 |

## 실제로 검증한 것

- `backend/*.py` 전체 `python -m py_compile` 통과
- `ppocr_chat_extractor.py`가 파인튜닝 모델을 실제로 찾아서 쓰는지 로직 시뮬레이션 통과
- `npm run build` 성공 (프론트엔드 854개 모듈 정상 변환)

## 폴더 구조

```
backend/
├── models/wbb_rec/          ← [신규] 파인튜닝된 OCR 인식 모델
│   ├── inference.json
│   ├── inference.pdiparams
│   └── inference.yml
├── wbb_chat_dict.txt         ← [신규] 파인튜닝 시 사용한 문자 사전
├── ppocr_chat_extractor.py   ← [수정] 위 모델을 자동으로 찾아서 사용
├── server.py                 ← (기존 검증본) 업로드 API, 4시간 자동삭제 스케줄러 포함
├── highlight_pipeline.py     ← (기존 검증본) crop_box=None 기본값 (Auto-ROI)
└── ... (나머지 파이프라인 파일 동일)

frontend/
├── src/components/Footer.jsx ← [신규 추가]
├── src/api.js                ← [교체] VITE_API_BASE 환경변수 지원
├── src/App.css                ← [추가] 푸터 스타일 병합
└── ... (나머지 동일)
```

## 아직 사용자가 직접 해야 할 것

### 1. KoBERT 파인튜닝 모델 (용량 문제로 미포함)

`backend/kobert_wbb_model/` 폴더에 직접 옮겨주세요:
```
config.json
model.safetensors
tokenizer.json
tokenizer_config.json
```

### 2. `.env` 파일 생성

```
MONGODB_URL=mongodb://localhost:27017   (또는 Atlas 주소)
DB_NAME=wbb_db
KOBERT_MODEL_DIR=./kobert_wbb_model
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
RETENTION_HOURS=4
```
`CHAT_CROP_BOX`는 넣지 마세요 (Auto-ROI 자동 적용).

### 3. 패키지 설치

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install python-multipart soundfile apscheduler
```

### 4. 실행 및 확인

```powershell
uvicorn server:app --reload --port 8000
```

로그에 이게 뜨면 파인튜닝 모델이 정상적으로 연결된 겁니다:
```
🎯 파인튜닝된 채팅 인식 모델(models/wbb_rec)을 사용합니다.
```

## 병합하면서 발견한 것 — 팀 커뮤니케이션 확인 필요

`feature/ai-nlp`에 있던 `ppocr_chat_extractor.py`가 여전히 구버전(`use_gpu=False` 등 이미
고쳤던 버그가 있는 상태)이었습니다. 즉 그 브랜치에서 작업하시는 분이 최신 통합 버전
(`integration/e2e-working-v1`)의 존재를 모르고 계실 가능성이 있어요. 헛수고를 막으려면
한 번 확인해보시는 걸 권합니다.
