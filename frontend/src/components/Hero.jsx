import UploadForm from "./UploadForm.jsx";

const SOURCES = [
  { label: "유튜브", short: "YT", className: "src-yt" },
  { label: "치지직", short: "CZ", className: "src-chzzk" },
  { label: "SOOP", short: "SP", className: "src-soop" },
];

export default function Hero({ onSubmit, onFileSubmit, disabled }) {
  return (
    <section id="top" className="hero">
      <div className="hero-text">
        <h1>
          몇 시간짜리 방송,
          <br />
          터진 순간만 자동으로.
        </h1>
        <p>
          채팅·화면·음성을 동시에 읽어서 진짜 하이라이트만 골라냅니다.
          플랫폼 상관없이 링크 하나면 충분해요.
        </p>
      </div>

      <div className="system-diagram" aria-hidden="true">
        <div className="diagram-col diagram-sources">
          {SOURCES.map((s) => (
            <div key={s.label} className={`source-chip ${s.className}`}>
              <span className="source-dot" />
              {s.label}
            </div>
          ))}
        </div>

        <div className="diagram-arrow">→</div>

        <div className="diagram-col">
          <div className="engine-badge">
            <span className="engine-mascot">W</span>
            <span className="engine-label">OCR · KoBERT<br />멀티모달 분석</span>
          </div>
        </div>

        <div className="diagram-arrow">→</div>

        <div className="diagram-col diagram-output">
          <div className="output-clip">🔥 하이라이트 #1</div>
          <div className="output-clip">✨ 하이라이트 #2</div>
          <div className="output-clip dim">하이라이트 #3</div>
        </div>
      </div>

      <div id="try">
        <UploadForm onSubmit={onSubmit} onFileSubmit={onFileSubmit} disabled={disabled} />
      </div>
    </section>
  );
}