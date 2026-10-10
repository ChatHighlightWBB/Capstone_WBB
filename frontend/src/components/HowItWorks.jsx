import Mascot from "./Mascot.jsx";

// 분석 단계 이름은 분석 진행 화면(AnalyzingProgress)에 뜨는 단계와 같은 순서입니다.
// detail은 칩에 마우스를 올리거나(또는 탭/키보드로 선택하면) 나오는 상세 설명입니다.
const PIPELINE = [
  {
    name: "채팅 읽기",
    tool: "OCR",
    detail:
      "영상을 5초마다 한 장씩 보면서 채팅창 부분만 잘라내고, 방송 채팅 글씨로 따로 학습시킨 PP-OCRv3 모델로 글자를 읽어요. 뭉개져서 알아볼 수 없는 글자는 걸러내요.",
  },
  {
    name: "감정 분석",
    tool: "KoBERT",
    detail:
      "읽어낸 채팅마다 기쁨·당황·분노·슬픔·혐오·공포·중립 7가지 감정이 얼마나 담겼는지 계산해요. 이 값이 결과 화면의 시간대별 감정 그래프가 돼요.",
  },
  {
    name: "후보 구간 찾기",
    tool: "30초 단위",
    detail:
      "30초 구간을 5초씩 옮겨 가며 채팅 반응 점수를 매기고, 이 영상의 반응 정도에 맞춰 자동으로 정한 기준을 넘는 구간을 후보로 골라요. 서로 겹치는 후보는 하나로 합쳐요.",
  },
  {
    name: "스트리머 발화 확인",
    tool: "Whisper",
    detail:
      "후보 구간마다 Demucs로 게임 소리와 배경음을 걷어내 목소리만 남기고, Whisper로 받아 적은 말을 KoBERT로 다시 분석해요. 채팅 점수 70%와 발화 점수 30%를 합쳐 최대 10개를 확정해요.",
  },
  {
    name: "영상 잘라 붙이기",
    tool: "FFmpeg",
    detail:
      "확정된 구간을 다시 인코딩하지 않고 원본에서 그대로 잘라 하이라이트별 클립을 만들고, 이어 붙여 전체 요약 영상을 만들어요.",
  },
];

const STEPS = [
  {
    n: "1",
    title: "영상을 올리거나 링크를 붙여넣어요",
    desc: "영상 파일을 직접 올리는 게 가장 안정적이에요. 유튜브·치지직·SOOP 다시보기 링크도 받을 수 있어요. 화면에 채팅창이 보이는 방송 영상이면 어디서 온 영상이든 괜찮아요.",
  },
  {
    n: "2",
    title: "채팅창 위치를 확인해요",
    desc: "와바바가 화면에서 채팅창을 자동으로 찾아요. 파일을 올렸다면 미리보기 화면에서 채팅창 영역을 드래그해 직접 정해줄 수도 있어요.",
  },
  {
    n: "3",
    title: "다섯 단계로 분석해요",
    desc: "분석 화면에서 지금 몇 번째 단계인지 실시간으로 보여드려요. 영상 길이에 따라 몇 분 정도 걸려요.",
    pipeline: true,
  },
  {
    n: "4",
    title: "결과를 보고 내려받아요",
    desc: "요약 영상과 하이라이트별 클립, 시간대별 감정 그래프가 한 화면에 나와요. 결과는 4시간 동안 보관되니 필요한 영상은 그 안에 내려받으세요.",
  },
];

const GLOSSARY = [
  {
    term: "와바바 스코어",
    desc: "하이라이트 점수의 평균이에요. 80점 이상은 역대급 방송, 60점 이상은 재밌는 방송, 40점 이상은 잔잔한 방송, 그 아래는 차분한 방송으로 표시돼요.",
  },
  {
    term: "⭐ 와바바 포인트",
    desc: "감정 그래프에서 시청자의 기쁨 반응이 가장 높았던 순간이에요. 방송에서 제일 크게 터진 지점을 별로 짚어줘요.",
  },
  {
    term: "하이라이트 점수",
    desc: "채팅 반응 점수 70%와 스트리머 발화의 기쁨 점수 30%를 합친 점수예요. 점수가 높은 순서로 최대 10개를 골라요.",
  },
  {
    term: "카드 왼쪽 색",
    desc: "하이라이트 카드 왼쪽 선의 색은 그 구간에서 스트리머가 말할 때의 감정이에요. 카드를 펼치면 그 구간의 채팅과 감정 변화도 볼 수 있어요.",
  },
];

// <ol>/<li> 대신 div를 씁니다. 브라우저 기본 번호(1. 2. 3.)가 커스텀 숫자
// 배지와 겹쳐 보이는 문제를 막기 위함입니다.
export default function HowItWorks() {
  return (
    <section id="how" className="how-section">
      <h2>이용 방법</h2>
      <p className="section-sub">네 단계면 끝나요. 회원가입도, 편집도 필요 없어요.</p>

      <div className="how-steps">
        {STEPS.map((s) => (
          <div key={s.n} className="how-step">
            <span className="how-step-num">{s.n}</span>
            <div className="how-step-body">
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
              {s.pipeline && (
                <>
                  <ol className="how-pipeline">
                    {PIPELINE.map((p, i) => (
                      <li key={p.name} tabIndex={0} aria-describedby={`pipe-tip-${i}`}>
                        <span className="how-pipeline-name">{p.name}</span>
                        <span className="how-pipeline-tool">{p.tool}</span>
                        <span id={`pipe-tip-${i}`} role="tooltip" className="how-pipeline-tip">
                          {p.detail}
                        </span>
                      </li>
                    ))}
                  </ol>
                  <p className="how-pipeline-hint">각 단계에 마우스를 올리면 자세한 설명이 나와요.</p>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="how-glossary">
        <div className="how-glossary-head">
          <Mascot mood="thinking" size={64} />
          <div>
            <h3>결과 화면은 이렇게 읽어요</h3>
            <p>분석이 끝나면 나오는 숫자와 표시들이에요.</p>
          </div>
        </div>
        <dl className="how-glossary-list">
          {GLOSSARY.map((g) => (
            <div key={g.term} className="how-glossary-item">
              <dt>{g.term}</dt>
              <dd>{g.desc}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
