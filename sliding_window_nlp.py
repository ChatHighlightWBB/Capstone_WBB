import os
import re
from typing import Dict, List
import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class WBBWindowNLPAnalyzer:
  """[설명] 30초 Sliding Window 기반 채팅 감정 밀도 및 화력 집계 엔진.

  개별 채팅의 7대 감정 Softmax 확률값을 30초 단위 구간으로 통합 계산합니다.
  """

  def __init__(self, model_path: str = "./kobert_wbb_model"):
    print(
        "🚀 [와바바 NLP Engine] 30초 Sliding Window 집계 엔진을"
        " 초기화합니다..."
    )

    if not os.path.exists(model_path):
      raise FileNotFoundError(
          f"'{model_path}' 경로에 파인튜닝된 KoBERT 모델이 없습니다."
      )

    # 1. KoBERT 토크나이저 및 로컬 파인튜닝 가중치 로드
    self.tokenizer = AutoTokenizer.from_pretrained(
        "monologg/kobert", trust_remote_code=True
    )
    self.model = AutoModelForSequenceClassification.from_pretrained(
        model_path, num_labels=7
    )
    self.model.eval()  # 추론 모드 설정

    # 노션 공식 명세 기준 0~6번 감정 라벨
    self.labels = {
        0: "기쁨/행복/환호",
        1: "당황/놀람",
        2: "분노/짜증",
        3: "슬픔/좌절",
        4: "혐오/불쾌",
        5: "공포/불안",
        6: "중립/일상",
    }

    # 복합 감정 및 문맥 우선순위 가드레일 딕셔너리
    self.high_priority_rules = {
        5: ["무서", "소름", "살려", "조지기", "귀신", "깜짝", "쫄", "ㄷㄷ"],  # 공포
        2: ["빡치", "뇌절", "개못", "망했", "짜증", "열받"],  # 분노
        4: ["더럽", "찝찝", "토나", "극혐", "웩", "역겹"],  # 혐오
        3: ["슬프", "가슴 찢", "ㅠㅠ", "ㅜㅜ", "눈물", "힘들"],  # 슬픔
        1: ["헐", "엥", "어우 뭐야", "진짜냐", "???"],  # 당황
    }

  def analyze_single_chat(self, text: str) -> np.ndarray:
    """[설명] 단일 채팅 문장에 대해 가드레일이 적용된 7대 감정 Softmax 확률 배열(0.0~1.0)을 반환합니다."""
    chat_text = str(text).strip()
    if not chat_text:
      return np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])

    inputs = self.tokenizer(
        chat_text,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=64,
    )

    with torch.no_grad():
      outputs = self.model(**inputs)
      probs = torch.softmax(outputs.logits, dim=1).squeeze().tolist()
      pred_idx = int(np.argmax(probs))

    # 문장 부호 및 형태소 특성 분석
    clean_text = re.sub(r"[^\w\s]", "", chat_text).strip()
    only_punctuation = len(clean_text) == 0
    has_question = bool(re.search(r"\?+", chat_text))
    has_exclamation = bool(re.search(r"!+", chat_text))

    overridden = False

    # 1순위: 특수문자 단독 입력 (???, !!!)
    if only_punctuation:
      if has_question:
        probs = [0.05, 0.85, 0.02, 0.02, 0.02, 0.02, 0.02]
        overridden = True
      elif has_exclamation:
        probs = [0.85, 0.05, 0.02, 0.02, 0.02, 0.02, 0.02]
        overridden = True

    # 2순위: 실질 감정어 우선 검사 (ㅋㅋ 섞임 방어)
    if not overridden:
      for target_label, keywords in self.high_priority_rules.items():
        if any(kw in chat_text for kw in keywords):
          probs[target_label] = max(probs[target_label], 0.85)
          overridden = True
          break

    # 3순위: 질문형 맥락 감지
    if not overridden and has_question:
      if any(
          kw in chat_text
          for kw in ["오바", "진짜", "대박", "뭐하", "이게", "헐", "엥", "나가"]
      ):
        probs[1] = max(probs[1], 0.75)
        overridden = True

    # 4순위: 순수 감탄/웃음
    if not overridden and any(
        kw in chat_text for kw in ["ㅋㅋㅋㅋ", "ㅋㅋㅋ", "개웃기", "대박이네"]
    ):
      probs[0] = max(probs[0], 0.85)

    # 확률값 정규화 (합이 1이 되도록 조정)
    sum_prob = sum(probs)
    normalized_probs = [p / sum_prob for p in probs]
    return np.array(normalized_probs)

  def process_sliding_window(
      self,
      chat_logs: List[Dict],
      video_duration_sec: int,
      window_size: int = 30,
      step_size: int = 10,
  ) -> List[Dict]:
    """[핵심] 타임스탬프 채팅 로그 전체를 30초 Sliding Window 단위로 집계합니다.

    :param chat_logs: [{'timestamp': 초단위실수, 'message': '채팅문장'}, ...]
    :param video_duration_sec: 전체 영상 길이 (초)
    :param window_size: 윈도우 크기 (30초)
    :param step_size: 이동 간격 (10초)
    :return: 30초 구간별 감정 밀도 및 화력 지수 리스트
    """
    results = []

    # 10초 간격으로 이동하며 30초 구간 분석
    for start_time in range(
        0, video_duration_sec - window_size + 1, step_size
    ):
      end_time = start_time + window_size

      # 해당 30초 구간 내 채팅 추출
      window_chats = [
          c
          for c in chat_logs
          if start_time <= c.get("timestamp", 0) < end_time
      ]

      chat_count = len(window_chats)

      if chat_count == 0:
        aggregated_emotions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        top_emotion_idx = 6  # 중립
      else:
        # 30초 구간 내 모든 채팅의 감정 확률 행렬화
        prob_matrix = [
            self.analyze_single_chat(c["message"]) for c in window_chats
        ]

        # 30초 구간 감정 확률 벡터 평균 (Mean)
        mean_probs = np.mean(prob_matrix, axis=0)
        aggregated_emotions = [round(float(p), 4) for p in mean_probs]
        top_emotion_idx = int(np.argmax(mean_probs))

      # Late Fusion 결합용 긍정(0번) 및 부정(1~5번) 감정 밀도 산출
      positive_density = aggregated_emotions[0]
      negative_density = sum(aggregated_emotions[1:6])

      results.append({
          "time_range": f"{start_time}s - {end_time}s",
          "start_sec": start_time,
          "end_sec": end_time,
          "chat_count": chat_count,  # 30초간 채팅 화력
          "top_emotion_idx": top_emotion_idx,
          "top_emotion_name": self.labels[top_emotion_idx],
          "positive_density": round(positive_density, 4),
          "negative_density": round(negative_density, 4),
          "all_emotion_probs": aggregated_emotions,
      })

    return results


# 테스트 실행 루틴
if __name__ == "__main__":
  analyzer = WBBWindowNLPAnalyzer()

  # 타임스탬프가 포함된 샘플 채팅 로그
  sample_logs = [
      {"timestamp": 2.5, "message": "와 무서워 ㅋㅋ"},
      {"timestamp": 6.1, "message": "뒤에 귀신 나옴 ㄷㄷ"},
      {"timestamp": 11.4, "message": "소름 돋네 진짜"},
      {"timestamp": 18.0, "message": "살려줘 ㅋㅋㅋ"},
      {"timestamp": 25.2, "message": "ㅋㅋㅋㅋㅋ"},
      {"timestamp": 35.0, "message": "오늘 방송 몇시까지 함?"},
  ]

  # 60초 길이 기준 30초 Sliding Window 분석
  summary = analyzer.process_sliding_window(
      chat_logs=sample_logs, video_duration_sec=60
  )

  print("\n📊 [30초 Sliding Window 감정 밀도 분석 결과]")
  print("=" * 75)
  for w in summary:
    print(
        f"⏱️ 구간: {w['time_range']} | 채팅 화력: {w['chat_count']}개 | 대표 감정:"
        f" [{w['top_emotion_idx']}] {w['top_emotion_name']}"
    )
    print(
        f" ➔ 긍정 밀도: {w['positive_density']} | 부정 밀도:"
        f" {w['negative_density']}"
    )
    print(f" ➔ 전체 감정 확률: {w['all_emotion_probs']}\n")