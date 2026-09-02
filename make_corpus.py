import os
import pandas as pd

def find_text_column(df: pd.DataFrame) -> str:
    """
    [설명] 
    CSV 파일 내에서 텍스트 데이터가 들어있는 컬럼명을 자동으로 찾아냅니다.
    """
    # 1. 흔히 사용되는 텍스트 컬럼 후보군 우선 검색
    candidate_cols = ["chat_text", "sentence", "text", "chat", "document", "content", "발화"]
    for col in candidate_cols:
        if col in df.columns:
            return col
            
    # 2. 후보군에 없으면 문자열(object) 타입인 컬럼 중 첫 번째 선택
    for col in df.columns:
        if df[col].dtype == "object":
            return col
            
    # 3. 모두 실패 시 첫 번째 컬럼 반환
    return df.columns[0]

def extract_corpus(output_txt: str = "chat_corpus.txt"):
    print("=" * 60)
    print("🔍 [단어장 자동 추출] CSV 텍스트 컬럼 자동 탐색 시작...")
    print("=" * 60)
    
    all_texts = []
    target_files = ["extracted_ocr_chats.csv", "wbb_kobert_train.csv"]
    
    for filename in target_files:
        if not os.path.exists(filename):
            print(f"⚠️ '{filename}' 파일이 존재하지 않아 스킵합니다.")
            continue
            
        try:
            df = pd.read_csv(filename)
            text_col = find_text_column(df)
            print(f" ➔ [{filename}] 감지된 텍스트 컬럼: '{text_col}' (총 {len(df)}행)")
            
            # 결측치 제외 및 문자열 변환
            valid_texts = df[text_col].dropna().astype(str).tolist()
            all_texts.extend(valid_texts)
        except Exception as e:
            print(f" ❌ [{filename}] 읽기 실패: {e}")

    # 중복 제거 및 공백 정리
    unique_texts = []
    seen = set()
    for text in all_texts:
        cleaned = text.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_texts.append(cleaned)
            
    # chat_corpus.txt 파일로 저장
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(unique_texts))
        
    print("=" * 60)
    print(f"✅ [추출 완료] 중복 제거된 고유 문장 수: {len(unique_texts)}개")
    print(f" ➔ 생성된 파일: '{output_txt}'")
    print("=" * 60)

if __name__ == "__main__":
    extract_corpus()