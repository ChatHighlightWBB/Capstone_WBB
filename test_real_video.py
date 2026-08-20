import os
from typing import Dict, List
import cv2
import librosa
import numpy as np
from multimodal_fusion import WBBMultimodalFusionEngine
from sliding_window_nlp import WBBWindowNLPAnalyzer


def extract_real_audio_energy(video_path: str, duration_sec: int) -> List[float]:
  """[설명] Librosa를 사용하여 실제 영상 파일에서 30초 윈도우 단위 오디오 RMS 에너지를 추출합니다."""
  print("🔊 [오디오 분석] Librosa로 실제 음성 파형(RMS) 분석 중...")
  # 음성 파형 로드 (22050Hz)
  y, sr = librosa.load(video_path, sr=22050, duration=duration_sec)

  # 30초 윈도우 / 10초 스텝으로 평균 RMS 에너지 계산
  audio_energies = []
  window_samples = 30 * sr
  step_samples = 10 * sr

  for start in range(0, len(y) - window_samples + 1, step_samples):
    chunk = y[start : start + window_samples]
    rms = np.sqrt(np.mean(chunk**2))  # RMS 에너지 계산
    audio_energies.append(float(rms))

  # 0.0 ~ 1.0 범위로 정규화 (Min-Max)
  if audio_energies and max(audio_energies) > 0:
    max_val = max(audio_energies)
    audio_energies = [round(v / max_val, 4) for v in audio_energies]

  return audio_energies


def extract_real_visual_changes(
    video_path: str, duration_sec: int
) -> List[float]:
  """[설명] OpenCV를 사용하여 실제 영상 프레임 간 픽셀 변화량을 추출합니다."""
  print("🎥 [비전 분석] OpenCV로 실제 영상 프레임 간 픽셀 변화량 분석 중...")
  cap = cv2.VideoCapture(video_path)
  fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

  frame_diffs = []
  ret, prev_frame = cap.read()
  if not ret:
    cap.release()
    return []

  prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

  frame_idx = 0
  max_frames = int(fps * duration_sec)

  # 1초에 2프레임씩 샘플링하여 연산 속도 최적화
  sample_interval = int(fps / 2) if fps >= 2 else 1

  while cap.isOpened() and frame_idx < max_frames:
    ret, frame = cap.read()
    if not ret:
      break

    if frame_idx % sample_interval == 0:
      gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
      diff = cv2.absdiff(prev_gray, gray)  # 프레임 간 픽셀 차이 절대값
      mean_diff = np.mean(diff)
      frame_diffs.append(mean_diff)
      prev_gray = gray

    frame_idx += 1

  cap.release()

  # 30초 윈도우 / 10초 스텝으로 화면 변화량 묶기
  visual_changes = []
  samples_per_window = 30 * 2  # 1초당 2샘플
  samples_per_step = 10 * 2

  for start in range(
      0, len(frame_diffs) - samples_per_window + 1, samples_per_step
  ):
    chunk = frame_diffs[start : start + samples_per_window]
    visual_changes.append(float(np.mean(chunk)))

  # 0.0 ~ 1.0 정규화
  if visual_changes and max(visual_changes) > 0:
    max_v = max(visual_changes)
    visual_changes = [round(v / max_v, 4) for v in visual_changes]

  return visual_changes


# [실제 영상 + 실제 KoBERT 융합 실행]
if __name__ == "__main__":
  # 테스트할 실제 영상 파일 경로 (본인이 가진 mp4 파일 이름으로 변경)
  TEST_VIDEO_PATH = "./test_sample.mp4"

  if not os.path.exists(TEST_VIDEO_PATH):
    print(f"⚠️ '{TEST_VIDEO_PATH}' 파일이 없습니다.")
    print("현재 프로젝트 폴더에 테스트용 .mp4 영상을 넣고 파일명을 맞춰주세요.")
  else:
    VIDEO_DURATION = 60  # 분석할 영상 길이 (초)

    # 1. 실제 영상에서 음성/비주얼 추출
    real_audio = extract_real_audio_energy(TEST_VIDEO_PATH, VIDEO_DURATION)
    real_visual = extract_real_visual_changes(TEST_VIDEO_PATH, VIDEO_DURATION)

    # 2. 실제 KoBERT 모델로 채팅 감정 분석
    nlp_analyzer = WBBWindowNLPAnalyzer()
    sample_chats = [
        {"timestamp": 5.0, "message": "와 무서워 ㅋㅋ"},
        {"timestamp": 12.0, "message": "소름 돋네 ㄷㄷ"},
        {"timestamp": 35.0, "message": "ㅋㅋㅋㅋㅋ 개웃기네"},
    ]
    nlp_windows = nlp_analyzer.process_sliding_window(
        sample_chats, VIDEO_DURATION
    )

    # 3. 멀티모달 Late Fusion
    fusion_engine = WBBMultimodalFusionEngine()
    results = []
    for i, nlp_win in enumerate(nlp_windows):
      a_val = real_audio[i] if i < len(real_audio) else 0.1
      v_val = real_visual[i] if i < len(real_visual) else 0.1
      results.append(
          fusion_engine.calculate_window_fusion_score(nlp_win, a_val, v_val)
      )

    summary = fusion_engine.extract_candidate_highlights(results)

    print("\n🎯 [실제 영상 기반 멀티모달 하이라이트 판독 결과]")
    print(f"선정된 후보 구간 수: {summary['candidate_count']}개")
    for c in summary["candidates"]:
      print(
          f"⏱️ {c['time_range']} | 점수: {c['fusion_score']} | 대표 감정:"
          f" {c['top_emotion_name']}"
      )