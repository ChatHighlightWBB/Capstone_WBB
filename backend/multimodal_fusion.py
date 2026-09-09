from typing import Dict, List
import numpy as np


class WBBMultimodalFusionEngine:
  """[설명] 와바바(WBB) 제안서 4.1 규격: 멀티모달 Late Fusion 1차 하이라이트 탐지 엔진.

  30초 Sliding Window 단위로 집계된 NLP 감정/화력 데이터, Librosa 오디오 에너지,
  OpenCV 화면 변화량을 결합하여 동적 임계점(Adaptive Threshold) 기반으로 후보
  클립을 추출합니다.
  """

  def __init__(
      self,
      weight_chat: float = 0.4,
      weight_audio: float = 0.3,
      weight_visual: float = 0.3,
  ):
    # 기본 가중치 설정 (텍스트 0.4, 오디오 0.3, 비주얼 0.3)
    self.w_chat_base = weight_chat
    self.w_audio_base = weight_audio
    self.w_visual_base = weight_visual

  def calculate_window_fusion_score(
      self, nlp_window: Dict, audio_energy: float, visual_change: float
  ) -> Dict:
    """[핵심] 30초 단위 1개 윈도우에 대해 멀티모달 가중치 점수를 계산합니다.

    :param nlp_window: sliding_window_nlp.py에서 산출된 30초 단위 딕셔너리
    :param audio_energy: Librosa RMS 오디오 에너지 수치 (0.0 ~ 1.0)
    :param visual_change: OpenCV 프레임 간 픽셀 변화량 수치 (0.0 ~ 1.0)
    :return: 가중 결합 점수 및 저에너지 고감정 플래그가 포함된 딕셔너리
    """
    chat_count = nlp_window.get("chat_count", 0)
    pos_density = nlp_window.get("positive_density", 0.0)
    neg_density = nlp_window.get("negative_density", 0.0)

    # 1. 텍스트 감정 화력 점수 산출
    # 감정 강도 (긍정 밀도 + 부정 밀도)
    emotion_intensity = pos_density + neg_density
    # 채팅 빈도를 log1p 스케일로 정규화 (최대 20개 기준 정규화)
    chat_freq_norm = min(1.0, np.log1p(chat_count) / np.log1p(20))
    chat_score = chat_freq_norm * emotion_intensity

    # 2. 오디오 및 비주얼 정규화 (0.0 ~ 1.0 클리핑)
    audio_score = float(np.clip(audio_energy, 0.0, 1.0))
    visual_score = float(np.clip(visual_change, 0.0, 1.0))

    # 3. [핵심] 저에너지 고감정 (Low Energy, High Emotion) 동적 가중치 보정
    # 스트리머 오디오가 조용(0.3 미만)하지만 채팅 감정 화력이 높은(0.5 초과) 경우
    is_low_energy_high_emotion = audio_score < 0.3 and chat_score > 0.5

    if is_low_energy_high_emotion:
      # 채팅 가중치를 0.6으로 대폭 상향, 오디오 가중치 0.1로 하향
      w_c, w_a, w_v = 0.6, 0.1, 0.3
    else:
      w_c, w_a, w_v = (
          self.w_chat_base,
          self.w_audio_base,
          self.w_visual_base,
      )

    # 4. 멀티모달 최종 융합 점수 계산 (Late Fusion 공식)
    fusion_score = (
        (w_c * chat_score) + (w_a * audio_score) + (w_v * visual_score)
    )

    return {
        "time_range": nlp_window.get("time_range"),
        "start_sec": nlp_window.get("start_sec"),
        "end_sec": nlp_window.get("end_sec"),
        "fusion_score": round(float(fusion_score), 4),
        "chat_score": round(float(chat_score), 4),
        "audio_score": round(audio_score, 4),
        "visual_score": round(visual_score, 4),
        "top_emotion_name": nlp_window.get("top_emotion_name"),
        "is_low_energy_high_emotion": is_low_energy_high_emotion,
        "chat_count": chat_count,
    }

  def extract_candidate_highlights(
      self,
      window_results: List[Dict],
      sensitivity_multiplier: float = 1.0,
  ) -> Dict:
    """[핵심] 영상 전체 평균 기반 적응형 동적 임계점(Adaptive Threshold)을 적용하여 1차 하이라이트 후보 구간을

    추출합니다.
    """
    if not window_results:
      return {"threshold": 0.0, "candidates": []}

    scores = [w["fusion_score"] for w in window_results]

    # 동적 임계점 계산 공식: 평균(Mean) + (감도 계수 * 표준편차(Std))
    mean_score = float(np.mean(scores))
    std_score = float(np.std(scores))
    adaptive_threshold = mean_score + (sensitivity_multiplier * std_score * 0.5)

    # 임계점을 넘긴 구간 또는 저에너지 고감정 구간을 1차 후보군으로 선정
    candidate_clips = []
    for w in window_results:
      if (
          w["fusion_score"] >= adaptive_threshold
          or w["is_low_energy_high_emotion"]
      ):
        w["is_candidate"] = True
        candidate_clips.append(w)
      else:
        w["is_candidate"] = False

    return {
        "mean_score": round(mean_score, 4),
        "std_score": round(std_score, 4),
        "adaptive_threshold": round(adaptive_threshold, 4),
        "total_windows": len(window_results),
        "candidate_count": len(candidate_clips),
        "candidates": candidate_clips,
    }


# 단체 테스트 실행 루틴
if __name__ == "__main__":
  from sliding_window_nlp import WBBWindowNLPAnalyzer

  # 1. NLP 분석 엔진 실행 및 30초 집계 데이터 생성
  nlp_analyzer = WBBWindowNLPAnalyzer()

  sample_chat_logs = [
      {"timestamp": 2.5, "message": "와 무서워 ㅋㅋ"},
      {"timestamp": 6.1, "message": "뒤에 귀신 나옴 ㄷㄷ"},
      {"timestamp": 11.4, "message": "소름 돋네 진짜"},
      {"timestamp": 18.0, "message": "살려줘 ㅋㅋㅋ"},
      {"timestamp": 25.2, "message": "ㅋㅋㅋㅋㅋ"},
      {"timestamp": 35.0, "message": "오늘 방송 몇시까지 함?"},
      {"timestamp": 75.0, "message": "와 레전드 샷 미쳤다"},
      {"timestamp": 78.2, "message": "ㅋㅋㅋㅋㅋㅋ 대박"},
  ]

  # 100초 길이 영상 대상 30초 Sliding Window NLP 분석
  nlp_windows = nlp_analyzer.process_sliding_window(
      chat_logs=sample_chat_logs, video_duration_sec=100
  )

  # 2. 가상의 Librosa 오디오 에너지 및 OpenCV 픽셀 변화량 데이터 (구간별 매핑)
  # [0s~30s]: 공포 게임 잠입 구간 (오디오 조용함 0.15, 화면 변화 0.40) -> '저에너지 고감정' 케이스
  # [70s~100s]: 한타 교전 구간 (오디오 큼 0.85, 화면 변화 0.90) -> 일반 고화력 하이라이트
  mock_audio_energies = [0.15, 0.20, 0.10, 0.05, 0.05, 0.70, 0.85, 0.60]
  mock_visual_changes = [0.40, 0.35, 0.20, 0.10, 0.10, 0.80, 0.90, 0.75]

  fusion_engine = WBBMultimodalFusionEngine()
  window_fusion_results = []

  for i, nlp_win in enumerate(nlp_windows):
    audio_val = (
        mock_audio_energies[i] if i < len(mock_audio_energies) else 0.1
    )
    visual_val = (
        mock_visual_changes[i] if i < len(mock_visual_changes) else 0.1
    )
    result = fusion_engine.calculate_window_fusion_score(
        nlp_win, audio_val, visual_val
    )
    window_fusion_results.append(result)

  # 3. 적응형 임계점 기반 1차 하이라이트 후보 추출
  final_summary = fusion_engine.extract_candidate_highlights(
      window_fusion_results
  )

  print("\n🎯 [멀티모달 Late Fusion 1차 하이라이트 후보 추출 결과]")
  print("=" * 80)
  print(
      f"📊 전체 윈도우 수: {final_summary['total_windows']}개 | 산출된 동적 임계점:"
      f" {final_summary['adaptive_threshold']}"
  )
  print(f"🌟 1차 선정된 후보 클립 수: {final_summary['candidate_count']}개\n")

  for cand in final_summary["candidates"]:
    low_energy_tag = (
        " [🚨 저에너지 고감정 감지!]"
        if cand["is_low_energy_high_emotion"]
        else ""
    )
    print(
        f"⏱️ 구간: {cand['time_range']} | 융합 점수: {cand['fusion_score']} |"
        f" 대표 감정: {cand['top_emotion_name']}{low_energy_tag}"
    )
    print(
        f"   └ [세부 점수] 채팅: {cand['chat_score']} | 오디오: {cand['audio_score']} |"
        f" 비주얼: {cand['visual_score']}\n"
    )