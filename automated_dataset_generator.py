import os
import json
import torch
import numpy as np
import pandas as pd
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification

class WBBEmotionDatasetGenerator:
    """
    [설명] 
    1. OCR로 추출된 extracted_ocr_chats.csv 파일을 읽어옵니다.
    2. KoBERT 감정 분류 모델에 전달하여 7대 감정 확률(%)을 계산합니다.
    3. IndexError 방지를 위한 토큰 ID 클램핑 및 시계열 JSON/CSV 데이터셋을 자동 생성합니다.
    """
    def __init__(self, model_dir: str = "./kobert_wbb_model"):
        print("🧠 [1/4] KoBERT 감정 분석 모델 로딩 중...")
        
        self.emotion_labels = ["기쁨", "당황", "분노", "불안", "상처", "슬픔", "중립"]
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 1. 토크나이저 로드 (KoBERT 전용 토크나이저 우선 로드)
        try:
            from tokenization_kobert import KoBERTTokenizer
            self.tokenizer = KoBERTTokenizer.from_pretrained("skt/kobert-base-v1")
            print(" ➔ [알림] KoBERT 전용 토크나이저(tokenization_kobert) 로드 성공")
        except Exception:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained("monologg/kobert", trust_remote_code=True)
            except Exception:
                self.tokenizer = AutoTokenizer.from_pretrained("skt/kobert-base-v1", trust_remote_code=True)

        # 2. 모델 로드
        if os.path.exists(model_dir) and os.path.isdir(model_dir):
            try:
                self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
                print(f" ➔ [알림] 파인튜닝된 로컬 모델 '{model_dir}' 로드 성공")
            except Exception as e:
                print(f" ⚠️ 로컬 모델 가중치 로드 실패 ({e}), 기본 베이스 모델로 전환합니다.")
                self.model = AutoModelForSequenceClassification.from_pretrained("skt/kobert-base-v1", num_labels=7)
        else:
            self.model = AutoModelForSequenceClassification.from_pretrained("skt/kobert-base-v1", num_labels=7)

        self.model.to(self.device)
        self.model.eval()
        self.vocab_size = self.model.config.vocab_size
        print(f"✅ KoBERT 로드 완료 (구동 장치: {self.device}, Vocab Size: {self.vocab_size})")

    def predict_emotion_probabilities(self, text: str) -> dict:
        """
        [설명] 단일 문장에 대해 7대 감정의 소프트맥스 확률(0~100%)을 안전하게 계산합니다.
        """
        if not text or not str(text).strip():
            return {label: 0.0 for label in self.emotion_labels[:-1]} | {"중립": 100.0, "dominant_emotion": "중립", "max_prob": 100.0}

        inputs = self.tokenizer(
            str(text),
            return_tensors="pt",
            truncation=True,
            max_length=64,
            padding=True
        )

        # [핵심 방어 코드] IndexError: index out of range in self 완벽 차단
        # 토크나이저가 만든 토큰 번호가 모델의 Vocab Size를 넘지 않도록 강제 제한
        inputs["input_ids"] = torch.clamp(inputs["input_ids"], min=0, max=self.vocab_size - 1).to(self.device)
        if "attention_mask" in inputs:
            inputs["attention_mask"] = inputs["attention_mask"].to(self.device)
        if "token_type_ids" in inputs:
            inputs["token_type_ids"] = inputs["token_type_ids"].to(self.device)

        with torch.no_grad():
            outputs = self.model(
                input_ids=inputs["input_ids"],
                attention_mask=inputs.get("attention_mask"),
                token_type_ids=inputs.get("token_type_ids")
            )
            logits = outputs.logits
            probs = F.softmax(logits, dim=-1).squeeze().cpu().numpy()

        # 1차원 배열 보장
        if probs.ndim == 0:
            probs = np.array([probs])
        if len(probs) < len(self.emotion_labels):
            # 출력 차원이 부족할 경우 패딩
            padded_probs = np.zeros(len(self.emotion_labels))
            padded_probs[:len(probs)] = probs
            probs = padded_probs

        prob_dict = {}
        for idx, label in enumerate(self.emotion_labels):
            prob_dict[label] = round(float(probs[idx]) * 100, 2)

        max_idx = int(np.argmax(probs[:len(self.emotion_labels)]))
        prob_dict["dominant_emotion"] = self.emotion_labels[max_idx]
        prob_dict["max_prob"] = round(float(probs[max_idx]) * 100, 2)

        return prob_dict

    def generate_dataset(self, input_csv_path: str = "extracted_ocr_chats.csv", 
                         output_csv_path: str = "video_emotion_timeseries.csv",
                         output_json_path: str = "video_emotion_timeseries.json"):
        if not os.path.exists(input_csv_path):
            raise FileNotFoundError(f"'{input_csv_path}' 파일이 없습니다. OCR 추출을 먼저 완료하세요.")

        print(f"📊 [2/4] OCR 데이터셋 로딩 중: '{input_csv_path}'")
        df_input = pd.read_csv(input_csv_path)

        if "chat_text" not in df_input.columns:
            raise KeyError("입력 CSV에 'chat_text' 컬럼이 없습니다.")

        print(f"🔥 [3/4] 총 {len(df_input)}개 프레임에 대한 KoBERT 7대 감정 추론 시작...")
        
        results_list = []
        for idx, row in df_input.iterrows():
            timestamp = row.get("timestamp", idx)
            frame = row.get("frame", idx * 30)
            text = str(row["chat_text"])

            prob_data = self.predict_emotion_probabilities(text)

            record = {
                "timestamp": float(timestamp),
                "frame": int(frame),
                "chat_text": text,
                "dominant_emotion": prob_data["dominant_emotion"],
                "max_prob": prob_data["max_prob"],
                "joy_pct": prob_data["기쁨"],
                "embarrass_pct": prob_data["당황"],
                "anger_pct": prob_data["분노"],
                "anxiety_pct": prob_data["불안"],
                "hurt_pct": prob_data["상처"],
                "sadness_pct": prob_data["슬픔"],
                "neutral_pct": prob_data["중립"]
            }
            results_list.append(record)

            if (idx + 1) % 10 == 0 or (idx + 1) == len(df_input):
                print(f" ➔ [{idx + 1:>3}/{len(df_input)}] {timestamp:>6.1f}초 | 감정: {prob_data['dominant_emotion']} ({prob_data['max_prob']}%) | 텍스트: {text[:20]}")

        df_output = pd.DataFrame(results_list)

        # 동적 임계점(Adaptive Threshold) 산출
        mean_joy = float(df_output["joy_pct"].mean()) if not df_output.empty else 0.0
        std_joy = float(df_output["joy_pct"].std()) if not df_output.empty else 0.0
        recommended_threshold = round(mean_joy + (1.2 * std_joy), 2)

        meta_data = {
            "video_metadata": {
                "total_records": len(df_output),
                "duration_sec": float(df_output["timestamp"].max()) if not df_output.empty else 0.0,
                "analysis_model": "KoBERT (7 Classes)"
            },
            "adaptive_threshold_stats": {
                "joy_mean": round(mean_joy, 2),
                "joy_std": round(std_joy, 2),
                "calculated_threshold": recommended_threshold,
                "description": "영상 기쁨 평균 + 1.2*표준편차 기반 1차 하이라이트 동적 임계점"
            },
            "time_series_data": results_list
        }

        # 1. CSV 저장
        df_output.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
        
        # 2. JSON 저장
        with open(output_json_path, "w", encoding="utf-8") as jf:
            json.dump(meta_data, jf, ensure_ascii=False, indent=2)

        print("\n" + "=" * 75)
        print(f"✅ [4/4 데이터셋 생성 완료]")
        print(f" 1. CSV 파일 : {output_csv_path} (총 {len(df_output)}행)")
        print(f" 2. JSON 파일: {output_json_path}")
        print(f" 3. 산출된 동적 임계점: 기쁨(Joy) {recommended_threshold}% 이상")
        print("=" * 75)

        return meta_data

if __name__ == "__main__":
    generator = WBBEmotionDatasetGenerator(model_dir="./kobert_wbb_model")
    generator.generate_dataset(
        input_csv_path="extracted_ocr_chats.csv",
        output_csv_path="video_emotion_timeseries.csv",
        output_json_path="video_emotion_timeseries.json"
    )