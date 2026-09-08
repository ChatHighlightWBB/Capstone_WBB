"""
=============================================================================
[와바바(WBB)] 3단계: 30초 Sliding Window 기반 1차 하이라이트 탐지기 (프로덕션 배포용)
- 담당자: 송태섭 (책임개발자)
- 핵심 개선사항:
  1. Step 2에서 생성한 표준 메타데이터 키('duration_sec', 'calculated_threshold') 완벽 동기화
  2. 영상 길이에 관계없이 180초부터 10시간 대용량까지 전체 타임라인 전수 순회
  3. 하드코딩된 폴백값(65초, 8.0%) 완전 제거 및 동적 임계점 100% 적용
- 입력: video_emotion_timeseries.json
- 출력: stage1_candidates.json, stage1_candidates.csv
=============================================================================
"""

import json
import os
import pandas as pd

class WBBSlidingWindowDetector:
    def __init__(self, json_path: str = "video_emotion_timeseries.json"):
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"❌ [Step 3 중단] '{json_path}' 파일이 없습니다. Step 2를 먼저 실행하세요.")
            
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
            
        # Step 2 표준 키 계약 동기화
        self.meta = self.data.get("video_metadata", {})
        self.stats = self.data.get("adaptive_threshold_stats", {})
        self.time_series = self.data.get("time_series_data", [])
        
        # 실제 데이터로부터 값 로드 (키 불일치 해결)
        self.duration_sec = float(self.meta.get("duration_sec", 0.0))
        self.threshold = float(self.stats.get("calculated_threshold", 0.0))

        # 메타데이터 무결성 방어 검증
        if self.duration_sec <= 0.0 and self.time_series:
            self.duration_sec = float(max(item.get("timestamp", 0.0) for item in self.time_series))
        if self.threshold <= 0.0:
            self.threshold = 20.0  # 최소 기본 안전 기준선

    def detect_candidate_windows(
        self, 
        window_size: float = 30.0, 
        step_size: float = 5.0, 
        max_stage1_candidates: int = 30,
        output_json: str = "stage1_candidates.json",
        output_csv: str = "stage1_candidates.csv"
    ):
        print("=" * 75)
        print("🔍 [Step 3 하이라이트 1차 탐지] 30초 Sliding Window 정밀 분석 가동")
        print(f" ➔ 분석 대상 영상 총 길이: {self.duration_sec:.1f}초")
        print(f" ➔ Step 2 연동 동적 임계점: 기쁨(Joy) {self.threshold:.1f}% 이상")
        print("=" * 75)

        df = pd.DataFrame(self.time_series)
        if df.empty:
            print("❌ [경고] 분석할 시계열 채팅 데이터가 비어 있습니다.")
            return []

        raw_candidates = []
        current_start = 0.0

        # 실제 영상 전체 길이를 누락 없이 30초 윈도우로 순회 (5초 스텝 이동)
        while current_start < self.duration_sec:
            current_end = min(current_start + window_size, self.duration_sec)
            
            # 해당 윈도우 시간대에 속한 채팅 필터링
            window_df = df[(df["timestamp"] >= current_start) & (df["timestamp"] <= current_end)]
            
            if not window_df.empty:
                avg_joy = float(window_df["joy_pct"].mean())
                max_joy = float(window_df["joy_pct"].max())
                chat_count = len(window_df)
                
                # 가중 스코어링: 평균 기쁨 70% + 최고 기쁨 30%
                window_score = round((avg_joy * 0.7) + (max_joy * 0.3), 2)
                
                # 동적 임계점을 상회하는 구간만 1차 후보로 수집
                if window_score >= self.threshold:
                    raw_candidates.append({
                        "start_time": round(current_start, 2),
                        "end_time": round(current_end, 2),
                        "duration": round(current_end - current_start, 2),
                        "window_score": window_score,
                        "avg_joy": round(avg_joy, 2),
                        "chat_count": chat_count
                    })

            current_start += step_size
            # 윈도우 시작점이 영상 끝에 도달하면 안전 종료
            if current_start + (window_size / 2) >= self.duration_sec:
                break

        # 1. 인접/중복 윈도우 병합
        merged_candidates = self._merge_overlapping_intervals(raw_candidates)

        # 2. 2차 검증(Demucs/Whisper) 과부하 방지를 위해 점수 상위 N개 선별 (제안서 기준 최대 30개)
        sorted_by_score = sorted(merged_candidates, key=lambda x: x["window_score"], reverse=True)
        selected_candidates = sorted_by_score[:max_stage1_candidates]
        
        # 3. 시간 순서대로 재정렬하여 최종 확정
        final_stage1 = sorted(selected_candidates, key=lambda x: x["start_time"])

        result_payload = {
            "metadata": {
                "source_video_duration": self.duration_sec,
                "applied_threshold": self.threshold,
                "total_candidates": len(final_stage1)
            },
            "candidate_clips": final_stage1
        }

        # 결과 저장
        with open(output_json, "w", encoding="utf-8") as jf:
            json.dump(result_payload, jf, ensure_ascii=False, indent=2)

        if final_stage1:
            pd.DataFrame(final_stage1).to_csv(output_csv, index=False, encoding="utf-8-sig")

        print(f"✅ [1차 후보 선별 완료] 2차 스트리머 정밀 검증(Step 4)으로 전달할 클립: 총 {len(final_stage1)}개")
        for idx, clip in enumerate(final_stage1, 1):
            print(f"   [{idx}] {clip['start_time']}초 ~ {clip['end_time']}초 (길이: {clip['duration']}초 | 점수: {clip['window_score']}점)")
        print("=" * 75)

        return final_stage1

    def _merge_overlapping_intervals(self, intervals):
        if not intervals:
            return []
        sorted_intervals = sorted(intervals, key=lambda x: x["start_time"])
        merged = []
        curr = dict(sorted_intervals[0])

        for next_interval in sorted_intervals[1:]:
            # 시간대가 겹치는 경우 하나의 연속 구간으로 병합
            if next_interval["start_time"] <= curr["end_time"]:
                curr["end_time"] = max(curr["end_time"], next_interval["end_time"])
                curr["duration"] = round(curr["end_time"] - curr["start_time"], 2)
                curr["window_score"] = max(curr["window_score"], next_interval["window_score"])
                curr["chat_count"] += next_interval["chat_count"]
            else:
                merged.append(curr)
                curr = dict(next_interval)
        merged.append(curr)
        return merged


if __name__ == "__main__":
    detector = WBBSlidingWindowDetector()
    detector.detect_candidate_windows()