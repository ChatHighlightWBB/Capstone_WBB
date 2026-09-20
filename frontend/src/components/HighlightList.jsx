import HighlightCard from "./HighlightCard.jsx";

// timeSeriesData(전체 감정/채팅 시계열)를 받아서 각 카드에 그대로 넘겨줍니다.
// 실제 구간별 필터링은 HighlightCard 내부에서 합니다.
export default function HighlightList({ highlights, timeSeriesData }) {
  if (!highlights || highlights.length === 0) return null;

  return (
    <div className="highlight-list">
      <h3>최종 하이라이트 <span className="mono">({highlights.length})</span></h3>
      <ul>
        {highlights.map((h, i) => (
          <HighlightCard
            key={h.rank}
            highlight={h}
            timeSeriesData={timeSeriesData}
            defaultOpen={i === 0}
          />
        ))}
      </ul>
    </div>
  );
}