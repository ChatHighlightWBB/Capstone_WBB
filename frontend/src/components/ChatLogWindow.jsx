// 실제 채팅창처럼 위아래로 스크롤(드래그)해서 볼 수 있는 채팅 로그입니다.
// backend의 emotion_timeseries.time_series_data에는 프레임마다 인식된
// chat_text가 타임스탬프와 함께 들어있는데, 이 중 해당 하이라이트 구간
// [startTime, endTime] 안에 속하는 것만 걸러서 보여줍니다.
//
// [참고] 지금 OCR은 화면에 보이는 채팅을 한 덩어리로 인식하기 때문에,
// 실제 채팅창처럼 "닉네임별로 줄이 나뉘어 색이 다른" 형태까지는 아직
// 재현하지 못합니다. 시간순으로 인식된 텍스트를 그대로 스크롤 가능한
// 목록으로 보여주는 선에서 구현했습니다.
function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ChatLogWindow({ timeSeriesData, startTime, endTime }) {
  const lines = (timeSeriesData || []).filter(
    (d) => d.timestamp >= startTime && d.timestamp <= endTime && d.chat_text
  );

  if (lines.length === 0) {
    return <div className="chat-log-empty">이 구간에서 인식된 채팅이 없어요.</div>;
  }

  return (
    <div className="chat-log-window">
      {lines.map((line, i) => (
        <div key={i} className="chat-log-line">
          <span className="chat-log-time mono">{formatTime(line.timestamp)}</span>
          <span className="chat-log-text">{line.chat_text}</span>
        </div>
      ))}
    </div>
  );
}