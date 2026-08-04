import glob
import os
import pandas as pd
from sklearn.model_selection import train_test_split


def create_unified_dataset():
    """[설명] 와바바(WBB) 프로젝트 데이터셋 통합 스크립트

    폴더 내 'wbb_labeling_work_*.csv' 파일들을 모두 읽어와 라벨 유효성을 검사하고
    Train(80%), Validation(20%) 데이터셋으로 자동 분할합니다.
    """
    print("🚀 [와바바 데이터셋 통합] 수집된 CSV 파일 병합을 시작합니다...")

    # 1. 'wbb_labeling_work_'로 시작하는 모든 CSV 파일 경로 탐색
    file_pattern = "wbb_labeling_work_*.csv"
    csv_files = glob.glob(file_pattern)

    if not csv_files:
        print(
            f"❌ '{file_pattern}' 패턴과 일치하는 CSV 파일을 찾을 수"
            " 없습니다."
        )
        return

    print(f"📂 발견된 데이터 파일 ({len(csv_files)}개): {csv_files}")

    all_dfs = []
    for file_path in csv_files:
        try:
            # 개별 CSV 파일 읽기
            df = pd.read_csv(file_path)

            # 필수 컬럼 존재 여부 확인
            if (
                "chat_message" in df.columns
                and "label" in df.columns
            ):
                all_dfs.append(df[["chat_message", "label"]])
            else:
                print(
                    f"⚠️ 경고: {file_path} 파일에 'chat_message' 또는 'label'"
                    " 컬럼이 없습니다."
                )
        except Exception as e:
            print(f"❌ {file_path} 읽기 실패: {str(e)}")

    if not all_dfs:
        print("❌ 유효한 데이터가 없습니다.")
        return

    # 2. 모든 데이터프레임 하나로 합치기
    merged_df = pd.concat(all_dfs, ignore_index=True)
    total_raw_count = len(merged_df)

    # 3. 라벨 전처리: 라벨이 비어있거나(NaN) 문자인 경우 정수형(0~6)으로 변환 및 정제
    merged_df = merged_df.dropna(subset=["label"])  # 라벨 빈 값 제거
    merged_df = merged_df[
        merged_df["label"] != ""
    ]  # 빈 문자열 제거

    # 라벨을 정수(int) 타입으로 변환
    merged_df["label"] = pd.to_numeric(
        merged_df["label"], errors="coerce"
    )
    merged_df = merged_df.dropna(subset=["label"])
    merged_df["label"] = merged_df["label"].astype(int)

    # 유효 라벨 범위(0~6) 데이터만 필터링
    merged_df = merged_df[
        (merged_df["label"] >= 0) & (merged_df["label"] <= 6)
    ]

    clean_count = len(merged_df)
    print(
        f"\n📊 데이터 정제 완료: 원본 {total_raw_count}줄 ➔ 유효"
        f" 데이터 {clean_count}줄"
    )

    # 4. Train(80%) / Validation(20%) 데이터셋 분할
    train_df, val_df = train_test_split(
        merged_df,
        test_size=0.2,
        random_state=42,
        stratify=merged_df["label"],  # 라벨 비율 균등 분할
    )

    # 5. 저장
    train_output = "wbb_kobert_train.csv"
    val_output = "wbb_kobert_val.csv"

    train_df.to_csv(train_output, index=False, encoding="utf-8-sig")
    val_df.to_csv(val_output, index=False, encoding="utf-8-sig")

    print("\n🎯 데이터셋 생성 완료!")
    print(f" - 학습용 데이터 ({train_output}): {len(train_df)}줄")
    print(f" - 검증용 데이터 ({val_output}): {len(val_df)}줄")


if __name__ == "__main__":
    create_unified_dataset()