# requirements.txt 누락 메모

- `paddlepaddle` 이 requirements.txt 에 없어서, 이 파일로 새 venv 를 만들면 OCR(PaddleOCR)이 동작하지 않음. paddlepaddle 을 requirements.txt 에 추가해야 함.
- 참고: 현재 backend venv 에는 `paddlepaddle==3.3.1` 과 `paddlepaddle-gpu==3.2.2` 가 둘 다 설치돼 있음 (2026-09-29 기준). 어느 쪽을 넣을지 정리할 때 확인 필요.
