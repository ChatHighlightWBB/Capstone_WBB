import { colorForEmotion } from "../emotionColors.js";

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// backend가 반환하는 highlight_result.highlights 를 그대로 입력받습니다.
// 카드마다 지배 감정(streamer_speech_emotion) 색으로 왼쪽 테두리를 표시해
// 감정 차트와 하이라이트 목록이 같은 색상 언어를 공유하도록 합니다.
export default function HighlightList({ highlights, onSeek }) {
  if (!highlights || highlights.length === 0) return null;

  return (
    <div className="highlight-list">
      <h3>최종 하이라이트 <span className="mono">({highlights.length})</span></h3>
      <ul>
        {highlights.map((h) => (
          <li
            key={h.rank}
            className="highlight-item"
            style={{ borderLeftColor: colorForEmotion(h.streamer_speech_emotion) }}
            onClick={() => onSeek?.(h.start_time)}
          >
            <div className="highlight-rank mono">{String(h.rank).padStart(2, "0")}</div>
            <div className="highlight-body">
              <div className="highlight-time">
                <span className="mono">
                  {formatTime(h.start_time)} – {formatTime(h.end_time)}
                </span>
                <span
                  className="emotion-tag"
                  style={{ color: colorForEmotion(h.streamer_speech_emotion) }}
                >
                  {h.streamer_speech_emotion}
                </span>
                <span className="mono highlight-score">
                  {h.final_highlight_score.toFixed(1)}점
                </span>
              </div>
              <p className="highlight-transcript">
                {h.streamer_speech_text.length > 120
                  ? h.streamer_speech_text.slice(0, 120) + "…"
                  : h.streamer_speech_text}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
