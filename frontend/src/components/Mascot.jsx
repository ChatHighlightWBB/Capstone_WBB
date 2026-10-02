import { useId } from "react";

// 와바바 마스코트 "바바"
// 시청자 채팅 말풍선이 몸이 된 캐릭터입니다. 머리 위 안테나 끝은 재생 버튼,
// 몸 색은 로고(W)와 같은 빨강·초록·파랑(유튜브·치지직·SOOP) 그라데이션이에요.
//
// mood: "happy"(기본) | "excited"(터졌을 때) | "thinking"(안내) | "oops"(오류)
//       | "working"(분석 중 — 땀 흘리며 열심히 일하는 모습, 땀방울과 몸 흔들림이 자동 재생)
// animate: true면 눈 깜빡임 + 살짝 떠 있는 움직임 (홈 히어로에서만 사용)
// outline: 몸 테두리·안테나 색. 어두운 배경(사이드바 등)에서는 밝은 색을 넘기면 스티커처럼 보여요.
export default function Mascot({
  mood = "happy",
  size = 96,
  animate = false,
  outline = "#17171B",
  className = "",
}) {
  const uid = useId().replace(/:/g, "");
  const gradId = `baba-body-${uid}`;

  return (
    <svg
      className={`mascot mascot-mood-${mood} ${animate ? "mascot-animate" : ""} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role="img"
      aria-label="와바바 마스코트 바바"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FF6A5C" />
          <stop offset="55%" stopColor="#2FD18F" />
          <stop offset="100%" stopColor="#3B8BFF" />
        </linearGradient>
      </defs>

      <g className="mascot-body">
        {/* 안테나 + 재생 버튼 */}
        <line x1="60" y1="20" x2="60" y2="8" stroke={outline} strokeWidth="3" strokeLinecap="round" />
        <circle cx="60" cy="7" r="6" fill="#FF3B30" stroke={outline} strokeWidth="2.5" />
        <path d="M58.4 4.6 L62.6 7 L58.4 9.4 Z" fill="#fff" />

        {/* 말풍선 몸통 (왼쪽 아래 꼬리) */}
        <path
          d="M24 20 H96 A18 18 0 0 1 114 38 V78 A18 18 0 0 1 96 96 H46 L26 112 L30 96 H24 A18 18 0 0 1 6 78 V38 A18 18 0 0 1 24 20 Z"
          fill={`url(#${gradId})`}
          stroke={outline}
          strokeWidth="3.5"
          strokeLinejoin="round"
        />

        {/* 볼 */}
        <ellipse cx="30" cy="70" rx="7" ry="4.5" fill="#FF8FA3" opacity="0.75" />
        <ellipse cx="90" cy="70" rx="7" ry="4.5" fill="#FF8FA3" opacity="0.75" />

        <Eyes mood={mood} />
        <Mouth mood={mood} />
        <Extra mood={mood} />
      </g>
    </svg>
  );
}

function Eyes({ mood }) {
  if (mood === "working") {
    // 화면을 뚫어지게 보는 눈 + 살짝 올라간 눈썹 (힘들지만 열심히)
    return (
      <g>
        <path d="M31 42 L50 37" stroke="#17171B" strokeWidth="4" strokeLinecap="round" />
        <path d="M89 42 L70 37" stroke="#17171B" strokeWidth="4" strokeLinecap="round" />
        <ellipse cx="42" cy="56" rx="10" ry="9" fill="#fff" stroke="#17171B" strokeWidth="3" />
        <ellipse cx="78" cy="56" rx="10" ry="9" fill="#fff" stroke="#17171B" strokeWidth="3" />
        <circle cx="40" cy="59" r="5" fill="#17171B" />
        <circle cx="76" cy="59" r="5" fill="#17171B" />
      </g>
    );
  }
  if (mood === "excited") {
    // > < 모양 눈
    return (
      <g stroke="#17171B" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none">
        <path d="M36 46 L46 53 L36 60" />
        <path d="M84 46 L74 53 L84 60" />
      </g>
    );
  }
  const pupilShift = mood === "thinking" ? { x: 3, y: -3 } : { x: 1, y: 1 };
  return (
    <g className="mascot-eyes">
      <ellipse cx="42" cy="54" rx="10" ry="11" fill="#fff" stroke="#17171B" strokeWidth="3" />
      <ellipse cx="78" cy="54" rx="10" ry="11" fill="#fff" stroke="#17171B" strokeWidth="3" />
      <circle cx={42 + pupilShift.x} cy={54 + pupilShift.y} r="5" fill="#17171B" />
      <circle cx={78 + pupilShift.x} cy={54 + pupilShift.y} r="5" fill="#17171B" />
      <circle cx={44 + pupilShift.x} cy={52 + pupilShift.y} r="1.6" fill="#fff" />
      <circle cx={80 + pupilShift.x} cy={52 + pupilShift.y} r="1.6" fill="#fff" />
    </g>
  );
}

function Mouth({ mood }) {
  const common = { stroke: "#17171B", strokeWidth: 3.5, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (mood) {
    case "excited":
      return <path d="M46 70 Q60 92 74 70 Z" fill="#17171B" {...common} />;
    case "thinking":
      return <path d="M52 78 L68 76" fill="none" {...common} />;
    case "oops":
      return <path d="M48 80 Q54 74 60 80 Q66 86 72 80" fill="none" {...common} />;
    case "working":
      // 입을 앙 다문 모습
      return (
        <g>
          <rect x="50" y="74" width="20" height="8" rx="3" fill="#fff" stroke="#17171B" strokeWidth="3" />
          <path d="M57 74 V82 M63 74 V82" stroke="#17171B" strokeWidth="2" />
        </g>
      );
    default:
      return <path d="M50 74 Q60 84 70 74" fill="none" {...common} />;
  }
}

function Extra({ mood }) {
  if (mood === "thinking") {
    return (
      <text x="98" y="16" fontSize="22" fontWeight="900" fill="#17171B" fontFamily="inherit">
        ?
      </text>
    );
  }
  if (mood === "working") {
    // 양옆으로 흘러내리는 땀방울 두 개 (CSS로 반복 애니메이션)
    return (
      <g>
        <path
          className="mascot-sweat mascot-sweat-1"
          d="M106 30 Q101 39 106 42 Q111 39 106 30 Z"
          fill="#7CC4FF"
          stroke="#17171B"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <path
          className="mascot-sweat mascot-sweat-2"
          d="M14 36 Q9 45 14 48 Q19 45 14 36 Z"
          fill="#7CC4FF"
          stroke="#17171B"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </g>
    );
  }
  if (mood === "oops") {
    // 식은땀 한 방울
    return (
      <path
        d="M104 36 Q99 45 104 48 Q109 45 104 36 Z"
        fill="#7CC4FF"
        stroke="#17171B"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    );
  }
  return null;
}
