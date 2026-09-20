import { useState } from "react";
import { colorForEmotion } from "../emotionColors.js";
import EmotionChart from "./EmotionChart.jsx";
import ChatLogWindow from "./ChatLogWindow.jsx";

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// 이 시리즈 전체(timeSeriesData)에서 [start,end] 구간만 잘라 미니 차트에 넘깁니다.
function sliceTimeSeries(timeSeriesData, start, end) {
  if (!timeSeriesData) return [];
  return timeSeriesData.filter((d) => d.timestamp >= start && d.timestamp <= end);
}

export default function HighlightCard({ highlight, timeSeriesData, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const h = highlight;
  const sliced = sliceTimeSeries(timeSeriesData, h.start_time, h.end_time);

  return (
    <li
      className="highlight-card"
      style={{ borderLeftColor: colorForEmotion(h.streamer_speech_emotion) }}
    >
      <button className="highlight-card-header" onClick={() => setOpen(!open)}>
        <span className="highlight-rank mono">{String(h.rank).padStart(2, "0")}</span>
        <div className="highlight-card-summary">
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
            <span className="mono highlight-score">{h.final_highlight_score.toFixed(1)}점</span>
          </div>
          <p className="highlight-transcript">
            {h.streamer_speech_text.length > 100
              ? h.streamer_speech_text.slice(0, 100) + "…"
              : h.streamer_speech_text}
          </p>
        </div>
        <span className={`highlight-card-chevron ${open ? "open" : ""}`} aria-hidden="true">
          ⌄
        </span>
      </button>

      {open && (
        <div className="highlight-card-body">
          {h.clip_url ? (
            <video className="highlight-card-video" src={h.clip_url} controls />
          ) : (
            <div className="chat-log-empty">이 하이라이트의 개별 클립이 아직 없어요.</div>
          )}

          <div className="highlight-card-panels">
            <div className="highlight-card-panel">
              <h4>이 구간 감정 변화</h4>
              <EmotionChart timeSeriesData={sliced} compact />
            </div>
            <div className="highlight-card-panel">
              <h4>이 구간 채팅</h4>
              <ChatLogWindow
                timeSeriesData={timeSeriesData}
                startTime={h.start_time}
                endTime={h.end_time}
              />
            </div>
          </div>
        </div>
      )}
    </li>
  );
}