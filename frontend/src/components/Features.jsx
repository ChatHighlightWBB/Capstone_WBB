const FEATURES = [
  {
    emoji: "💬",
    title: "플랫폼 무관 채팅 인식",
    desc: "다시보기 채팅은 어느 플랫폼도 API로 안 줍니다. 그래서 화면을 직접 읽어요 — 어떤 방송이든 동일하게 동작해요.",
  },
  {
    emoji: "😄",
    title: "한국어 특화 감정 분석",
    desc: "\"ㅋㅋㅋㅋ\", \"ㅠㅠ\" 같은 스트리밍 특유의 표현까지 정확히 이해하고 7가지 감정으로 분류해요.",
  },
  {
    emoji: "🎯",
    title: "적응형 임계점",
    desc: "게임 방송처럼 텐션 높은 영상과 잔잔한 토크 방송, 기준을 다르게 자동 산출해서 어떤 장르든 균형 잡힌 요약을 만들어요.",
  },
  {
    emoji: "🎤",
    title: "2단계 정밀 검증",
    desc: "시청자 반응으로 넓게 뽑고, 스트리머 목소리만 분리해 실제 발화까지 다시 확인해서 최종 구간을 확정해요.",
  },
  {
    emoji: "📈",
    title: "감정 타임라인 시각화",
    desc: "요약 영상과 함께 시간대별 감정 변화 그래프를 보여줘서, 원하는 분위기의 장면으로 바로 이동할 수 있어요.",
  },
  {
    emoji: "⚡",
    title: "무손실 초고속 클리핑",
    desc: "재인코딩 없이 구간만 잘라 붙이는 방식이라 화질 손실 없이 빠르게 결과물을 받을 수 있어요.",
  },
];

export default function Features() {
  return (
    <section id="features" className="features-section">
      <h2>어떤 기능이 있나요</h2>
      <p className="section-sub">단순히 소리 큰 지점이 아니라, 진짜 맥락을 읽어냅니다.</p>

      <div className="features-grid">
        {FEATURES.map((f) => (
          <div key={f.title} className="feature-card">
            <span className="feature-emoji" aria-hidden="true">{f.emoji}</span>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
