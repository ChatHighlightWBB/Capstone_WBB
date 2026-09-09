"""
=============================================================================
[와바바(WBB)] PP-OCRv3 인식(Recognition) 모델 파인튜닝 준비 스크립트
- 제안서 WBS 2.2.2 "한국어 가독성 향상을 위한 PP-OCRv3 파인튜닝 및
  인식률(Accuracy) 검증" 에 해당합니다.

[이 스크립트가 하는 일]
1) 합성 데이터셋의 라벨에서 실제 등장하는 문자 사전(dict)을 만듭니다.
2) PaddleOCR 공식 학습 코드가 요구하는 YAML 설정 파일을 생성합니다.
3) 다음에 실행할 명령어를 출력해줍니다.

[중요] 실제 학습은 PaddleOCR 공식 레포의 tools/train.py 로 수행합니다.
      이 스크립트는 그 학습에 필요한 설정과 사전을 만들어주는 역할입니다.
=============================================================================
"""

import os
import argparse


def build_char_dict(label_files, out_path):
    """라벨 파일들에서 등장하는 모든 문자를 모아 PaddleOCR 사전 파일 생성"""
    chars = set()
    for lf in label_files:
        if not os.path.exists(lf):
            continue
        with open(lf, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    chars.update(parts[1])

    # 공백은 PaddleOCR가 use_space_char 옵션으로 따로 처리하므로 사전에서 제외
    chars.discard(" ")
    sorted_chars = sorted(chars)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted_chars) + "\n")

    print(f"[사전] 총 {len(sorted_chars)}자 → {out_path}")
    return len(sorted_chars)


CONFIG_TEMPLATE = """# 와바바(WBB) PP-OCRv3 한국어 채팅 인식 파인튜닝 설정
# 자동 생성됨 - prepare_finetune.py
Global:
  use_gpu: true
  epoch_num: {epochs}
  log_smooth_window: 20
  print_batch_step: 20
  save_model_dir: {save_dir}
  save_epoch_step: 5
  eval_batch_step: [0, 500]
  cal_metric_during_train: true
  # 사전학습 가중치: 한국어 PP-OCRv3 인식 모델에서 이어서 학습합니다.
  pretrained_model: {pretrained}
  checkpoints:
  save_inference_dir:
  use_visualdl: false
  infer_img:
  character_dict_path: {dict_path}
  max_text_length: 40
  infer_mode: false
  use_space_char: true
  distributed: false
  save_res_path: {save_dir}/predicts.txt

Optimizer:
  name: Adam
  beta1: 0.9
  beta2: 0.999
  lr:
    name: Cosine
    # 파인튜닝이므로 처음부터 학습할 때보다 낮은 학습률을 씁니다.
    learning_rate: 0.0005
    warmup_epoch: 2
  regularizer:
    name: L2
    factor: 3.0e-05

Architecture:
  model_type: rec
  algorithm: SVTR_LCNet
  Transform:
  Backbone:
    name: MobileNetV1Enhance
    scale: 0.5
    last_conv_stride: [1, 2]
    last_pool_type: avg
  Head:
    name: MultiHead
    head_list:
      - CTCHead:
          Neck:
            name: svtr
            dims: 64
            depth: 2
            hidden_dims: 120
            use_guide: true
          Head:
            fc_decay: 0.00001
      - SARHead:
          enc_dim: 512
          max_text_length: 40

Loss:
  name: MultiLoss
  loss_config_list:
    - CTCLoss:
    - SARLoss:

PostProcess:
  name: CTCLabelDecode

Metric:
  name: RecMetric
  main_indicator: acc
  ignore_space: false

Train:
  dataset:
    name: SimpleDataSet
    data_dir: {data_dir}
    ext_op_transform_idx: 1
    label_file_list:
      - {train_label}
    transforms:
      - DecodeImage:
          img_mode: BGR
          channel_first: false
      - RecConAug:
          prob: 0.5
          ext_data_num: 2
          image_shape: [48, 320, 3]
      - RecAug:
      - MultiLabelEncode:
      - RecResizeImg:
          image_shape: [3, 48, 320]
      - KeepKeys:
          keep_keys:
            - image
            - label_ctc
            - label_sar
            - length
            - valid_ratio
  loader:
    shuffle: true
    batch_size_per_card: {batch_size}
    drop_last: true
    num_workers: 4

Eval:
  dataset:
    name: SimpleDataSet
    data_dir: {data_dir}
    label_file_list:
      - {val_label}
    transforms:
      - DecodeImage:
          img_mode: BGR
          channel_first: false
      - MultiLabelEncode:
      - RecResizeImg:
          image_shape: [3, 48, 320]
      - KeepKeys:
          keep_keys:
            - image
            - label_ctc
            - label_sar
            - length
            - valid_ratio
  loader:
    shuffle: false
    drop_last: false
    batch_size_per_card: {batch_size}
    num_workers: 2
"""


def main():
    ap = argparse.ArgumentParser(description="PP-OCRv3 인식 파인튜닝 설정 생성기")
    ap.add_argument("--dataset", default="./ocr_dataset", help="generate_ocr_dataset.py 출력 폴더")
    ap.add_argument("--out-config", default="./wbb_rec_finetune.yml")
    ap.add_argument("--dict-path", default="./wbb_chat_dict.txt")
    ap.add_argument("--save-dir", default="./output/wbb_rec")
    ap.add_argument("--pretrained", default="./pretrain/korean_PP-OCRv3_rec_train/best_accuracy",
                    help="사전학습 가중치 경로(확장자 제외)")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    data_dir = os.path.abspath(args.dataset)
    train_label = os.path.join(data_dir, "train_label.txt")
    val_label = os.path.join(data_dir, "val_label.txt")

    if not os.path.exists(train_label):
        print(f"❌ {train_label} 이 없습니다. generate_ocr_dataset.py 를 먼저 실행하세요.")
        return

    n_chars = build_char_dict([train_label, val_label], args.dict_path)

    config = CONFIG_TEMPLATE.format(
        epochs=args.epochs,
        save_dir=args.save_dir,
        pretrained=args.pretrained,
        dict_path=os.path.abspath(args.dict_path),
        data_dir=data_dir,
        train_label=train_label,
        val_label=val_label,
        batch_size=args.batch_size,
    )

    with open(args.out_config, "w", encoding="utf-8") as f:
        f.write(config)

    print(f"[설정] {args.out_config} 생성 완료 (문자 {n_chars}자)")
    print("\n" + "=" * 70)
    print("다음 단계 — PaddleOCR 공식 레포에서 아래 명령을 실행하세요:")
    print("=" * 70)
    print(f"""
# 1. PaddleOCR 레포 클론 (최초 1회)
git clone https://github.com/PaddlePaddle/PaddleOCR.git
cd PaddleOCR
pip install -r requirements.txt

# 2. 한국어 사전학습 인식 모델 다운로드 (최초 1회)
mkdir -p pretrain && cd pretrain
wget https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/korean_PP-OCRv3_rec_train.tar
tar -xf korean_PP-OCRv3_rec_train.tar
cd ..

# 3. 학습 시작
python tools/train.py -c {os.path.abspath(args.out_config)}

# 4. 학습된 모델을 추론용으로 변환
python tools/export_model.py \\
  -c {os.path.abspath(args.out_config)} \\
  -o Global.pretrained_model={args.save_dir}/best_accuracy \\
     Global.save_inference_dir=./inference/wbb_rec/
""")
    print("=" * 70)
    print("""
[변환 후 적용법] ppocr_chat_extractor.py 에서:

    self.ocr = PaddleOCR(
        lang="korean",
        use_angle_cls=True,
        rec_model_dir="./inference/wbb_rec/",        # ← 파인튜닝 모델
        rec_char_dict_path="./wbb_chat_dict.txt",    # ← 생성된 사전
        det_db_unclip_ratio=2.0,
    )
""")


if __name__ == "__main__":
    main()
