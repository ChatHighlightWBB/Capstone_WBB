const STEPS = [
  {
    n: "01",
    title: "링크를 붙여넣어요",
    desc: "유튜브, 치지직, SOOP TV — 어떤 플랫폼이든 다시보기 링크나 영상 파일 하나면 됩니다.",
  },
  {
    n: "02",
    title: "채팅과 화면을 동시에 읽어요",
    desc: "화면 속 채팅창을 직접 읽고(OCR), 시청자 반응과 화면 변화·음성 에너지를 함께 분석해요.",
  },
  {
    n: "03",
    title: "진짜 재미있는 순간만 골라요",
    desc: "시청자 반응으로 넓게 후보를 뽑고, 스트리머 발화까지 다시 확인해서 최종 구간을 확정해요.",
  },
  {
    n: "04",
    title: "요약 영상과 감정 리포트를 받아요",
    desc: "하이라이트 모음 영상과 함께, 시간대별 감정 변화 그래프도 같이 보여드려요.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how" className="how-section">
      <h2>이용 방법</h2>
      <p className="section-sub">네 단계면 끝나요. 회원가입도, 편집도 필요 없어요.</p>

      <ol className="how-steps">
        {STEPS.map((s) => (
          <li key={s.n} className="how-step">
            <span className="how-step-num">{s.n}</span>
            <div>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
