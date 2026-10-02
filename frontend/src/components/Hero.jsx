import UploadForm from "./UploadForm.jsx";
import ShortsCarousel from "./ShortsCarousel.jsx";
import LiveChatDecor from "./LiveChatDecor.jsx";
import Mascot from "./Mascot.jsx";

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
          시청자 채팅과 스트리머 목소리를 함께 읽어서 진짜 하이라이트만 골라냅니다.
          영상 파일이나 링크 하나면 충분해요.
        </p>
      </div>

      {/* 히어로 중앙: 마스코트 "바바"가 패널 위에 걸터앉아 안내하고,
          패널 안에는 예시 영상 5개(마우스를 올리면 소리)와 흐르는 채팅이 있습니다. */}
      <div className="hero-stage">
        <div className="hero-mascot">
          <Mascot mood="happy" size={92} animate />
          <span className="hero-mascot-bubble">영상에 마우스를 올리면 소리가 나와요</span>
        </div>

        <div className="hero-visual">
          <ShortsCarousel />
          <LiveChatDecor />
        </div>
      </div>

      <div id="try" className="hero-form-wrap">
        <UploadForm onSubmit={onSubmit} onFileSubmit={onFileSubmit} disabled={disabled} />
      </div>
    </section>
  );
}
