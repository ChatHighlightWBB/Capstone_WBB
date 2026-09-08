"""
=============================================================================
[와바바(WBB)] 2단계: KoBERT 채팅 감정 분석 및 시계열 데이터 생성기 (프로덕션 배포용)
- 담당자: 송태섭 (책임개발자)
- 핵심 개선사항:
  1. 실제 비디오 파일(MP4)로부터 정확한 재생 시간(duration_sec)을 OpenCV로 자동 추출
  2. 3단계 슬라이딩 윈도우 및 프론트엔드 연동 규격(JSON Schema) 완벽 일치
  3. 테스트용 하드코딩 더미 데이터 완전 제거 및 무결성 예외 처리
- 입력: extracted_ocr_chats.csv, 실제 영상 파일(선택/자동 탐색)
- 출력: video_emotion_timeseries.csv, video_emotion_timeseries.json
=============================================================================
"""

import os
import re
import json
import torch
import cv2
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

    # 비아냥/조소 대응: 부정 단어와 웃음 자음 결합 시 분노/당황 가중치 상향
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

    def _get_actual_video_duration(self, video_path: str) -> float:
        """OpenCV를 사용하여 실제 영상의 정확한 재생 길이(초)를 측정합니다."""
        if video_path and os.path.exists(video_path):
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                cap.release()
                if fps > 0:
                    return round(float(frame_count / fps), 2)
        return 0.0

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
        output_json_path: str = "video_emotion_timeseries.json",
        video_path: str = None
    ):
        if not os.path.exists(input_csv_path):
            raise FileNotFoundError(f"❌ [Step 2 중단] 1단계 추출 파일 '{input_csv_path}'이 존재하지 않습니다.")

        df_input = pd.read_csv(input_csv_path)
        if df_input.empty:
            print(f"⚠️ 경고: '{input_csv_path}'에 추출된 채팅 데이터가 0건입니다.")

        text_col = "chat_text" if "chat_text" in df_input.columns else df_input.columns[-1]
        time_col = "timestamp" if "timestamp" in df_input.columns else df_input.columns[0]

        results_list = []
        joy_scores = []
        max_chat_time = 0.0

        for _, row in df_input.iterrows():
            try:
                t_val = float(row[time_col])
            except (ValueError, TypeError):
                t_val = 0.0
            
            msg = str(row[text_col])
            max_chat_time = max(max_chat_time, t_val)
            
            top_emo, probs = self.predict_emotion(msg)
            joy_pct = float(probs[0] * 100.0)
            joy_scores.append(joy_pct)

            record = {
                "timestamp": round(t_val, 2),
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
        
        # 실제 영상 길이 확정: 입력 비디오가 있으면 비디오 길이, 없으면 마지막 채팅 타임스탬프 기준
        real_duration = self._get_actual_video_duration(video_path)
        if real_duration == 0.0:
            real_duration = round(max_chat_time, 2) if max_chat_time > 0 else 60.0

        # 동적 임계점 계산 (평균 + 0.5 * 표준편차)
        mean_joy = float(np.mean(joy_scores)) if joy_scores else 20.0
        std_joy = float(np.std(joy_scores)) if joy_scores else 5.0
        calculated_threshold = round(float(mean_joy + 0.5 * std_joy), 2)

        # [핵심] 3단계 및 프론트엔드 연동 규격에 정확히 맞춘 표준 메타데이터 페이로드
        meta_data = {
            "video_metadata": {
                "duration_sec": real_duration,
                "total_chats_analyzed": len(df_output),
                "source_video_path": video_path if video_path else "unknown"
            },
            "adaptive_threshold_stats": {
                "calculated_threshold": calculated_threshold,
                "mean_joy": round(mean_joy, 2),
                "std_joy": round(std_joy, 2)
            },
            "time_series_data": results_list
        }

        # CSV 및 JSON 저장
        df_output.to_csv(output_csv_path, index=False, encoding="utf-8-sig")
        with open(output_json_path, "w", encoding="utf-8") as jf:
            json.dump(meta_data, jf, ensure_ascii=False, indent=2)

        print("\n" + "=" * 75)
        print("[Step 2 감정 분석 및 시계열 생성 완료 (실제 데이터 반영)]")
        print(f"1. 실제 영상 총 길이 : {real_duration:.1f}초")
        print(f"2. 분석된 채팅 건수  : {len(df_output)}건")
        print(f"3. 산출된 동적 임계점: 기쁨(Joy) {calculated_threshold:.1f}% 이상 (평균: {mean_joy:.1f}%, 편차: {std_joy:.1f})")
        print(f"4. 저장된 메타 파일  : {output_json_path}")
        print("=" * 75)

        return meta_data


if __name__ == "__main__":
    generator = WBBEmotionDatasetGenerator(model_dir="./kobert_wbb_model")
    # 로컬 파이프라인 단독 테스트 시 대상 영상 전달
    generator.generate_dataset(video_path="test_sample_game.mp4")