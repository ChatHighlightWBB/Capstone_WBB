# 🎬 WBB (와바바) - Multi-modal Streaming Highlight Summarizer

> **KoBERT와 PP-OCRv3를 활용한 멀티모달 분석 기반 스트리밍 하이라이트 요약 웹 플랫폼**

---

## 📌 프로젝트 개요
긴 스트리밍 다시보기(VOD) 영상에서 **시청자 채팅(PP-OCRv3/KoBERT)**, **시각적 역동성(OpenCV)**, **음향 에너지(Librosa)**를 결합하여 핵심 구간을 자동 검출하고 무인코딩(Stream Copy)으로 고속 추출하는 통합 파이프라인 시스템입니다.

* **브랜치명**: `integration/e2e-working-v1`
* **브랜치 목적**: 프론트엔드-백엔드-AI 추론 간 End-to-End(E2E) 데이터 통신 및 통합 검증

---

## 📂 저장소 디렉터리 구조
```text
Capstone_WBB/
├── backend/          # FastAPI 서버, 듀얼 스트림 파싱, FFmpeg 클리핑 엔진
├── frontend/         # React 웹 대시보드, 타임라인 감정 시각화 UI
└── ocr_finetune/     # 스트리밍 폰트/배경 노이즈 대응 PP-OCRv3 학습 파이프라인
