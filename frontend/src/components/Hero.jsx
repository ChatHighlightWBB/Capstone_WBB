import UploadForm from "./UploadForm.jsx";
import ShortsCarousel from "./ShortsCarousel.jsx";
import LiveChatDecor from "./LiveChatDecor.jsx";

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

      {/* 히어로 중앙 장식: 위쪽엔 짧은 영상이 흘러가는 캐러셀, 아래쪽엔
          실시간 채팅이 스크롤되는 모습으로 "이 서비스가 다루는 것"을 보여줍니다. */}
      <div className="hero-visual">
        <ShortsCarousel />
        <LiveChatDecor />
      </div>

      <div id="try" className="hero-form-wrap">
        <UploadForm onSubmit={onSubmit} onFileSubmit={onFileSubmit} disabled={disabled} />
      </div>
    </section>
  );
}