import json
import os
import pandas as pd

class WBBSlidingWindowDetector:
    """
    [설명]
    1. video_emotion_timeseries.json 데이터를 로드합니다.
    2. 30초 단위 Sliding Window(5초 이동)로 감정 점수와 채팅 빈도를 분석합니다.
    3. 동적 임계점을 넘긴 구간 중 점수 상위 최대 20개(max_candidates)를 1차 후보로 확정합니다.
    """
    def __init__(self, json_path: str = "video_emotion_timeseries.json"):
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"'{json_path}' 파일이 없습니다.")
            
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
            
        self.meta = self.data.get("video_metadata", {})
        self.stats = self.data.get("adaptive_threshold_stats", {})
        self.time_series = self.data.get("time_series_data", [])
        
        self.threshold = float(self.stats.get("calculated_threshold", 8.0))
        self.duration_sec = float(self.meta.get("duration_sec", 65.0))

    def detect_candidate_windows(self, window_size: float = 30.0, step_size: float = 5.0, 
                                 max_stage1_candidates: int = 20,
                                 output_json: str = "stage1_candidates.json"):
        print("=" * 70)
        print(f"🔍 [1차 하이라이트 탐지] 30초 Sliding Window 분석 가동")
        print(f" ➔ 영상 총 길이: {self.duration_sec:.1f}초 | 적용 동적 임계점: {self.threshold}%")
        print("=" * 70)

        df = pd.DataFrame(self.time_series)
        if df.empty:
            print("❌ 분석할 시계열 데이터가 비어 있습니다.")
            return []

        raw_candidates = []
        current_start = 0.0

        # 30초 윈도우 순회 (5초 간격 이동)
        while current_start + window_size <= self.duration_sec + step_size:
            current_end = min(current_start + window_size, self.duration_sec)
            window_df = df[(df["timestamp"] >= current_start) & (df["timestamp"] <= current_end)]
            
            if not window_df.empty:
                avg_joy = float(window_df["joy_pct"].mean())
                max_joy = float(window_df["joy_pct"].max())
                chat_count = len(window_df)
                
                # 윈도우 스코어 = 평균 기쁨 70% + 순간 최고 기쁨 30%
                window_score = round((avg_joy * 0.7) + (max_joy * 0.3), 2)
                
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
            if current_start >= self.duration_sec:
                break

        # 1. 겹치는 윈도우 구간 병합
        merged_candidates = self._merge_overlapping_intervals(raw_candidates)

        # 2. 1차 후보 개수 제한 (2차 정밀 검증 부하 방지를 위해 상위 max_stage1_candidates개 선별)
        sorted_by_score = sorted(merged_candidates, key=lambda x: x["window_score"], reverse=True)
        selected_candidates = sorted_by_score[:max_stage1_candidates]
        
        # 3. 시간 순서대로 재정렬
        final_stage1 = sorted(selected_candidates, key=lambda x: x["start_time"])

        result_payload = {
            "metadata": {
                "source_video_duration": self.duration_sec,
                "applied_threshold": self.threshold,
                "total_candidates": len(final_stage1)
            },
            "candidate_clips": final_stage1
        }

        with open(output_json, "w", encoding="utf-8") as jf:
            json.dump(result_payload, jf, ensure_ascii=False, indent=2)

        pd.DataFrame(final_stage1).to_csv("stage1_candidates.csv", index=False, encoding="utf-8-sig")

        print(f"✅ [1차 후보 확정] 2차 정밀 검증으로 전달할 클립 수: {len(final_stage1)}개")
        return final_stage1

    def _merge_overlapping_intervals(self, intervals):
        if not intervals:
            return []
        sorted_intervals = sorted(intervals, key=lambda x: x["start_time"])
        merged = []
        curr = sorted_intervals[0]
        for next_interval in sorted_intervals[1:]:
            if next_interval["start_time"] <= curr["end_time"]:
                curr["end_time"] = max(curr["end_time"], next_interval["end_time"])
                curr["duration"] = round(curr["end_time"] - curr["start_time"], 2)
                curr["window_score"] = max(curr["window_score"], next_interval["window_score"])
                curr["chat_count"] += next_interval["chat_count"]
            else:
                merged.append(curr)
                curr = next_interval
        merged.append(curr)
        return merged

if __name__ == "__main__":
    detector = WBBSlidingWindowDetector()
    detector.detect_candidate_windows()