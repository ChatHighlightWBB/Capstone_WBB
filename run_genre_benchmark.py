"""
=============================================================================
[와바바(WBB)] 장르별 영상 3종 적응형 동적 임계점 벤치마크 테스트 (최종 수정본)
- 담당자: 송태섭 (책임개발자)
- 목적: 토크, 공포, 게임 영상별 동적 임계점(Adaptive Threshold) 산출 실증
=============================================================================
"""

import os
import json
from highlight_pipeline import WBBAutoHighlightPipeline

# 3종 장르 영상별 파일 경로 및 채팅창 크롭 영역 (ymin, xmin, ymax, xmax 비율 0.0~1.0)
BENCHMARK_VIDEOS = [
    {
        "genre": "게임 (FPS/MOBA)",
        "file_path": "test_sample_game.mp4",
        "crop_box": (0.45, 0.50, 0.75, 0.75),  # 롤 영상: 캠 위쪽 채팅창 영역
        "prefix": "game",
        "desc": "롤 교전 및 고텐션"
    },
    {
        "genre": "공포 게임",
        "file_path": "test_sample_horror.mp4",
        "crop_box": (0.20, 0.65, 0.85, 0.98),  # 우측 세로형 채팅창 영역
        "prefix": "horror",
        "desc": "저에너지 정적 구간 + 비명 피크"
    },
    {
        "genre": "토크 / 소통",
        "file_path": "test_sample_talk.mp4",
        "crop_box": (0.15, 0.02, 0.85, 0.35),  # 좌측 세로형 채팅창 영역
        "prefix": "talk",
        "desc": "잔잔한 일상 대화 및 웃음"
    }
]

def run_benchmark():
    benchmark_results = []

    print("\n" + "=" * 80)
    print("🚀 [와바바] 3종 장르 영상 적응형 동적 임계점 벤치마크 테스트 가동")
    print("=" * 80)

    # 파이프라인 엔진 1회 초기화 (메모리 절약)
    pipeline = WBBAutoHighlightPipeline(model_dir="./kobert_wbb_model")

    for idx, item in enumerate(BENCHMARK_VIDEOS, 1):
        video_path = item["file_path"]
        genre = item["genre"]
        crop_box = item["crop_box"]
        prefix = item["prefix"]

        if not os.path.exists(video_path):
            print(f"\n❌ [{idx}/3] {genre} 영상 파일({video_path})을 찾을 수 없습니다. 건너뜁니다.")
            continue

        print(f"\n" + "#" * 80)
        print(f">>> [{idx}/3] {genre} 방송 분석 시작: {video_path}")
        print("#" * 80)

        # [핵심] 실제 파일 경로와 크롭 영역을 명시적으로 전달
        result = pipeline.run_full_pipeline(
            video_path=video_path,
            crop_box=crop_box,
            output_prefix=prefix
        )

        step2_json = result["emotion_timeseries_json"]
        step3_json = f"{prefix}_stage1_candidates.json"

        duration = 0.0
        mean_joy = 0.0
        threshold_val = 0.0
        chat_count = 0
        candidates_count = 0

        if os.path.exists(step2_json):
            with open(step2_json, "r", encoding="utf-8") as f:
                s2_data = json.load(f)
                meta = s2_data.get("video_metadata", {})
                stats = s2_data.get("adaptive_threshold_stats", {})
                duration = meta.get("duration_sec", 0.0)
                chat_count = meta.get("total_chats_analyzed", 0)
                mean_joy = stats.get("mean_joy", 0.0)
                threshold_val = stats.get("calculated_threshold", 0.0)

        if os.path.exists(step3_json):
            with open(step3_json, "r", encoding="utf-8") as f:
                s3_data = json.load(f)
                candidates_count = len(s3_data.get("candidate_clips", []))

        benchmark_results.append({
            "genre": genre,
            "duration": duration,
            "chat_count": chat_count,
            "mean_joy": mean_joy,
            "threshold": threshold_val,
            "candidates": candidates_count
        })

    # 최종 결과 요약 표 출력 (보고서 및 교수님 미팅 증빙용)
    print("\n" + "=" * 85)
    print("📊 [최종 검증 완료] 장르별 적응형 동적 임계점(Adaptive Threshold) 비교 표")
    print("=" * 85)
    print(f"{'장르':<15} | {'영상 길이':<9} | {'추출 채팅':<8} | {'평균 기쁨':<9} | {'산출 임계점':<11} | {'1차 후보 수'}")
    print("-" * 85)
    for res in benchmark_results:
        print(f"{res['genre']:<15} | {res['duration']:<7.1f}초 | {res['chat_count']:<6}건 | {res['mean_joy']:<7.1f}% | {res['threshold']:<9.1f}% | {res['candidates']}개")
    print("=" * 85)
    print("💡 분석 포인트: 각 장르의 분위기(텐션)에 따라 평균 기쁨과 임계점이 상이하게 산출되었는지 확인하세요.\n")

if __name__ == "__main__":
    run_benchmark()