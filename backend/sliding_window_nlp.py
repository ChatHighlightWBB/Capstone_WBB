import json
import math
import os
import pandas as pd

# ==============================================================================
# [채팅+음성 융합] 1차 후보 점수 설정
# 채팅 감정 점수와 스트리머 목소리 크기(1초 dB)를 각각 영상 안 순위 비율(0~1)로
# 바꾼 뒤 가중합합니다. 단위가 다른 두 값을 순위로 맞춰서 섞기 위함입니다.
# ==============================================================================
FUSION_W_CHAT = 0.7   # 융합 점수에서 채팅 순위 비중
FUSION_W_AUDIO = 0.3  # 융합 점수에서 소리 순위 비중
FUSION_K_STD = 0.5    # 융합 임계점 = 융합 점수 평균 + FUSION_K_STD * 표준편차(모집단)

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

        # ------------------------------------------------------------------
        # [버그 수정] 예전 JSON은 'recommended_joy_threshold'만 담고 있어서
        # adaptive_threshold_stats 를 못 찾고 폴백값 8.0으로 동작했습니다.
        # 두 키 이름을 모두 허용하도록 하위 호환 처리합니다.
        # ------------------------------------------------------------------
        threshold = self.stats.get("calculated_threshold")
        if threshold is None:
            threshold = self.data.get("recommended_joy_threshold")
        if threshold is None:
            print("⚠️ 임계점 정보를 찾지 못해 기본값 8.0을 사용합니다.")
            threshold = 8.0
        self.threshold = float(threshold)

        # 영상 길이도 마찬가지. 없으면 마지막 채팅 시각으로 추정합니다.
        duration = self.meta.get("duration_sec")
        if duration is None and self.time_series:
            duration = max(float(r.get("timestamp", 0)) for r in self.time_series) + 30.0
            print(f"⚠️ 영상 길이 정보가 없어 채팅 기준으로 추정합니다: {duration:.1f}초")
        self.duration_sec = float(duration if duration else 65.0)

    def detect_candidate_windows(self, window_size: float = 30.0, step_size: float = 5.0, 
                                 max_stage1_candidates: int = 20,
                                 output_json: str = "stage1_candidates.json",
                                 audio_db_per_sec=None):
        # audio_db_per_sec: 1초마다의 목소리 대역 음량(dB) 리스트 (audio_energy.py).
        #   None 이면 예전과 똑같이 채팅 감정 점수만으로 후보를 고릅니다.
        #   값이 있으면 채팅+음성 융합 점수로 후보를 고릅니다.
        use_fusion = audio_db_per_sec is not None
        print("=" * 70)
        print(f"🔍 [1차 하이라이트 탐지] 30초 Sliding Window 분석 가동")
        print(f" ➔ {'1차 후보: 채팅+음성 융합' if use_fusion else '1차 후보: 채팅 단독'}")
        print(f" ➔ 영상 총 길이: {self.duration_sec:.1f}초 | 적용 동적 임계점: {self.threshold}%")
        print("=" * 70)

        df = pd.DataFrame(self.time_series)
        if df.empty:
            print("❌ 분석할 시계열 데이터가 비어 있습니다.")
            return []

        applied_threshold = self.threshold
        if use_fusion:
            raw_candidates, applied_threshold = self._fusion_raw_candidates(
                df, audio_db_per_sec, window_size, step_size)
        else:
            raw_candidates = self._chat_raw_candidates(df, window_size, step_size)

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
                "applied_threshold": applied_threshold,
                "total_candidates": len(final_stage1)
            },
            "candidate_clips": final_stage1
        }

        with open(output_json, "w", encoding="utf-8") as jf:
            json.dump(result_payload, jf, ensure_ascii=False, indent=2)

        pd.DataFrame(final_stage1).to_csv("stage1_candidates.csv", index=False, encoding="utf-8-sig")

        print(f"✅ [1차 후보 확정] 2차 정밀 검증으로 전달할 클립 수: {len(final_stage1)}개")
        return final_stage1

    def _chat_raw_candidates(self, df, window_size, step_size):
        """[채팅 단독] 예전 방식 그대로: 채팅 감정 점수가 self.threshold 이상인 창을 모읍니다."""
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

        return raw_candidates

    def _fusion_raw_candidates(self, df, audio_db_per_sec, window_size, step_size):
        """
        [채팅+음성 융합] 모든 창(채팅 없는 창 포함)의 채팅 점수·소리 점수를 구해
        각각 순위 비율로 바꾼 뒤 융합하고, 융합 임계점 이상인 창을 모읍니다.
        반환: (임계점 넘은 창 목록, 결과 metadata 에 넣을 임계점(0~100 단위))
        """
        windows = []
        current_start = 0.0

        # 창 순회·채팅 포함 조건은 채팅 단독 방식과 같습니다.
        while current_start + window_size <= self.duration_sec + step_size:
            current_end = min(current_start + window_size, self.duration_sec)
            window_df = df[(df["timestamp"] >= current_start) & (df["timestamp"] <= current_end)]

            if not window_df.empty:
                avg_joy = float(window_df["joy_pct"].mean())
                max_joy = float(window_df["joy_pct"].max())
                chat_score = (avg_joy * 0.7) + (max_joy * 0.3)
            else:
                avg_joy = 0.0
                chat_score = 0.0  # 채팅 없는 창도 점수 0으로 순위 계산에 포함

            # 소리 점수: i번째 1초 값은 [i, i+1)초 → 창 [start, end) 안의 1초 dB 평균
            vals = audio_db_per_sec[int(math.floor(current_start)):int(math.ceil(current_end))]
            audio_score = (sum(vals) / len(vals)) if vals else float(min(audio_db_per_sec))

            windows.append({
                "start": current_start, "end": current_end,
                "avg_joy": avg_joy, "chat_count": len(window_df),
                "chat_score": chat_score, "audio_score": audio_score,
            })

            current_start += step_size
            if current_start >= self.duration_sec:
                break

        # 순위 비율(0~1, 가장 큰 값 1, 같은 값은 평균 순위)
        n = len(windows)
        chat_rank = pd.Series([w["chat_score"] for w in windows], dtype=float).rank(method="average") / n
        audio_rank = pd.Series([w["audio_score"] for w in windows], dtype=float).rank(method="average") / n
        fusion = FUSION_W_CHAT * chat_rank + FUSION_W_AUDIO * audio_rank

        # 융합 임계점 = 평균 + K * 표준편차(모집단). self.threshold 는 건드리지 않습니다.
        fusion_threshold = float(fusion.mean() + FUSION_K_STD * fusion.std(ddof=0))

        raw_candidates = []
        for w, f, ar in zip(windows, fusion.tolist(), audio_rank.tolist()):
            if f >= fusion_threshold:
                raw_candidates.append({
                    "start_time": round(w["start"], 2),
                    "end_time": round(w["end"], 2),
                    "duration": round(w["end"] - w["start"], 2),
                    # 2차 검증의 0~100 단위와 맞추려고 융합 점수(0~1)에 100을 곱합니다.
                    "window_score": round(f * 100, 2),
                    "avg_joy": round(w["avg_joy"], 2),
                    "chat_count": w["chat_count"],
                    "audio_score": round(ar, 4),
                })

        print(f" ➔ 융합 임계점: {fusion_threshold * 100:.2f} | 넘은 창: {len(raw_candidates)}/{n}개")
        return raw_candidates, round(fusion_threshold * 100, 2)

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