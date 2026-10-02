import Mascot from "./Mascot.jsx";

// 홈 화면 "바바 소개" 섹션 (사이드바 '바바 소개'로 이동)
// 프로필 문구나 표정 설명을 바꾸려면 아래 배열만 고치면 됩니다.

const PROFILE = [
  { label: "이름", value: "바바 (와바바의 '바바')" },
  { label: "태어난 곳", value: "어느 방송의 채팅창. 시청자들이 친 말풍선 하나가 바바가 됐어요." },
  { label: "하는 일", value: "몇 시간짜리 방송 채팅을 처음부터 끝까지 읽고, 시청자가 크게 반응한 순간을 찾아와요." },
  { label: "좋아하는 것", value: "끝없이 이어지는 ㅋㅋㅋㅋ, 한꺼번에 쏟아지는 ???" },
  { label: "싫어하는 것", value: "아무도 채팅을 치지 않는 조용한 구간" },
];

const LOOKS = [
  { part: "몸", desc: "채팅 말풍선이에요. 왼쪽 아래 꼬리까지 그대로예요." },
  { part: "몸 색", desc: "빨강·초록·파랑. 유튜브, 치지직, SOOP 어느 방송이든 읽는다는 뜻이에요." },
  { part: "안테나", desc: "끝에 재생 버튼이 달려 있어요. 영상 신호를 받는 안테나예요." },
];

const MOODS = [
  { mood: "happy", name: "기본", desc: "평소의 바바. 홈 화면에서 영상 안내를 해요." },
  { mood: "excited", name: "신남", desc: "채팅이 터진 순간을 찾았을 때. 처음 안내 화면과 재밌는 결과 화면에서 만나요." },
  { mood: "working", name: "일하는 중", desc: "분석하는 동안 땀 흘리며 열심히 일해요. 분석 화면에서 만나요." },
  { mood: "thinking", name: "생각 중", desc: "결과를 어떻게 읽는지 설명하거나, 하이라이트를 못 찾았을 때 나와요." },
  { mood: "oops", name: "당황", desc: "오류가 났을 때. 분석 실패 화면과 오류 대처 방법 페이지에 있어요." },
];

export default function BabaIntro() {
  return (
    <section id="baba" className="baba-section">
      <h2>와바바의 길잡이, 바바</h2>
      <p className="section-sub">하이라이트를 찾는 동안 화면 곳곳에서 바바가 안내해요.</p>

      <div className="baba-card">
        <div className="baba-portrait">
          <Mascot mood="happy" size={168} />
          <span className="baba-name">바바</span>
        </div>

        <dl className="baba-profile">
          {PROFILE.map((p) => (
            <div key={p.label} className="baba-profile-row">
              <dt>{p.label}</dt>
              <dd>{p.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="baba-details">
        <div className="baba-looks">
          <h3>이렇게 생겼어요</h3>
          <ul>
            {LOOKS.map((l) => (
              <li key={l.part}>
                <b>{l.part}</b> {l.desc}
              </li>
            ))}
          </ul>
        </div>

        <div className="baba-moods">
          <h3>바바의 표정</h3>
          <div className="baba-mood-grid">
            {MOODS.map((m) => (
              <figure key={m.mood} className="baba-mood">
                <Mascot mood={m.mood} size={72} />
                <figcaption>
                  <b>{m.name}</b>
                  <span>{m.desc}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
