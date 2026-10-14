import bisect
import difflib
import json
import math
import os
import statistics
import numpy as np
import pandas as pd

# ==============================================================================
# [채팅+음성 융합] 1차 후보 점수 설정
# 채팅 감정 점수와 스트리머 목소리 크기(1초 dB)를 각각 영상 안 순위 비율(0~1)로
# 바꾼 뒤 가중합합니다. 단위가 다른 두 값을 순위로 맞춰서 섞기 위함입니다.
# ==============================================================================
FUSION_W_CHAT = 0.7   # 융합 점수에서 채팅 순위 비중
FUSION_W_AUDIO = 0.3  # 융합 점수에서 소리 순위 비중
FUSION_K_STD = 0.5    # 융합 임계점 = 융합 점수 평균 + FUSION_K_STD * 표준편차(모집단)

# ==============================================================================
# [화면 변화량(보조)] OCR 이 5초마다 꺼낸 장면의 앞 장면 대비 픽셀 차이(0~255).
# 창 안 값들의 중간값을 VIS_LOW~VIS_HIGH 사이에서 0~1 점수로 바꿔, 채팅 비중에서
# FUSION_W_VISUAL 만큼 떼어 섞습니다. 2026-10-12 토크 방송 42분 시험에서 3%·5% 모두
# 1차 후보 변화가 없어서(끝 10초 차이 1건), 극히 일부만 반영하는 보조 신호입니다.
# ==============================================================================
FUSION_W_VISUAL = 0.05  # 화면 점수 비중 (채팅 비중 = FUSION_W_CHAT - FUSION_W_VISUAL)
VIS_LOW = 50.0          # 창 중간값이 이 이하면 화면 점수 0
VIS_HIGH = 90.0         # 이 이상이면 화면 점수 1 (사이는 비례)

# ==============================================================================
# [클립 길이 상한] 겹치는 창을 합치면 5분이 넘는 후보가 생겨, 2차 선별(최대 10개·합계 900초)에서
# 긴 후보 몇 개가 시간을 다 차지합니다. 합친 구간이 상한을 넘으면 그 안에서 창 점수 평균이
# 가장 높은 상한 길이 구간 하나만 남깁니다(쪼개지 않음: 쪼개면 붙은 클립 두 개가 중복처럼 뽑힘).
# 환경변수 CLIP_MAX_SEC 로 바꿀 수 있고, 0 이하면 상한 없음.
# ==============================================================================
CLIP_MAX_SEC_DEFAULT = 90.0  # 제안서의 "1차 후보 클립 1~2분", 태섭 확인 10-12

# ==============================================================================
# [두 번째 90초] 합친 구간이 길면(90초+30초+90초 이상) 가장 좋은 90초와 30초 이상 떨어진 두 번째 90초까지 남김.
# 붙은 조각은 안 남겨 중복처럼 보이지 않게 함(태섭 확인 10-14).
# 토크 방송 시험에서 1:05~6:30 안의 4:50~6:20(1차 87점)과 보정 부작용으로 빠지던 10:15~11:45 를 살림.
# 환경변수 CLIP_SECOND_SPAN: 없거나 "on" 이면 켜짐, "off" 면 꺼짐(첫 90초 하나만 남기는 예전 방식).
# ==============================================================================
CLIP_SECOND_SPAN_MIN_TOTAL = 210.0  # 원래 합친 구간이 이 길이(초) 이상일 때만 두 번째 90초를 찾음
CLIP_SECOND_SPAN_GAP = 30.0         # 두 번째 구간은 첫 구간과 이만큼(초) 이상 떨어져야 함

# ==============================================================================
# [저에너지 고감정 보정] 제안서 4.1.1 '저에너지 고감정 상황 시 채팅 가중치 자동 상향 보정'.
# 방송인 목소리는 이 영상에서 작은 편(하위 30%)인데 채팅 반응은 큰(상위 30%) 창은 채팅 비중을 올림.
# 2026-10-14 토크 방송 시험에서 21개 창이 걸려 '조용히 말했는데 채팅이 터진' 23:05 장면이 1차 후보로 들어옴.
# 채팅 비중 = 1 - LOW_ENERGY_W_AUDIO - 화면 비중(화면 있으면 FUSION_W_VISUAL, 없으면 0) → 화면 있으면 0.80, 없으면 0.85.
# 환경변수 LOW_ENERGY_BOOST: 없거나 "on" 이면 켜짐, "off" 면 꺼짐.
# ==============================================================================
LOW_ENERGY_AUDIO_RANK_MAX = 0.30  # 소리 순위가 이 값 미만이고
LOW_ENERGY_CHAT_RANK_MIN = 0.70   # 채팅 순위가 이 값 이상인 창만 보정
LOW_ENERGY_W_AUDIO = 0.15         # 보정 창의 소리 비중

# ==============================================================================
# [목소리 점수: 음량+피치+템포] 목소리 점수 = 음량 80% + 피치 10% + 템포 10%.
# 피치·템포는 음량과 상관이 높고 측정 한계(피치 옥타브 오검출 가능, 템포는 소리 변화량에 가까움)가 있어 보조 비중.
# 2026-10-14 토크 방송 시험에서 최종 하이라이트 차이는 1개 구간(17:35→17:30, 5초).
# 각 값을 창 순위로 바꿔 섞은 뒤 다시 순위로 바꿔 융합의 소리 순위로 씁니다(voice_features 가 있을 때만).
# ==============================================================================
VOICE_W_RMS = 0.8            # 음량 순위 비중
VOICE_W_PITCH = 0.1          # 피치 순위 비중
VOICE_W_TEMPO = 0.1          # 템포 순위 비중
VOICE_PITCH_RANK_MISSING = 0.5  # 창 안에 피치 값이 하나도 없을 때 쓰는 피치 순위

# ==============================================================================
# [채팅 점수: 기쁨+집중도+빈도] 제안서 3.1·4.1.1 채팅 빈도·채팅 간 코사인 유사도(채팅 집중도).
# 새로 올라온 줄(앞 장면 줄과 문자열 유사도 0.8 미만)만 세고, 30초 창마다 새 줄 수(빈도)와
# 새 줄끼리 글자 2~3-gram 코사인 유사도 평균(집중도)을 구함.
# 기쁨 점수와 상관이 낮아(0.29·0.34) 새 정보지만, 0.1 이상 비중에서는 후보 구간이 이어져 결과가 크게
# 흔들려 보조 비중(5%+5%)으로. 2026-10-14 토크 방송 시험에서 최종 하이라이트 변화는 5초 차이 1개.
# 각 값을 창 순위로 바꿔 섞은 뒤 다시 순위로 바꿔 융합의 채팅 순위로 씁니다(chat_lines 가 있을 때만).
# ==============================================================================
CHAT_W_JOY = 0.9                # 기쁨 순위 비중
CHAT_W_CONC = 0.05              # 집중도 순위 비중
CHAT_W_FREQ = 0.05              # 빈도 순위 비중
CHAT_NEW_LINE_SIM = 0.8         # 앞 장면 줄과 difflib 유사도가 이 이상이면 이미 있던 줄(새 줄 아님)
CHAT_CONC_MIN_LINES = 3         # 창 안 새 줄이 이 개수 이상일 때만 집중도 계산
CHAT_CONC_RANK_MISSING = 0.5    # 집중도를 못 구한 창의 집중도 순위
CHAT_NGRAM_RANGE = (2, 3)       # 집중도에 쓰는 글자 n-gram 범위(공백 뺀 글자)
# OCR 줄 목록은 줄 없는 장면을 기록하지 않으므로, 바로 앞 기록이 이보다 멀면(5초 장면 하나 이상 비었음)
# 앞 장면은 줄이 없던 것으로 봅니다(앞 장면 줄과만 비교하는 규칙을 그대로 지키기 위함).
CHAT_SCENE_GAP_SEC = 7.5


def _chat_new_lines(chat_lines):
    """장면 목록 [{"t", "lines"}] → [(t, 새 줄 목록)]. 바로 앞 장면 줄 중 하나와 비슷하면 이미 있던 줄로 뺌."""
    out, prev_t, prev_lines = [], None, []
    for scene in sorted(chat_lines, key=lambda s: float(s["t"])):
        t, lines = float(scene["t"]), list(scene.get("lines") or [])
        if prev_t is None or t - prev_t > CHAT_SCENE_GAP_SEC:
            prev_lines = []  # 바로 앞 5초 장면이 기록에 없음 = 그 장면에 줄이 없었음
        new = [ln for ln in lines
               if not any(difflib.SequenceMatcher(None, ln, p).ratio() >= CHAT_NEW_LINE_SIM for p in prev_lines)]
        out.append((t, new))
        prev_t, prev_lines = t, lines
    return out


def _chat_concentration(lines):
    """줄들의 공백 뺀 글자 n-gram 개수 벡터 → 모든 줄 쌍 코사인 유사도 평균(n-gram 이 하나도 없으면 0)"""
    # scikit-learn 은 무거워서 서버 시작이 느려지지 않게 함수 안에서 import
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    docs = [ln.replace(" ", "") for ln in lines]
    try:
        X = CountVectorizer(analyzer="char", ngram_range=CHAT_NGRAM_RANGE).fit_transform(docs)
    except ValueError:  # 모든 줄이 1글자라 n-gram 이 하나도 없음
        return 0.0
    sim = cosine_similarity(X)
    pairs = [sim[i, j] for i in range(len(docs)) for j in range(i + 1, len(docs))]
    return float(np.mean(pairs))

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
                                 audio_db_per_sec=None, visual_samples=None, voice_features=None,
                                 chat_lines=None):
        # audio_db_per_sec: 1초마다의 목소리 대역 음량(dB) 리스트 (audio_energy.py).
        #   None 이면 예전과 똑같이 채팅 감정 점수만으로 후보를 고릅니다.
        #   값이 있으면 채팅+음성 융합 점수로 후보를 고릅니다.
        # visual_samples: [(초, 화면 변화량), ...] (OCR 워커의 visual_change.csv).
        #   채팅+음성 융합일 때만 쓰고, None 이면 채팅+음성 융합과 완전히 같습니다.
        # voice_features: audio_energy.compute_voice_features_per_sec 결과 dict(f0_hz, onset_strength 1초 값).
        #   채팅+음성 융합일 때만 쓰고, None 이면 소리 순위는 음량만으로 계산합니다(예전과 완전히 같음).
        # chat_lines: OCR 워커의 채팅 줄 목록 [{"t": 초, "lines": [...]}, ...] (chat_lines.jsonl).
        #   채팅+음성 융합일 때만 쓰고, None 이면 채팅 순위는 기쁨 점수만으로 계산합니다(예전과 완전히 같음).
        use_fusion = audio_db_per_sec is not None
        if use_fusion and visual_samples is not None:
            mode_label = "1차 후보: 채팅+음성+화면(보조) 융합"
        elif use_fusion:
            mode_label = "1차 후보: 채팅+음성 융합"
        else:
            mode_label = "1차 후보: 채팅 단독"
        if use_fusion and voice_features is not None:
            mode_label += " (목소리: 음량+피치+템포)"
        if use_fusion and chat_lines is not None:
            mode_label += " (채팅: 기쁨+집중도+빈도)"
        print("=" * 70)
        print(f"🔍 [1차 하이라이트 탐지] 30초 Sliding Window 분석 가동")
        print(f" ➔ {mode_label}")
        print(f" ➔ 영상 총 길이: {self.duration_sec:.1f}초 | 적용 동적 임계점: {self.threshold}%")
        print("=" * 70)

        df = pd.DataFrame(self.time_series)
        if df.empty:
            print("❌ 분석할 시계열 데이터가 비어 있습니다.")
            return []

        applied_threshold = self.threshold
        if use_fusion:
            raw_candidates, applied_threshold = self._fusion_raw_candidates(
                df, audio_db_per_sec, window_size, step_size, visual_samples, voice_features, chat_lines)
        else:
            raw_candidates = self._chat_raw_candidates(df, window_size, step_size)

        # [클립 길이 상한] 상한 값: CLIP_MAX_SEC 환경변수가 있으면 그 값(잘못된 값이면 기본값), 0 이하면 상한 없음
        max_sec = CLIP_MAX_SEC_DEFAULT
        env_max = os.getenv("CLIP_MAX_SEC")
        if env_max is not None:
            try:
                max_sec = float(env_max)
                if not math.isfinite(max_sec):
                    max_sec = CLIP_MAX_SEC_DEFAULT
            except ValueError:
                max_sec = CLIP_MAX_SEC_DEFAULT
        # 아래 병합이 창 dict 를 직접 고쳐 쓰므로, 상한 계산에 쓸 합치기 전 창 목록을 미리 복사해 둡니다.
        raw_windows = [dict(c) for c in raw_candidates]

        # 1. 겹치는 윈도우 구간 병합
        merged_candidates = self._merge_overlapping_intervals(raw_candidates)

        # 1-1. 합친 구간이 상한보다 길면 점수가 가장 높은 상한 길이 구간 하나로 줄임 (채팅 단독·융합 공통)
        if max_sec > 0:
            merged_candidates = self._cap_long_intervals(merged_candidates, raw_windows, max_sec, step_size)

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

    def _fusion_raw_candidates(self, df, audio_db_per_sec, window_size, step_size, visual_samples=None,
                               voice_features=None, chat_lines=None):
        """
        [채팅+음성 융합] 모든 창(채팅 없는 창 포함)의 채팅 점수·소리 점수를 구해
        각각 순위 비율로 바꾼 뒤 융합하고, 융합 임계점 이상인 창을 모읍니다.
        visual_samples 가 있으면 화면 점수(0~1)를 FUSION_W_VISUAL 비중으로 더합니다.
        voice_features 가 있으면 융합의 소리 순위를 음량·피치·템포 순위를 섞은 목소리 순위로 바꿉니다
        (저에너지 고감정 보정 조건은 음량 순위로만 판단).
        chat_lines 가 있으면 융합의 채팅 순위를 기쁨·집중도·빈도 순위를 섞은 채팅 순위로 바꿉니다
        (저에너지 고감정 보정 조건은 기쁨 순위로만 판단).
        반환: (임계점 넘은 창 목록, 결과 metadata 에 넣을 임계점(0~100 단위))
        """
        use_visual = visual_samples is not None
        if use_visual:
            # 창마다 [start, end) 안의 값을 빨리 찾으려고 시각 순으로 정렬해 둡니다.
            vis_sorted = sorted(visual_samples)
            vis_times = [t for t, _ in vis_sorted]
            vis_values = [v for _, v in vis_sorted]

        use_voice = voice_features is not None
        if use_voice:
            # 1초 값 배열(f0 없는 초는 NaN). 창 피치는 영상 전체 f0 중간값 대비 반음 차이로 씁니다.
            f0_per_sec = np.array([np.nan if v is None else v for v in voice_features["f0_hz"]], dtype=float)
            onset_per_sec = np.array(voice_features["onset_strength"], dtype=float)
            f0_all = float(np.nanmedian(f0_per_sec))

        use_chat_sim = chat_lines is not None
        if use_chat_sim:
            # 장면마다 새로 올라온 줄만 남겨 둡니다(창마다 빈도·집중도 계산에 씀).
            chat_new = _chat_new_lines(chat_lines)

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

            # 화면 점수: 값의 시각 t 는 (t-5초 → t) 변화 → 창 [start, end) 안의 값들 중간값(없으면 0)
            visual_score = 0.0
            if use_visual:
                lo = bisect.bisect_left(vis_times, current_start)
                hi = bisect.bisect_left(vis_times, current_end)
                vis_med = statistics.median(vis_values[lo:hi]) if hi > lo else 0.0
                visual_score = min(1.0, max(0.0, (vis_med - VIS_LOW) / (VIS_HIGH - VIS_LOW)))

            # 피치·템포: 음량과 같은 1초 범위 [floor(start), ceil(end)) 의 f0 중간값(반음)·onset strength 평균
            pitch_st, tempo = np.nan, np.nan
            if use_voice:
                a, b = int(math.floor(current_start)), int(math.ceil(current_end))
                wf = f0_per_sec[a:b]
                wf = wf[np.isfinite(wf)]
                if len(wf):
                    pitch_st = 12 * math.log2(float(np.median(wf)) / f0_all)
                if len(onset_per_sec[a:b]):
                    tempo = float(onset_per_sec[a:b].mean())

            # 채팅 빈도·집중도: 채팅 감정과 같은 포함 규칙(start <= t <= end)의 장면들의 새 줄
            chat_freq, chat_conc = 0, np.nan
            if use_chat_sim:
                new_lines = [ln for t, new in chat_new if current_start <= t <= current_end for ln in new]
                chat_freq = len(new_lines)
                if chat_freq >= CHAT_CONC_MIN_LINES:
                    chat_conc = _chat_concentration(new_lines)

            windows.append({
                "start": current_start, "end": current_end,
                "avg_joy": avg_joy, "chat_count": len(window_df),
                "chat_score": chat_score, "audio_score": audio_score,
                "visual_score": visual_score,
                "pitch_st": pitch_st, "tempo": tempo,
                "chat_freq": chat_freq, "chat_conc": chat_conc,
            })

            current_start += step_size
            if current_start >= self.duration_sec:
                break

        # 순위 비율(0~1, 가장 큰 값 1, 같은 값은 평균 순위)
        n = len(windows)
        chat_rank = pd.Series([w["chat_score"] for w in windows], dtype=float).rank(method="average") / n
        # 저에너지 고감정 보정 조건은 채팅 점수를 섞더라도 기쁨 순위로만 판단하려고 따로 둡니다.
        joy_rank = chat_rank
        if use_chat_sim:
            # [채팅 점수] 집중도 순위(값 있는 창끼리, 없는 창은 0.5)·빈도 순위를 기쁨 순위와 섞어 다시 순위로 바꿈
            conc = pd.Series([w["chat_conc"] for w in windows], dtype=float)
            conc_rank = (conc.rank(method="average") / conc.notna().sum()).fillna(CHAT_CONC_RANK_MISSING)
            freq_rank = pd.Series([w["chat_freq"] for w in windows], dtype=float).rank(method="average") / n
            chat_mix = CHAT_W_JOY * chat_rank + CHAT_W_CONC * conc_rank + CHAT_W_FREQ * freq_rank
            chat_rank = chat_mix.rank(method="average") / n
        audio_rank = pd.Series([w["audio_score"] for w in windows], dtype=float).rank(method="average") / n
        # 저에너지 고감정 보정 조건은 목소리 점수를 섞더라도 음량 순위로만 판단하려고 따로 둡니다.
        loud_rank = audio_rank
        if use_voice:
            # [목소리 점수] 피치 순위(값 있는 창끼리, 없는 창은 0.5)·템포 순위를 음량 순위와 섞어 다시 순위로 바꿈
            pitch = pd.Series([w["pitch_st"] for w in windows], dtype=float)
            pitch_rank = (pitch.rank(method="average") / pitch.notna().sum()).fillna(VOICE_PITCH_RANK_MISSING)
            tempo_rank = pd.Series([w["tempo"] for w in windows], dtype=float).rank(method="average") / n
            voice = VOICE_W_RMS * audio_rank + VOICE_W_PITCH * pitch_rank + VOICE_W_TEMPO * tempo_rank
            audio_rank = voice.rank(method="average") / n
        if use_visual:
            # 화면 점수는 이미 0~1 이라 순위로 바꾸지 않고, 채팅 비중에서 FUSION_W_VISUAL 만큼 떼어 씁니다.
            visual_score = pd.Series([w["visual_score"] for w in windows], dtype=float)
            fusion = ((FUSION_W_CHAT - FUSION_W_VISUAL) * chat_rank + FUSION_W_AUDIO * audio_rank
                      + FUSION_W_VISUAL * visual_score)
        else:
            fusion = FUSION_W_CHAT * chat_rank + FUSION_W_AUDIO * audio_rank

        # [저에너지 고감정 보정] 목소리는 작은데 채팅 반응이 큰 창만 채팅 비중을 올려 다시 계산합니다.
        # 나머지 창은 위 융합 점수 그대로이고, 임계점은 보정이 반영된 최종 융합 점수로 계산합니다.
        use_boost = os.getenv("LOW_ENERGY_BOOST", "on").strip().lower() != "off"
        boosted = [False] * n
        if use_boost:
            w_vis = FUSION_W_VISUAL if use_visual else 0.0
            w_chat = 1.0 - LOW_ENERGY_W_AUDIO - w_vis
            boosted = ((loud_rank < LOW_ENERGY_AUDIO_RANK_MAX) & (joy_rank >= LOW_ENERGY_CHAT_RANK_MIN)).tolist()
            boost_fusion = w_chat * chat_rank + LOW_ENERGY_W_AUDIO * audio_rank
            if use_visual:
                boost_fusion = boost_fusion + w_vis * visual_score
            fusion = fusion.where(~pd.Series(boosted), boost_fusion)
            print(f" ➔ 저에너지 고감정 보정: {sum(boosted)}개 창")

        # 융합 임계점 = 평균 + K * 표준편차(모집단). self.threshold 는 건드리지 않습니다.
        fusion_threshold = float(fusion.mean() + FUSION_K_STD * fusion.std(ddof=0))

        raw_candidates = []
        for w, f, ar, bst in zip(windows, fusion.tolist(), audio_rank.tolist(), boosted):
            if f >= fusion_threshold:
                cand = {
                    "start_time": round(w["start"], 2),
                    "end_time": round(w["end"], 2),
                    "duration": round(w["end"] - w["start"], 2),
                    # 2차 검증의 0~100 단위와 맞추려고 융합 점수(0~1)에 100을 곱합니다.
                    "window_score": round(f * 100, 2),
                    "avg_joy": round(w["avg_joy"], 2),
                    "chat_count": w["chat_count"],
                    "audio_score": round(ar, 4),
                }
                if use_visual:
                    cand["visual_score"] = round(w["visual_score"], 4)
                if use_boost:
                    cand["low_energy_boost"] = bool(bst)
                raw_candidates.append(cand)

        print(f" ➔ 융합 임계점: {fusion_threshold * 100:.2f} | 넘은 창: {len(raw_candidates)}/{n}개")
        return raw_candidates, round(fusion_threshold * 100, 2)

    def _cap_long_intervals(self, merged, raw_candidates, max_sec, step_size):
        """
        [클립 길이 상한] 합친 구간(merged) 중 duration 이 max_sec 를 넘는 것은,
        그 안의 합치기 전 창(raw_candidates)들로 길이 max_sec 구간을 step_size 씩 옮겨 보며
        [s, s+max_sec] 안에 완전히 들어가는 창들의 window_score 평균이 가장 큰 위치 하나만 남깁니다
        (같으면 앞쪽, 끝은 원래 구간 끝을 넘지 않음). 원래 길이는 original_duration 키로 남깁니다.
        [두 번째 90초] CLIP_SECOND_SPAN 이 켜져 있고 원래 구간이 CLIP_SECOND_SPAN_MIN_TOTAL 이상이면,
        첫 구간과 CLIP_SECOND_SPAN_GAP 이상 떨어진 위치 중 같은 방식으로 하나 더 남깁니다(second_span=True).
        """
        use_second = os.getenv("CLIP_SECOND_SPAN", "on").strip().lower() != "off"
        result = []
        n_cut = 0
        n_second = 0
        for iv in merged:
            if iv["duration"] <= max_sec:
                result.append(iv)
                continue

            a, b = iv["start_time"], iv["end_time"]
            inside = [w for w in raw_candidates if w["start_time"] >= a and w["end_time"] <= b]
            best = self._best_capped_span(inside, a, b, max_sec, step_size)

            if best is None:
                # 상한이 창 길이보다 짧아 들어가는 창이 없으면 자를 기준이 없으므로 원래 구간을 그대로 둡니다.
                result.append(iv)
                continue

            _, s1, e1, ws = best
            result.append(self._make_capped_interval(iv, s1, e1, ws))
            n_cut += 1

            if use_second and iv["duration"] >= CLIP_SECOND_SPAN_MIN_TOTAL:
                # 첫 구간과 붙어 있거나 겹치는 위치는 빼고, GAP 이상 떨어진 위치에서만 두 번째를 찾습니다.
                gap = CLIP_SECOND_SPAN_GAP
                far = lambda s, e: e <= s1 - gap + 1e-9 or s >= e1 + gap - 1e-9
                best2 = self._best_capped_span(inside, a, b, max_sec, step_size, allowed=far)
                if best2 is not None:  # 들어가는 창이 없으면 두 번째는 만들지 않음
                    _, s2, e2, ws2 = best2
                    second = self._make_capped_interval(iv, s2, e2, ws2)
                    second["second_span"] = True
                    result.append(second)
                    n_second += 1

        if n_cut:
            msg = f" ➔ 길이 상한 {max_sec:.0f}초: {n_cut}개 구간을 잘라냄"
            if use_second:
                msg += f" (두 번째 {max_sec:.0f}초 {n_second}개 추가)"
            print(msg)
        return result

    def _best_capped_span(self, inside, a, b, max_sec, step_size, allowed=None):
        """
        [a, b] 안에서 길이 max_sec 구간을 step_size 씩 옮겨 보며 [s, s+max_sec] 안에 완전히 들어가는
        창들의 window_score 평균이 가장 큰 위치를 고릅니다(같으면 앞쪽). allowed(s, e) 가 False 인 위치는 건너뜀.
        반환: (평균 점수, 시작, 끝, 안에 든 창들) 또는 들어가는 창이 없으면 None
        """
        best = None
        s = a
        while s + max_sec <= b + 1e-9:
            e = s + max_sec
            if allowed is None or allowed(s, e):
                ws = [w for w in inside if w["start_time"] >= s and w["end_time"] <= e]
                if ws:
                    avg = sum(w["window_score"] for w in ws) / len(ws)
                    if best is None or avg > best[0]:  # 같은 평균이면 앞쪽(먼저 찾은 것) 유지
                        best = (avg, s, e, ws)
            s += step_size
        return best

    def _make_capped_interval(self, iv, s, e, ws):
        """잘라낸 구간의 필드를 채웁니다: window_score 최대, chat_count 합, visual_score 최대, avg_joy·audio_score 첫 창."""
        cut = dict(iv)
        cut["start_time"] = round(s, 2)
        cut["end_time"] = round(e, 2)
        cut["duration"] = round(e - s, 2)
        cut["window_score"] = max(w["window_score"] for w in ws)
        cut["chat_count"] = sum(w["chat_count"] for w in ws)
        if "visual_score" in iv:
            cut["visual_score"] = max(w.get("visual_score", 0.0) for w in ws)
        cut["avg_joy"] = ws[0]["avg_joy"]
        if "audio_score" in iv:
            cut["audio_score"] = ws[0]["audio_score"]
        # 잘라낸 90초 안에 보정된 창이 있을 때만 표시(합친 긴 구간의 다른 위치 보정이 옮겨 오지 않게)
        if "low_energy_boost" in iv:
            cut["low_energy_boost"] = any(w.get("low_energy_boost", False) for w in ws)
        cut["original_duration"] = iv["duration"]
        return cut

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
                # 화면 점수는 합친 구간에서 가장 큰 값을 남겨, 화면 변화가 실제로 얼마나 반영됐는지 결과에서 볼 수 있게 함
                if "visual_score" in curr and "visual_score" in next_interval:
                    curr["visual_score"] = max(curr["visual_score"], next_interval["visual_score"])
                # 저에너지 보정 창이 하나라도 섞이면 합친 구간도 보정 표시를 남김
                if "low_energy_boost" in curr and "low_energy_boost" in next_interval:
                    curr["low_energy_boost"] = curr["low_energy_boost"] or next_interval["low_energy_boost"]
            else:
                merged.append(curr)
                curr = next_interval
        merged.append(curr)
        return merged

if __name__ == "__main__":
    detector = WBBSlidingWindowDetector()
    detector.detect_candidate_windows()