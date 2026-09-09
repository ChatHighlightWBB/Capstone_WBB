import pandas as pd
from sklearn.utils import resample


def augment_minority_classes():
  """[설명] wbb_kobert_train.csv에서 부족한 소수 감정(1~5번) 데이터를

  오버샘플링(Oversampling)하여 데이터 불균형을 해소하는 스크립트.
  """
  train_path = "wbb_kobert_train.csv"
  try:
    df = pd.read_csv(train_path)
  except Exception as e:
    print(f"❌ 파일 읽기 실패: {str(e)}")
    return

  print("🚀 [와바바 데이터 증강] 소수 감정 클래스 오버샘플링 작업 시작...")

  # 라벨별 데이터 분리
  df_majority = df[df["label"] == 6]  # 중립 (7000+ 개)
  df_list = [df_majority]

  # Target 샘플 수: 소수 감정들을 각각 1,200개 수준으로 증강
  TARGET_SAMPLES = 1200

  for label_idx in range(6):
    df_class = df[df["label"] == label_idx]
    count = len(df_class)

    if count < TARGET_SAMPLES and count > 0:
      # 부족한 감정 데이터를 복제 업샘플링
      df_oversampled = resample(
          df_class, replace=True, n_samples=TARGET_SAMPLES, random_state=42
      )
      df_list.append(df_oversampled)
      print(f"  - 라벨 [{label_idx}] 기존 {count}개 ➔ {TARGET_SAMPLES}개로 증강 완료")
    else:
      df_list.append(df_class)

  # 데이터 통합 및 셔플
  augmented_df = (
      pd.concat(df_list).sample(frac=1, random_state=42).reset_index(drop=True)
  )
  augmented_df.to_csv(train_path, index=False, encoding="utf-8-sig")

  print(
      f"\n🎉 증강 완료! 새로운 'wbb_kobert_train.csv' 총 데이터 수:"
      f" {len(augmented_df)}줄"
  )


if __name__ == "__main__":
  augment_minority_classes()