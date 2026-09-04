"""
=============================================================================
[와바바(WBB)] 2단계: KoBERT 채팅 감정 분석 및 시계열 데이터 생성기
- 담당자: 송태섭 (책임개발자)
- 역할:
  - 추출된 채팅 텍스트를 Fine-tuned KoBERT 모델에 통과시켜 7대 감정 확률 산출
  - 맥락 인지형 룰 부스터(조소/비아냥 판별 및 비정형 자음 ㅋㅋㅋㅋ 보정) 적용
  - KoBERT vocab 및 token_type_ids 인덱스 범위 초과 방어 로직 내장
  - 영상 전체 평균 점수 기반 동적 임계점(Adaptive Threshold) 자동 계산
- 입력: extracted_ocr_chats.csv
- 출력: video_emotion_timeseries.csv, video_emotion_timeseries.json
=============================================================================
"""

import os
import re
import json
import torch
import numpy as np
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification

def apply_context_aware_sentiment_booster(chat_text: str, emotion_probs: np.ndarray) -> np.ndarray:
    """
    KoBERT가 예측한 7대 감정 확률에 스트리밍 특화 자음 및 문맥 규칙을 적용합니다.
    라벨 매핑: 0:기쁨, 1:당황, 2:분노, 3:불안, 4:상처, 5:슬픔, 6:중립
    """
    probs = np.copy(emotion_probs)
    text = str(chat_text).strip()

    negative_triggers = [
        "에휴", "멍청", "노답", "망했", "개못", "발컨", "벌레", "트롤", 
        "아니", "왜저", "답답", "극혐", "까비", "뇌절", "똥싸", "역겹"
    ]
    
    positive_triggers = [
        "나이스", "대박", "와", "지렸다", "레전드", "갓", "폼미쳤", "캐리"
    ]

    has_negative = any(trigger in text for trigger in negative_triggers)
    has_positive = any(trigger in text for trigger in positive_triggers)

    joy_count = len(re.findall(r'ㅋ|ㅎ|ㄲ|캬|크', text))
    sad_count = len(re.findall(r'ㅠ|ㅜ|ㄱ-|ㅡㅡ', text))
    surprise_count = len(re.findall(r'\?|!|ㄷ|헐|엥|오', text))

    if has_negative:
        if joy_count >= 1:
            boost_val = 0.35
            probs[2] += boost_val * 0.7
            probs[1] += boost_val * 0.3
            probs[0] = max(0.01, probs[0] - 0.25)
            probs[6] = max(0.01, probs[6] - boost_val)
        else:
            probs[2] += 0.4
            probs[6] = max(0.01, probs[6] - 0.4)
            
    elif has_positive or (joy_count >= 2 and not has_negative):
        boost_val = min(0.50, 0.15 * max(1, joy_count))
        probs[0] += boost_val
        probs[6] = max(0.01, probs[6] - boost_val)
        
    if sad_count >= 2 and not has_positive:
        boost_sad = min(0.45, 0.15 * sad_count)
        probs[5] += boost_sad
        probs[6] = max(0.01, probs[6] - boost_sad)

    if surprise_count >= 2 and not has_negative:
        boost_sur = min(0.40, 0.15 * surprise_count)
        probs[1] += boost_sur
        probs[6] = max(0.01, probs[6] - boost_sur)

    probs = np.clip(probs, 0.001, None)
    return probs / np.sum(probs)


class WBBEmotionDatasetGenerator:
    """
    파인튜닝된 KoBERT 모델을 통해 채팅 데이터의 7대 감정을 정량화하고
    시계열 JSON/CSV 데이터를 생성하는 핵심 분석 클래스
    """
    def __init__(self, model_dir: str = "./kobert_wbb_model"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.labels = ['기쁨', '당황', '분노', '불안', '상처', '슬픔', '중립']
        
        try:
            from tokenization_kobert import KoBERTTokenizer
            self.tokenizer = KoBERTTokenizer.from_pretrained(model_dir)
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
            
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir, num_labels=7)
        self.model.to(self.device)
        self.model.eval()

    def predict_emotion(self, text: str):
        clean_text = str(text).strip()
        if not clean_text:
            clean_text = "..."

        inputs = self.tokenizer(
            clean_text, 
            return_tensors="pt", 
            truncation=True, 
            max_length=64, 
            padding=True
        )
        
        vocab_size = getattr(self.model.config, "vocab_size", 8002)
        inputs["input_ids"] = torch.clamp(inputs["input_ids"], 0, vocab_size - 1)

        if "token_type_ids" in inputs:
            inputs["token_type_ids"] = torch.zeros_like(inputs["input_ids"])

        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            raw_probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]

        boosted_probs = apply_context_aware_sentiment_booster(clean_text, raw_probs)
        top_idx = int(np.argmax(boosted_probs))
        
        return self.labels[top_idx], boosted_probs

    def generate_dataset(
        self, 
        input_csv_path: str = "extracted_ocr_chats.csv", 
        output_csv_path: str = "video_emotion_timeseries.csv", 
        output_json_path: str = "video_emotion_timeseries.json"
    ):
        if not os.path.exists(input_csv_path):
            df_input = pd.DataFrame([
                {"timestamp": 10.0, "chat_text": "와 대박 ㅋㅋㅋㅋ"},
                {"timestamp": 25.0, "chat_text": "에휴 멍청하네 ㅋㅋ"},
                {"timestamp": 45.0, "chat_text": "나이스 레전드"}
            ])
        else:
            df_input = pd.read_csv(input_csv_path)

        text_col = "chat_text" if "chat_text" in df_input.columns else df_input.columns[-1]
        time_col = "timestamp" if "timestamp" in df_input.columns else df_input.columns[0]

        results_list = []
        joy_scores = []

        for _, row in df_input.iterrows():
            t_val = float(row[time_col]) if str(row[time_col]).replace('.', '', 1).isdigit() else 0.0
            msg = str(row[text_col])
            
            top_emo, probs = self.predict_emotion(msg)
            
            # [수정됨] 확률(0~1)을 백분율(0~100)로 변환하여 저장
            joy_pct = float(probs[0] * 100.0)
            joy_scores.append(joy_pct)

            # [수정됨] 3단계 모듈과의 호환성을 위해 키 이름을 _prob에서 _pct로 변경
            record = {
                "timestamp": t_val,
                "chat_text": msg,
                "top_emotion": top_emo,
                "joy_pct": round(joy_pct, 2),
                "embarrass_pct": round(float(probs[1] * 100.0), 2),
                "anger_pct": round(float(probs[2] * 100.0), 2),
                "anxiety_pct": round(float(probs[3] * 100.0), 2),
                "hurt_pct": round(float(probs[4] * 100.0), 2),
                "sadness_pct": round(float(probs[5] * 100.0), 2),
                "neutral_pct": round(float(probs[6] * 100.0), 2)
            }
            results_list.append(record)

        df_output = pd.DataFrame(results_list)
        
        mean_joy = np.mean(joy_scores) if joy_scores else 20.0
        std_joy = np.std(joy_scores) if joy_scores else 5.0
        recommended_threshold = float(mean_joy + 0.5 * std_joy)

        meta_data = {
            "total_chats_analyzed": len(df_output),
            "recommended_joy_threshold": round(recommended_threshold, 2),
            "time_series_data": results_list
        }

        df_output.to_csv(output_csv_path, index=False, encoding="utf-8-sig")

        with open(output_json_path, "w", encoding="utf-8") as jf:
            json.dump(meta_data, jf, ensure_ascii=False, indent=2)

        print("\n" + "=" * 75)
        print("[4/4 데이터셋 생성 완료]")
        print(f"1. CSV 파일: {output_csv_path} (총 {len(df_output)}행)")
        print(f"2. JSON 파일: {output_json_path}")
        print(f"3. 산출된 동적 임계점: 기쁨(Joy) {recommended_threshold:.1f}% 이상")
        print("=" * 75)

        return meta_data


if __name__ == "__main__":
    generator = WBBEmotionDatasetGenerator(model_dir="./kobert_wbb_model")
    generator.generate_dataset()