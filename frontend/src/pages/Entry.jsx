import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import Mascot from "../components/Mascot.jsx";
import { setScene, unlock } from "../sound.js";
import "./Entry.css";

// 메인 페이지(/main) 앞에 보여주는 입장 화면입니다.
// 상단에 소개 문구 한 단락만 두고, 바바 + 설계도 격자 + 신호 파형 + 채팅 말풍선으로 분위기만 보여줍니다.
// 하단 중앙의 "와바바 바로가기" 버튼을 누르면 메인 페이지로 이동합니다.
// 버튼을 누르는 순간(브라우저가 소리를 허락하는 첫 클릭) 배경음악(public/bgm/main.mp3)을 시작합니다.
// 마우스를 움직이면 배경·바바·말풍선이 서로 다른 깊이로 살짝 따라 움직입니다(--mx, --my: -1~1).

// 배경에 떠다니는 채팅 말풍선 (위치·크기·색·애니메이션 지연)
const BUBBLES = [
  { x: 12, y: 22, s: 1.1, c: "var(--entry-red)", d: 0 },
  { x: 82, y: 18, s: 0.8, c: "var(--entry-green)", d: 1.2 },
  { x: 8, y: 64, s: 0.7, c: "var(--entry-blue)", d: 2.4 },
  { x: 88, y: 58, s: 1.2, c: "var(--entry-red)", d: 0.6 },
  { x: 22, y: 82, s: 0.9, c: "var(--entry-green)", d: 1.8 },
  { x: 74, y: 80, s: 0.75, c: "var(--entry-blue)", d: 3 },
];

// 감정 신호처럼 보이는 파형 (중간에 크게 튀는 "하이라이트" 구간)
const WAVE =
  "M0 60 L60 60 L80 52 L100 66 L120 58 L150 60 L170 48 L190 70 L210 60 L260 60 " +
  "L280 40 L295 84 L310 20 L325 96 L340 30 L355 76 L370 60 L420 60 L440 54 L460 64 " +
  "L480 58 L520 60 L540 50 L560 68 L580 60 L640 60";

export default function Entry() {
  const navigate = useNavigate();
  const rootRef = useRef(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const onMove = (e) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        el.style.setProperty("--mx", ((e.clientX / window.innerWidth) * 2 - 1).toFixed(3));
        el.style.setProperty("--my", ((e.clientY / window.innerHeight) * 2 - 1).toFixed(3));
      });
    };
    window.addEventListener("pointermove", onMove);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return (
    <div className="entry" ref={rootRef}>
      <div className="entry-grid" aria-hidden="true" />
      <div className="entry-glow" aria-hidden="true" />
      <div className="entry-scan" aria-hidden="true" />

      {/* 회로 배선 */}
      <svg className="entry-circuit" viewBox="0 0 1000 600" preserveAspectRatio="none" aria-hidden="true">
        <g fill="none" strokeWidth="1.5">
          <path className="entry-trace" stroke="var(--entry-red)" d="M0 250 H180 L220 290 H340" />
          <path className="entry-trace" stroke="var(--entry-green)" d="M1000 270 H820 L780 310 H660" />
          <path className="entry-trace" stroke="var(--entry-blue)" d="M0 470 H140 L190 420 H330" />
          <path className="entry-trace" stroke="var(--entry-red)" d="M1000 460 H860 L810 410 H670" />
        </g>
        <g>
          <circle cx="340" cy="290" r="4" fill="var(--entry-red)" />
          <circle cx="660" cy="310" r="4" fill="var(--entry-green)" />
          <circle cx="330" cy="420" r="4" fill="var(--entry-blue)" />
          <circle cx="670" cy="410" r="4" fill="var(--entry-red)" />
        </g>
      </svg>

      {/* 떠다니는 채팅 말풍선 */}
      {BUBBLES.map((b, i) => (
        <svg
          key={i}
          className="entry-bubble"
          style={{ left: `${b.x}%`, top: `${b.y}%`, "--s": b.s, "--d": `${b.d}s`, color: b.c }}
          viewBox="0 0 48 40"
          aria-hidden="true"
        >
          <path
            d="M8 2 H40 A6 6 0 0 1 46 8 V24 A6 6 0 0 1 40 30 H18 L10 38 L12 30 H8 A6 6 0 0 1 2 24 V8 A6 6 0 0 1 8 2 Z"
            fill="currentColor"
            fillOpacity="0.14"
            stroke="currentColor"
            strokeWidth="2"
          />
          <circle cx="15" cy="16" r="2.4" fill="currentColor" />
          <circle cx="24" cy="16" r="2.4" fill="currentColor" />
          <circle cx="33" cy="16" r="2.4" fill="currentColor" />
        </svg>
      ))}

      {/* 상단 문구 */}
      <header className="entry-head">
        <h1 className="entry-title">
          <span className="entry-line">몇 시간짜리 방송,</span>
          <br />
          <span className="entry-line entry-line-2">
            <span className="entry-title-hl">터진 순간만</span> 자동으로.
          </span>
        </h1>
        <p className="entry-lead">
          시청자 채팅과 스트리머 목소리를 함께 읽어서 진짜 하이라이트만 골라냅니다.
          <br className="entry-br" />
          영상 파일이나 링크 하나면 충분해요.
        </p>
      </header>

      {/* 중앙: 바바 + 궤도 링 */}
      <div className="entry-core">
        <div className="entry-ring entry-ring-1" aria-hidden="true" />
        <div className="entry-ring entry-ring-2" aria-hidden="true" />
        <div className="entry-ring entry-ring-3" aria-hidden="true" />
        <div className="entry-reticle" aria-hidden="true">
          <span /><span /><span /><span />
        </div>
        <Mascot mood="excited" size={220} animate outline="#F3EFE7" className="entry-mascot" />
      </div>

      {/* 신호 파형 + 하단 중앙 버튼 */}
      <div className="entry-bottom">
        <svg className="entry-wave" viewBox="0 0 640 120" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="entry-wave-grad" x1="0" x2="1">
              <stop offset="0%" stopColor="#FF6A5C" />
              <stop offset="50%" stopColor="#2FD18F" />
              <stop offset="100%" stopColor="#3B8BFF" />
            </linearGradient>
          </defs>
          <path d={WAVE} fill="none" stroke="url(#entry-wave-grad)" strokeWidth="2.5" strokeLinejoin="round" />
        </svg>

        <button
          type="button"
          className="entry-go"
          onClick={() => {
            setScene("main");
            unlock();
            navigate("/main");
          }}
          autoFocus
        >
          와바바 바로가기
          <ArrowRight className="entry-go-arrow" size={20} strokeWidth={2.4} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
