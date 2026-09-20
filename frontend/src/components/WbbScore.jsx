// 하이라이트들의 최종 점수를 하나의 "와바바 스코어"로 종합해서 보여줌
export default function WbbScore({ highlights }) {
  if (!highlights || highlights.length === 0) return null;

  const avg =
    highlights.reduce((sum, h) => sum + h.final_highlight_score, 0) / highlights.length;
  const score = Math.round(avg);

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