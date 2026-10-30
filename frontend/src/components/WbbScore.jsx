// 와바바 스코어: 하이라이트의 웃음(기쁨) 반응이 이 방송 평소보다 얼마나 높은지를 백분위(0~100)로 나타냄.
// 1차 후보 탐지(sliding_window_nlp.py)와 같은 30초 창·5초 이동으로, 같은 크기의 구간끼리 비교함.
//  1) 방송 전체를 30초 창으로 나눠 창마다 기쁨% 평균 → 그 값들의 평균(μ)·표준편차(σ)
//  2) 하이라이트마다 그 안에 들어가는 창들의 기쁨% 평균 → 표준점수 z = (값 − μ) / σ
//  3) 하이라이트들의 z 평균을 정규분포 누적확률로 바꿔 0~100 (수능 표준점수 → 백분위와 같은 원리)
// 등급 경계 69/84/98 = 표준점수 +0.5σ(1차 후보 기준과 같은 잣대) / +1σ / +2σ 의 백분위.
const WINDOW_SEC = 30; // 창 길이(초): 1차 후보 탐지와 같음
const STEP_SEC = 5;    // 창 이동 간격(초): 1차 후보 탐지와 같음

// 표준정규분포 누적확률 Φ(z) (Abramowitz-Stegun 7.1.26 근사, 오차 1e-7 수준)
function normalCdf(z) {
  const x = Math.abs(z) / Math.SQRT2;
  const t = 1 / (1 + 0.3275911 * x);
  const erf = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
  return z >= 0 ? (1 + erf) / 2 : (1 - erf) / 2;
}

// 30초 창(5초 이동)마다 [시작, 끝, 기쁨% 평균]. 채팅이 없는 창은 반응을 알 수 없어서 뺌.
function joyWindows(timeSeriesData, endSec) {
  const windows = [];
  for (let start = 0; start + WINDOW_SEC <= endSec + STEP_SEC; start += STEP_SEC) {
    const end = Math.min(start + WINDOW_SEC, endSec);
    const joys = timeSeriesData.filter((r) => r.timestamp >= start && r.timestamp <= end).map((r) => r.joy_pct);
    if (joys.length > 0) windows.push([start, end, joys.reduce((s, v) => s + v, 0) / joys.length]);
    if (start + STEP_SEC >= endSec) break;
  }
  return windows;
}

export function computeWbbScore(highlights, timeSeriesData) {
  if (!highlights || highlights.length === 0) return 0;

  if (timeSeriesData && timeSeriesData.length > 0) {
    const endSec = Math.max(...timeSeriesData.map((r) => r.timestamp), ...highlights.map((h) => h.end_time));
    const windows = joyWindows(timeSeriesData, endSec);
    const means = windows.map((w) => w[2]);
    if (means.length > 0) {
      const mu = means.reduce((s, v) => s + v, 0) / means.length;
      const sd = Math.sqrt(means.reduce((s, v) => s + (v - mu) ** 2, 0) / means.length);
      if (sd === 0) return 50; // 방송 내내 기쁨이 같으면 하이라이트도 평소와 같다고 봄

      const zs = [];
      for (const h of highlights) {
        const inside = windows.filter((w) => w[0] >= h.start_time && w[1] <= h.end_time).map((w) => w[2]);
        if (inside.length === 0) continue; // 30초보다 짧아 창이 하나도 안 들어가면 건너뜀
        const value = inside.reduce((s, v) => s + v, 0) / inside.length;
        zs.push((value - mu) / sd);
      }
      if (zs.length > 0) {
        const z = zs.reduce((s, v) => s + v, 0) / zs.length;
        return normalCdf(z) * 100;
      }
    }
  }

  // 감정 데이터가 없으면 예전처럼 하이라이트 순위 점수 평균 (반올림은 표시하는 쪽에서)
  return highlights.reduce((sum, h) => sum + h.final_highlight_score, 0) / highlights.length;
}

export default function WbbScore({ highlights, timeSeriesData }) {
  if (!highlights || highlights.length === 0) return null;

  const score = Math.round(computeWbbScore(highlights, timeSeriesData));

  const grade =
    score >= 98 ? "레전드 웃음" :
    score >= 84 ? "빵 터진 웃음" :
    score >= 69 ? "웃음 포인트" : "잔잔한 웃음";

  return (
    <div className="wbb-score">
      <div className="wbb-score-number">{score}</div>
      <div>
        <div className="wbb-score-label">와바바 스코어</div>
        <div className="wbb-score-grade">{grade}</div>
      </div>
    </div>
  );
}