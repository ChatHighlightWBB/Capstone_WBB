# PP-OCRv3 채팅 인식 파인튜닝 (WBS 2.2.1 / 2.2.2)

인식률이 낮은 이유는 두 가지입니다. 하나는 전처리 설정 문제(이미 `ppocr_chat_extractor.py`에서 수정 완료), 다른 하나는 **범용 사전학습 모델을 그대로 쓰고 있어서**입니다. 이 폴더는 후자를 해결합니다.

---

## 준비물 (팀이 직접 챙겨야 하는 것)

### 1. 폰트 파일 → `fonts/` 폴더에 넣기

방송 채팅창에서 쓰이는 것과 비슷한 한국어 폰트 `.ttf` 파일을 3~6개 정도 넣으세요. 완전히 똑같을 필요는 없고, 굵기와 스타일이 다양할수록 좋습니다. 무료로 쓸 수 있는 것들:

- 나눔고딕 / 나눔스퀘어 (네이버, 무료 배포)
- Pretendard (오픈소스)
- 프리텐다드, 에스코어드림, 지마켓산스 등 무료 상업용 한글 폰트
- Windows 사용자는 `C:/Windows/Fonts/malgun.ttf` (맑은 고딕)도 복사해서 쓸 수 있음

> `fonts/` 폴더가 비어 있으면 시스템에 설치된 Noto Sans CJK로 자동 폴백됩니다. 동작은 하지만, 폰트가 한 종류뿐이면 실제 방송 폰트에 대한 일반화 성능이 떨어지니 꼭 몇 개 넣어주세요.

### 2. 채팅 어휘 목록 → `build_vocab.py`로 생성

어휘 파일은 단순히 문장을 모으는 게 아니라 **한글 문자 커버리지**를 확인하며 만들어야 합니다. OCR 사전(dict)은 어휘 파일에 등장한 문자만으로 구성되고, **사전에 없는 글자는 화면에 아무리 선명해도 모델이 출력 자체를 못 합니다.**

여러 소스를 합쳐서 만드세요:

```bash
python build_vocab.py \
  --csv extracted_ocr_chats.csv:chat_text \
  --csv aihub_감성대화.csv:sentence \
  --out vocab/chat_vocab.txt
```

**권장 소스 조합:**

| 소스 | 역할 |
|---|---|
| `extracted_ocr_chats.csv` | 실제 방송 채팅 — 도메인 일치도 최상 |
| AI Hub 감성 대화 말뭉치 | 한글 문자 커버리지 확보 (KoBERT 학습에 쓴 것 재활용) |
| 내장 슬랭 목록 | ㅋㅋㅋ, ㄷㄷ 등 비정형 자음 — 자동으로 15% 섞임 |

스크립트가 자동으로 처리하는 것: URL·숫자만 있는 줄 제거, 중복 제거, 너무 길거나 짧은 줄 제외, 슬랭 비율 보정.

**실행 후 출력되는 "고유 한글 문자 수"를 꼭 확인하세요.** 500자 미만이면 경고가 뜨는데, 그 상태로 학습하면 실제 방송에서 사전에 없는 글자가 나올 때 인식이 불가능합니다. AI Hub 말뭉치를 추가하면 보통 1,500~2,000자 수준까지 올라갑니다.

주요 옵션:
- `--txt 파일.txt` — CSV 말고 일반 텍스트 파일도 추가 가능 (여러 번 지정 가능)
- `--slang-ratio 0.25` — 슬랭 비율 조정 (기본 0.15)
- `--max-lines 20000` — 최종 줄 수 제한

---

## 실행 순서

### Step 0. 어휘 파일 생성

```bash
python build_vocab.py \
  --csv extracted_ocr_chats.csv:chat_text \
  --csv aihub_감성대화.csv:sentence \
  --out vocab/chat_vocab.txt
```

### Step 1. 합성 데이터셋 생성

```bash
python generate_ocr_dataset.py \
  --video ./test_sample.mp4 \
  --fonts ./fonts \
  --vocab ./vocab/chat_vocab.txt \
  --out ./ocr_dataset \
  --num 5000
```

`--video`에 실제 방송 영상을 넣으면 그 영상의 프레임을 배경으로 써서 훨씬 현실적인 데이터가 만들어집니다 (게임 화면 위에 반투명 채팅이 얹힌 상황 재현). 생략하면 합성 배경으로 대체됩니다.

**생성 후 반드시 `ocr_dataset/train/` 안의 이미지 몇 장을 열어보세요.** 사람 눈으로 못 읽을 정도면 모델도 못 배웁니다. 너무 뭉개졌으면 `render_sample()` 안의 열화 확률을 낮추세요.

### Step 2. 학습 설정 파일 생성

```bash
python prepare_finetune.py --dataset ./ocr_dataset
```

라벨에 등장하는 문자만 모아 사전(`wbb_chat_dict.txt`)을 만들고, 학습용 YAML(`wbb_rec_finetune.yml`)을 생성합니다. 실행이 끝나면 다음에 칠 명령어를 그대로 출력해줍니다.

### Step 3. 학습 (PaddleOCR 공식 레포에서)

```bash
git clone https://github.com/PaddlePaddle/PaddleOCR.git
cd PaddleOCR
pip install -r requirements.txt

# 한국어 사전학습 인식 모델 받기
mkdir -p pretrain && cd pretrain
wget https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/korean_PP-OCRv3_rec_train.tar
tar -xf korean_PP-OCRv3_rec_train.tar
cd ..

# 학습 시작
python tools/train.py -c /경로/wbb_rec_finetune.yml
```

GPU 기준 5000장 / 50 epoch이면 대략 1~3시간 정도 걸립니다. Colab T4에서도 충분합니다.

### Step 4. 추론용 모델로 변환

```bash
python tools/export_model.py \
  -c /경로/wbb_rec_finetune.yml \
  -o Global.pretrained_model=./output/wbb_rec/best_accuracy \
     Global.save_inference_dir=./inference/wbb_rec/
```

### Step 5. 인식률 검증 (발표 자료용 수치)

파인튜닝 전후를 같은 검증셋으로 비교합니다.

```bash
# 베이스라인
python evaluate_ocr.py --dataset ./ocr_dataset

# 파인튜닝 후
python evaluate_ocr.py --dataset ./ocr_dataset \
  --rec-model-dir ./inference/wbb_rec/ \
  --rec-char-dict-path ./wbb_chat_dict.txt
```

"정확 일치율 XX% → YY%로 개선" 형태로 나오니 최종 보고서에 그대로 쓸 수 있습니다.

### Step 6. 실제 파이프라인에 적용

`ppocr_chat_extractor.py`의 생성자를 수정합니다:

```python
self.ocr = PaddleOCR(
    lang="korean",
    use_angle_cls=True,
    rec_model_dir="./inference/wbb_rec/",       # 파인튜닝 모델
    rec_char_dict_path="./wbb_chat_dict.txt",   # 생성된 사전
    det_db_unclip_ratio=2.0,
)
```

---

## 참고 사항

- **detection이 아니라 recognition만 파인튜닝합니다.** 글자 위치를 찾는 detection은 대체로 잘 동작하고, 문제는 "찾은 글자가 뭔지 읽는" recognition 쪽인 경우가 대부분이라 비용 대비 효과가 좋습니다. Step 1의 디버그 이미지에서 글자 박스는 잘 잡히는데 텍스트만 틀린다면 이 진단이 맞습니다.
- **사전(dict) 범위 주의**: 생성된 사전은 합성 데이터에 등장한 문자만 포함합니다. 어휘 목록이 빈약하면 실제 방송에서 나온 못 보던 글자를 아예 출력할 수 없게 됩니다. 어휘를 충분히 다양하게 넣으세요.
- **학습 데이터가 실제와 너무 다르면 역효과**입니다. 폰트/배경이 실제 방송과 동떨어지면 합성 데이터에만 과적합됩니다. `--video`로 실제 영상을 넣는 게 중요한 이유입니다.
