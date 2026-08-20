import os
import shutil
from typing import Dict, List
from ffmpeg_clipper import WBBFFmpegClipper
from multimodal_fusion import WBBMultimodalFusionEngine
from sliding_window_nlp import WBBWindowNLPAnalyzer
from stage2_refinement import WBBStage2RefinementEngine
from test_real_video import extract_real_audio_energy, extract_real_visual_changes


class WBBHighlightMasterPipeline:
  """[설명] 와바바(WBB) 전체 하이라이트 자동 생성 통합 마스터 파이프라인

  1차 멀티모달 Late Fusion -> FFmpeg 클리핑 -> 2차 Demucs/Whisper/KoBERT 정밀
  검증 -> FFmpeg 최종 병합
  """

  def __init__(self):
    print("🚀 [WBB Master Pipeline] 와바바 통합 하이라이트 엔진 가동...")
    self.nlp_engine = WBBWindowNLPAnalyzer()
    self.fusion_engine = WBBMultimodalFusionEngine()
    self.clipper = WBBFFmpegClipper(temp_dir="./temp_clips")
    self.stage2_engine = WBBStage2RefinementEngine()

  def run_full_pipeline(
      self,
      video_path: str,
      chat_logs: List[Dict],
      output_final_video: str = "./final_highlight.mp4",
  ) -> Dict:
    """[핵심] 원본 영상과 채팅 데이터를 입력받아 최종 하이라이트 영상을 생성합니다."""
    if not os.path.exists(video_path):
      raise FileNotFoundError(f"'{video_path}' 파일을 찾을 수 없습니다.")

    # 1. 영상 메타데이터 분석 및 1차 신호 추출 (비전/오디오)
    print("\n" + "=" * 80)
    print("🎬 [STEP 1] 1차 멀티모달 신호 추출 및 30초 Sliding Window 분석")
    print("=" * 80)

    # 넉넉하게 120초 영상 분량 기준 신호 분석
    video_duration = 120
    audio_energies = extract_real_audio_energy(video_path, video_duration)
    visual_changes = extract_real_visual_changes(video_path, video_duration)

    # 30초 단위 NLP 감정 밀도 계산
    nlp_windows = self.nlp_engine.process_sliding_window(
        chat_logs, video_duration
    )

    # Late Fusion 융합 점수 계산
    fusion_results = []
    for i, nlp_win in enumerate(nlp_windows):
      a_val = audio_energies[i] if i < len(audio_energies) else 0.1
      v_val = visual_changes[i] if i < len(visual_changes) else 0.1
      fusion_results.append(
          self.fusion_engine.calculate_window_fusion_score(
              nlp_win, a_val, v_val
          )
      )

    # 1차 후보군 추출 (동적 임계점 적용)
    stage1_summary = self.fusion_engine.extract_candidate_highlights(
        fusion_results
    )
    candidates = stage1_summary["candidates"]
    print(f"✅ 1차 후보 구간 탐색 완료: 총 {len(candidates)}개 구간 선정")

    if not candidates:
      print("⚠️ 하이라이트 기준치를 충족하는 후보 구간이 없습니다.")
      return {"status": "fail", "message": "No candidates found"}

    # 2. FFmpeg 무인코딩 고속 클리핑
    print("\n" + "=" * 80)
    print("✂️ [STEP 2] FFmpeg 무인코딩 스트림 복사(Stream Copy) 클리핑")
    print("=" * 80)

    clipped_paths = []
    for idx, cand in enumerate(candidates):
      clip_name = f"candidate_{idx+1}.mp4"
      clip_path = self.clipper.clip_candidate_segment(
          video_path=video_path,
          start_sec=cand["start_sec"],
          end_sec=cand["end_sec"],
          output_filename=clip_name,
          buffer_sec=2.0,  # 앞뒤 2초 버퍼
      )
      if clip_path:
        cand["clip_path"] = clip_path
        clipped_paths.append(clip_path)
        print(
            f" ➔ 클립 {idx+1} 생성: {clip_name} ({cand['start_sec']}s ~"
            f" {cand['end_sec']}s)"
        )

    # 3. 2단계 Demucs + Whisper + KoBERT 스트리머 발화 정밀 검증
    print("\n" + "=" * 80)
    print("🎙️ [STEP 3] 2차 스트리머 발화 정밀 검증 (Demucs + Whisper + KoBERT)")
    print("=" * 80)

    verified_clips = []
    for cand in candidates:
      clip_path = cand.get("clip_path")
      if not clip_path or not os.path.exists(clip_path):
        continue

      stage2_res = self.stage2_engine.analyze_streamer_speech(clip_path)
      cand["stage2_result"] = stage2_res

      print(
          f"🔍 [{os.path.basename(clip_path)}] 발화:"
          f" \"{stage2_res['speech_text'][:25]}...\" | 감정:"
          f" {stage2_res['streamer_emotion_name']}"
      )

      # 2차 검증 통과 여부 확인 (또는 1차 융합 점수가 압도적으로 높은 경우 포함)
      if stage2_res["is_verified"] or cand["fusion_score"] >= 0.6:
        verified_clips.append(clip_path)
        print(f" ➔ ✅ 최종 하이라이트 확정: {os.path.basename(clip_path)}")
      else:
        print(f" ➔ ❌ 2차 필터링 탈락: {os.path.basename(clip_path)}")

    # 만약 엄격한 검증으로 모두 탈락한 경우, 1차 최상위 1개 클립 구출
    if not verified_clips and clipped_paths:
      print("⚠️ 2차 검증 통과 클립이 없어 1차 최우수 클립을 선정합니다.")
      verified_clips.append(clipped_paths[0])

    # 4. FFmpeg 최종 하이라이트 영상 병합
    print("\n" + "=" * 80)
    print("🎬 [STEP 4] 최종 하이라이트 클립 자동 병합")
    print("=" * 80)

    final_output = self.clipper.merge_final_clips(
        clip_paths=verified_clips, output_final_path=output_final_video
    )

    print(f"\n🎉 [WBB 파이프라인 완결] 최종 요약 영상 생성 완료: {final_output}")

    return {
        "status": "success",
        "final_video_path": final_output,
        "total_windows_analyzed": stage1_summary["total_windows"],
        "stage1_candidates_count": len(candidates),
        "final_verified_clips_count": len(verified_clips),
        "highlight_timeline": candidates,
    }


# 단독 실행 테스트 루틴
if __name__ == "__main__":
  pipeline = WBBHighlightMasterPipeline()

  SAMPLE_VIDEO = "./test_sample.mp4"

  # 테스트용 타임스탬프 채팅 데이터
  sample_chats = [
      {"timestamp": 5.0, "message": "와 무서워 ㅋㅋ"},
      {"timestamp": 12.0, "message": "소름 돋네 ㄷㄷ"},
      {"timestamp": 35.0, "message": "ㅋㅋㅋㅋㅋ 개웃기네"},
      {"timestamp": 40.0, "message": "대박 사건 ㅋㅋㅋ"},
      {"timestamp": 75.0, "message": "와 샷 미쳤다 레전드"},
  ]

  # 전체 마스터 파이프라인 가동
  result = pipeline.run_full_pipeline(
      video_path=SAMPLE_VIDEO,
      chat_logs=sample_chats,
      output_final_video="./final_highlight.mp4",
  )