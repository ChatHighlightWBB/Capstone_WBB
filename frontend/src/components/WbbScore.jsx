// 하이라이트 구간 채팅의 기쁨 반응을 0~100 으로 종합한 점수.
// 하이라이트 순위용 점수(영상 안 순위)와 달리 방송끼리 비교할 수 있음.

// 하이라이트마다 구간 안 채팅의 joy_pct 로 (평균×0.7 + 최고×0.3) 을 구해 평균.
// 채팅 레코드가 있는 하이라이트가 하나도 없거나 감정 데이터가 없으면
// 예전처럼 final_highlight_score 평균을 돌려줌. (반올림은 표시하는 쪽에서)
export function computeWbbScore(highlights, timeSeriesData) {
  if (!highlights || highlights.length === 0) return 0;

  if (timeSeriesData && timeSeriesData.length > 0) {
    const perHighlight = [];
    for (const h of highlights) {
      const joys = timeSeriesData
        .filter((r) => r.timestamp >= h.start_time && r.timestamp <= h.end_time)
        .map((r) => r.joy_pct);
      if (joys.length === 0) continue; // 구간 안 채팅이 없으면 건너뜀
      const avg = joys.reduce((sum, v) => sum + v, 0) / joys.length;
      perHighlight.push(avg * 0.7 + Math.max(...joys) * 0.3);
    }
    if (perHighlight.length > 0) {
      return perHighlight.reduce((sum, v) => sum + v, 0) / perHighlight.length;
    }
  }

  return highlights.reduce((sum, h) => sum + h.final_highlight_score, 0) / highlights.length;
}

export default function WbbScore({ highlights, timeSeriesData }) {
  if (!highlights || highlights.length === 0) return null;

  const score = Math.round(computeWbbScore(highlights, timeSeriesData));

  const grade =
    score >= 80 ? "역대급 방송" :
    score >= 60 ? "재밌는 방송" :
    score >= 40 ? "잔잔한 방송" : "차분한 방송";

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