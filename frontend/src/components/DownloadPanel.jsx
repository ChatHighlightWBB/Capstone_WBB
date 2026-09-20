function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function DownloadPanel({ finalVideoUrl, highlights }) {
  const hasClips = highlights && highlights.some((h) => h.clip_url);
  if (!finalVideoUrl && !hasClips) return null;

  return (
    <div className="download-panel">
      <h3>다운로드</h3>
      <p className="section-sub" style={{ textAlign: "left", margin: "0 0 16px" }}>
        전체 요약 영상 또는 하이라이트별로 따로 받을 수 있어요.
      </p>

      {finalVideoUrl && (
        <a href={finalVideoUrl} download className="download-card download-card-main">
          <span className="download-icon">🎬</span>
          <span className="download-card-body">
            <span className="download-card-title">전체 하이라이트 요약 영상</span>
            <span className="download-card-sub">모든 하이라이트를 이어붙인 완성본</span>
          </span>
          <span className="download-btn">⬇ 다운로드</span>
        </a>
      )}

      {hasClips && (
        <div className="download-clip-list">
          {highlights
            .filter((h) => h.clip_url)
            .map((h) => (
              <a key={h.rank} href={h.clip_url} download className="download-card">
                <span className="download-icon">🎞️</span>
                <span className="download-card-body">
                  <span className="download-card-title">
                    하이라이트 #{h.rank} <span className="mono">({formatTime(h.start_time)}–{formatTime(h.end_time)})</span>
                  </span>
                  <span className="download-card-sub">{h.streamer_speech_emotion} · {h.final_highlight_score.toFixed(1)}점</span>
                </span>
                <span className="download-btn">⬇</span>
              </a>
            ))}
        </div>
      )}
    </div>
  );
}