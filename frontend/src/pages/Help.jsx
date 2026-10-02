import { useEffect } from "react";
import { Link } from "react-router-dom";
import Sidebar from "../components/Sidebar.jsx";
import Topbar from "../components/Topbar.jsx";
import Footer from "../components/Footer.jsx";
import Mascot from "../components/Mascot.jsx";

// 오류 대처 방법 페이지 (/help)
// "화면에 보이는 문구" 기준으로 정리했습니다. 문구는 실제 서버(server.py)와
// 결과 화면(Result.jsx)이 보여주는 메시지와 맞춰 두었으니, 그쪽 문구를 바꾸면
// 여기도 같이 바꿔 주세요.

const ISSUES = [
  {
    group: "분석을 시작할 때",
    items: [
      {
        symptom: "\"분석 요청 실패\", \"업로드 실패\", \"Failed to fetch\" 또는 아무 반응이 없어요",
        cause: "분석 서버가 꺼져 있거나 아직 준비 중이에요.",
        fix: [
          "1~2분 뒤 페이지를 새로고침하고 다시 시도하세요. 서버를 처음 켜면 AI 모델을 불러오는 데 시간이 걸려요.",
          "계속되면 서버 담당자(시연자)에게 알려 주세요.",
        ],
      },
      {
        symptom: "\"지원하지 않는 영상 플랫폼 URL입니다\"",
        cause: "링크 분석은 유튜브·치지직·SOOP 주소만 받을 수 있어요.",
        fix: [
          "다른 곳의 영상은 영상 파일을 내려받은 뒤 '영상 파일 직접 업로드'로 올려 주세요. 파일 업로드는 플랫폼과 관계없이 분석돼요.",
        ],
      },
      {
        symptom: "링크로 분석했는데 \"스트림 다운로드 실패 … 파일 업로드를 이용해주세요\"",
        cause: "플랫폼의 보안 정책 때문에 서버가 영상을 내려받지 못했어요. 자주 생기는 일이에요.",
        fix: ["영상 파일을 직접 업로드해 주세요. 가장 안정적인 방법이에요."],
      },
      {
        symptom: "\"AI 파이프라인이 로드되지 않았습니다\"",
        cause: "서버가 AI 모델 파일을 불러오지 못했어요.",
        fix: ["서버 담당자에게 알려 주세요. (모델 폴더 위치 확인 후 서버 재시작 필요)"],
      },
      {
        symptom: "업로드한 영상의 미리보기 화면이 안 떠요",
        cause: "브라우저가 읽지 못하는 영상 형식이에요.",
        fix: [
          "mp4(H.264) 형식으로 변환해서 올리면 미리보기와 채팅창 위치 지정을 쓸 수 있어요.",
          "미리보기 없이 그대로 분석을 시작해도 채팅창 위치는 자동으로 찾아요.",
        ],
      },
    ],
  },
  {
    group: "분석이 진행되는 중에",
    items: [
      {
        symptom: "'분석 대기 중...'에서 넘어가지 않아요",
        cause: "분석은 한 번에 하나씩 처리돼요. 앞선 분석이 진행 중이에요.",
        fix: ["앞 분석이 끝나면 자동으로 시작돼요. 페이지를 닫지 말고 기다려 주세요."],
      },
      {
        symptom: "분석이 너무 오래 걸려요",
        cause: "영상 길이에 비례해서 시간이 걸리고, 그래픽카드가 없는 PC에서는 더 오래 걸려요.",
        fix: [
          "처음에는 1~3분 정도의 짧은 영상으로 시도해 보세요.",
          "진행 단계(1/5 ~ 5/5)가 바뀌고 있다면 정상적으로 분석 중이에요.",
        ],
      },
      {
        symptom: "\"분석 실패 — …\" 문구가 떠요",
        cause: "분석 도중 오류가 났어요. 문구 뒤에 원인이 함께 표시돼요.",
        fix: [
          "왼쪽 메뉴의 '다시 분석하기'로 한 번 더 시도해 보세요.",
          "같은 오류가 반복되면 아래 '그래도 해결되지 않으면'을 참고해 주세요.",
        ],
      },
    ],
  },
  {
    group: "분석 결과를 볼 때",
    items: [
      {
        symptom: "\"채팅을 인식하지 못해 하이라이트를 만들 수 없어요\"",
        cause: "영상에서 채팅창을 찾지 못했거나, 채팅 영역이 잘못 잡혔어요.",
        fix: [
          "화면에 채팅창이 보이는 방송 영상인지 확인하세요.",
          "파일 업로드 후 미리보기 화면에서 채팅창 영역을 직접 드래그로 지정하고 다시 분석하세요.",
          "설정 페이지에서 기본 채팅창 위치를 지정해 둘 수도 있어요.",
        ],
      },
      {
        symptom: "\"반응이 두드러진 구간을 찾지 못해 하이라이트를 만들지 않았어요\"",
        cause: "채팅은 읽었지만 시청자 반응이 크게 몰린 구간이 없었어요.",
        fix: ["채팅 반응이 활발한 구간이 들어간 영상이나, 조금 더 긴 영상으로 시도해 보세요."],
      },
      {
        symptom: "\"존재하지 않는 video_id 입니다\" / 예전 결과가 사라졌어요",
        cause: "분석 결과는 4시간이 지나면 자동으로 삭제돼요.",
        fix: ["같은 영상을 다시 분석해 주세요. 필요한 결과는 4시간 안에 내려받아 두세요."],
      },
      {
        symptom: "하이라이트 구간이 기대와 달라요",
        cause: "AI가 채팅 반응과 스트리머 발화를 기준으로 자동으로 고른 결과라 사람의 판단과 다를 수 있어요.",
        fix: ["감정 그래프와 하이라이트별 개별 클립을 보면서 원하는 구간을 직접 확인해 보세요."],
      },
    ],
  },
  {
    group: "홈 화면",
    items: [
      {
        symptom: "예시 영상에 마우스를 올려도 소리가 안 나요",
        cause: "브라우저는 페이지를 한 번 클릭하기 전까지 소리 재생을 막아요.",
        fix: ["페이지 아무 곳이나 한 번 클릭한 뒤 다시 마우스를 올려 보세요."],
      },
    ],
  },
];

export default function Help() {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <div className="results legal-doc">
          <div className="help-head">
            <Mascot mood="oops" size={72} />
            <div>
              <h1 className="settings-title">오류 대처 방법</h1>
              <p className="legal-meta">
                화면에 뜬 문구와 비슷한 항목을 찾아 순서대로 해 보세요.
              </p>
            </div>
          </div>

          {ISSUES.map((g) => (
            <section key={g.group} className="legal-section">
              <h2 className="help-group">{g.group}</h2>
              {g.items.map((it) => (
                <div key={it.symptom} className="help-item">
                  <h3>{it.symptom}</h3>
                  <p className="help-cause">원인: {it.cause}</p>
                  <ul>
                    {it.fix.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          ))}

          <section className="legal-section">
            <h2 className="help-group">그래도 해결되지 않으면</h2>
            <div className="help-item">
              <p>
                아래 세 가지를 적어서{" "}
                <a
                  href="https://github.com/ChatHighlightWBB/Capstone_WBB/issues"
                  target="_blank"
                  rel="noreferrer"
                >
                  GitHub 이슈
                </a>
                로 남겨 주세요.
              </p>
              <ul>
                <li>결과 페이지 주소의 video_id (예: wbb_20261003_091500)</li>
                <li>화면에 뜬 오류 문구 그대로</li>
                <li>분석한 영상의 길이와 방식 (파일 업로드 / 링크)</li>
              </ul>
            </div>
          </section>

          <p className="legal-meta">
            <Link to="/">← 홈으로 돌아가기</Link>
          </p>
        </div>
        <Footer />
      </main>
    </div>
  );
}
