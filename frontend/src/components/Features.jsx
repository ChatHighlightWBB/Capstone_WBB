// 기능 소개. 문구는 실제로 구현된 동작 기준으로 작성했습니다.
// (fact는 각 기능을 뒷받침하는 구체적인 사실 한 줄)
const FEATURES = [
  {
    emoji: "💬",
    title: "어떤 방송이든 채팅을 읽어요",
    desc: "다시보기 채팅은 플랫폼마다 API로 주지 않아요. 그래서 화면에 보이는 채팅창을 직접 읽어요. 채팅창이 보이기만 하면 어느 플랫폼 영상이든 똑같이 동작해요.",
    fact: "방송 채팅 글씨로 따로 학습시킨 OCR, 인식 정확도 95.8%",
  },
  {
    emoji: "😄",
    title: "\"ㅋㅋㅋ\"의 감정까지 알아들어요",
    desc: "\"ㅋㅋㅋㅋ\", \"ㅠㅠ\", 줄임말 같은 방송 채팅 말투로 학습한 한국어 모델이 채팅 하나하나를 기쁨·당황·분노·슬픔·혐오·공포·중립 7가지 감정으로 나눠요.",
    fact: "방송 채팅 1만 5천여 줄로 파인튜닝한 KoBERT",
  },
  {
    emoji: "🎯",
    title: "영상마다 기준이 달라요",
    desc: "늘 시끄러운 게임 방송과 잔잔한 토크 방송을 같은 잣대로 보면 한쪽은 전부 하이라이트, 한쪽은 하나도 없게 돼요. 영상 전체 반응을 먼저 보고 그 영상에 맞는 기준을 자동으로 정해요.",
    fact: "30초 구간을 5초씩 옮겨 가며 반응을 비교",
  },
  {
    emoji: "🎤",
    title: "스트리머 목소리로 한 번 더 확인해요",
    desc: "채팅 반응으로 후보를 넓게 고른 뒤, 게임 소리와 배경음을 걷어내고 스트리머 목소리만 남겨 실제로 무슨 말을 했는지 듣고 최종 구간을 정해요.",
    fact: "Demucs로 목소리 분리, Whisper로 받아쓰기",
  },
  {
    emoji: "⭐",
    title: "가장 터진 순간을 짚어줘요",
    desc: "시간대별 감정 그래프에 시청자 반응이 가장 높았던 와바바 포인트를 별로 표시하고, 방송 전체 분위기를 와바바 스코어 한 숫자로 보여줘요.",
    fact: "역대급, 재밌는, 잔잔한, 차분한 방송까지 4단계",
  },
  {
    emoji: "✂️",
    title: "화질 그대로 바로 잘라요",
    desc: "다시 인코딩하지 않고 원본에서 구간만 잘라 붙여서 화질이 떨어지지 않아요. 전체 요약 영상과 하이라이트별 클립을 따로 내려받을 수 있어요.",
    fact: "FFmpeg 무인코딩 클리핑",
  },
];

export default function Features() {
  return (
    <section id="features" className="features-section">
      <h2>어떤 기능이 있나요</h2>
      <p className="section-sub">소리가 큰 지점이 아니라, 시청자가 진짜 반응한 순간을 찾아요.</p>

      <div className="features-grid">
        {FEATURES.map((f) => (
          <div key={f.title} className="feature-card">
            <span className="feature-emoji" aria-hidden="true">{f.emoji}</span>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
            <p className="feature-fact">{f.fact}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
