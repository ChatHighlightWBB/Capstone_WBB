import glob
import os
import pandas as pd
from sklearn.model_selection import train_test_split


def build_clean_wbb_dataset():
  """[설명] wbb_labeling_work_*.csv 원본 파일들을 통합하되,

  원본 라벨 번호(0~6)를 어떠한 변형도 없이 그대로 보존하고,
  '.' 등 유효하지 않은 오기입 라벨만 자동 제거하여 train/val CSV를 만드는
  스크립트.
  """
  raw_files = glob.glob("wbb_labeling_work_*.csv")
  if not raw_files:
    print(
        "❌ 원본 라벨링 파일(wbb_labeling_work_*.csv)을 찾을 수 없습니다."
    )
    return

  print(
      f"📂 원본 라벨링 파일 {len(raw_files)}개 발견. 라벨 변형 없이 정제"
      " 시작..."
  )

  df_list = []
  for file in raw_files:
    try:
      temp_df = pd.read_csv(file)
      if "chat_message" in temp_df.columns and "label" in temp_df.columns:
        temp_df = temp_df[["chat_message", "label"]].dropna()

        # '.' 문자 등 숫자가 아닌 불량 라벨을 NaN으로 변환 후 제거
        temp_df["label"] = pd.to_numeric(temp_df["label"], errors="coerce")
        temp_df = temp_df.dropna(subset=["label"])
        temp_df["label"] = temp_df["label"].astype(int)

        # 공식 라벨 범주 0~6 사이 값만 추출
        temp_df = temp_df[temp_df["label"].between(0, 6)]
        df_list.append(temp_df)
    except Exception as e:
      print(f"⚠️ {file} 읽기 건너뜀: {str(e)}")

  if not df_list:
    print("❌ 유효한 라벨링 데이터가 없습니다.")
    return

  full_df = pd.concat(df_list, ignore_index=True)

  # 중복 채팅 제거
  full_df = full_df.drop_duplicates(subset=["chat_message"]).reset_index(
      drop=True
  )

  print(f"✅ 불량 라벨 정제 완료! 유효 데이터 총 {len(full_df)}줄")

  # Train(80%) / Val(20%) 층화 추출(Stratified Split) 분할
  train_df, val_df = train_test_split(
      full_df, test_size=0.2, random_state=42, stratify=full_df["label"]
  )

  train_df.to_csv("wbb_kobert_train.csv", index=False, encoding="utf-8-sig")
  val_df.to_csv("wbb_kobert_val.csv", index=False, encoding="utf-8-sig")

  print(
      f"🎉 클린 재구축 완료! -> 학습용: {len(train_df)}줄 | 검증용:"
      f" {len(val_df)}줄"
  )


if __name__ == "__main__":
  build_clean_wbb_dataset()