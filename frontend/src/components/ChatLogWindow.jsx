// 실제 채팅창처럼 위아래로 스크롤(드래그)해서 볼 수 있는 채팅 로그입니다.
// backend의 emotion_timeseries.time_series_data에는 프레임마다 인식된
// chat_text가 타임스탬프와 함께 들어있는데, 이 중 해당 하이라이트 구간
// [startTime, endTime] 안에 속하는 것만 걸러서 보여줍니다.
//
// [참고] 지금 OCR은 화면에 보이는 채팅을 한 덩어리로 인식하기 때문에,
// 실제 채팅창처럼 "닉네임별로 줄이 나뉘어 색이 다른" 형태까지는 아직
// 재현하지 못합니다. 시간순으로 인식된 텍스트를 그대로 스크롤 가능한
// 목록으로 보여주는 선에서 구현했습니다.
//
// [영상 연동] 하이라이트 카드에서 curSec(클립 재생 위치를 원본 초로 바꾼 값)과
// onSeek(원본 초로 클립 이동)을 넘기면, 지금 위치의 줄을 강조하고 줄을 눌러
// 그 시각으로 옮길 수 있습니다. 두 props 가 없으면 예전과 똑같이 보여 줍니다.
import { useEffect, useRef } from "react";

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ChatLogWindow({ timeSeriesData, startTime, endTime, curSec, onSeek }) {
  const lines = (timeSeriesData || []).filter(
    (d) => d.timestamp >= startTime && d.timestamp <= endTime && d.chat_text
  );
  const sync = typeof onSeek === "function";

  // 지금 재생 위치(curSec)보다 같거나 앞선 마지막 줄 = 지금 화면에 떠 있던 채팅
  let activeIndex = -1;
  if (sync && curSec != null) {
    lines.forEach((line, i) => {
      if (line.timestamp <= curSec) activeIndex = i;
    });
  }

  // 강조 줄이 채팅창 안에 보이도록 채팅창(스크롤 영역)의 scrollTop 만 조정합니다.
  // scrollIntoView 를 쓰면 페이지 전체까지 따라 스크롤되어 보던 위치가 흔들려서 쓰지 않습니다.
  const boxRef = useRef(null);
  const activeRef = useRef(null);
  useEffect(() => {
    const box = boxRef.current;
    const row = activeRef.current;
    if (!box || !row) return;
    const boxRect = box.getBoundingClientRect();
    const rowRect = row.getBoundingClientRect();
    if (rowRect.top < boxRect.top) box.scrollTop -= boxRect.top - rowRect.top;
    else if (rowRect.bottom > boxRect.bottom) box.scrollTop += rowRect.bottom - boxRect.bottom;
  }, [activeIndex]);

  if (lines.length === 0) {
    return <div className="chat-log-empty">이 구간에서 인식된 채팅이 없어요.</div>;
  }

  return (
    <div ref={boxRef} className={`chat-log-window${sync ? " is-sync" : ""}`}>
      {lines.map((line, i) => (
        // 같은 timestamp 가 겹칠 수도 있어 순번을 붙여 key 를 만듭니다.
        <div
          key={`${line.timestamp}-${i}`}
          ref={i === activeIndex ? activeRef : undefined}
          className={`chat-log-line${i === activeIndex ? " is-active" : ""}`}
          onClick={sync ? () => onSeek(line.timestamp) : undefined}
        >
          <span className="chat-log-time mono">{formatTime(line.timestamp)}</span>
          <span className="chat-log-text">{line.chat_text}</span>
        </div>
      ))}
    </div>
  );
}