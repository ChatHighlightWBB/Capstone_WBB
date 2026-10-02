import { useEffect } from "react";
import { Link } from "react-router-dom";
import Sidebar from "../components/Sidebar.jsx";
import Topbar from "../components/Topbar.jsx";
import Footer from "../components/Footer.jsx";

// 이용약관 / 개인정보처리방침 페이지 (/terms, /privacy)
// 졸업작품 시연용 서비스 기준으로 작성한 초안입니다.
// 실제 서비스로 공개 운영할 경우에는 법률 검토를 받아 다시 작성해야 합니다.

const EFFECTIVE_DATE = "2026년 10월 3일";

const DOCS = {
  terms: {
    title: "이용약관",
    sections: [
      {
        heading: "제1조 (목적)",
        body: [
          "이 약관은 신한대학교 소프트웨어융합학과 2026 캡스톤디자인 3조가 졸업작품으로 개발한 스트리밍 하이라이트 요약 서비스 '와바바(WBB)'(이하 '서비스')의 이용 조건과 절차를 정합니다.",
        ],
      },
      {
        heading: "제2조 (서비스 내용)",
        body: [
          "서비스는 이용자가 업로드한 영상 파일 또는 입력한 영상 링크를 분석하여 채팅 반응과 스트리머 발화를 기준으로 하이라이트 구간을 찾고, 요약 영상과 감정 분석 결과를 제공합니다.",
          "서비스는 학습 및 졸업작품 시연을 목적으로 운영되며, 상업적 목적으로 제공되지 않습니다.",
        ],
      },
      {
        heading: "제3조 (이용자의 책임)",
        body: [
          "이용자는 본인이 이용 권한을 가진 영상만 업로드하거나 입력해야 합니다.",
          "타인의 저작권, 초상권 등 권리를 침해하는 영상을 이용하여 발생한 문제의 책임은 이용자에게 있습니다.",
          "서비스의 정상적인 운영을 방해하는 행위(과도한 반복 요청, 악성 파일 업로드 등)를 해서는 안 됩니다.",
        ],
      },
      {
        heading: "제4조 (분석 결과의 한계)",
        body: [
          "하이라이트 구간과 감정 분석 결과는 AI 모델(PP-OCRv3, KoBERT, Whisper 등)이 자동으로 산출한 것으로, 정확성이나 완전성을 보장하지 않습니다.",
        ],
      },
      {
        heading: "제5조 (결과물 보관)",
        body: [
          "분석 결과와 하이라이트 영상은 분석 요청 후 4시간이 지나면 자동으로 삭제되며, 삭제된 결과는 복구할 수 없습니다.",
          "필요한 결과물은 보관 기간 안에 직접 다운로드해야 합니다.",
        ],
      },
      {
        heading: "제6조 (서비스 변경 및 중단)",
        body: [
          "서비스는 개발 및 시연 일정에 따라 사전 안내 없이 변경되거나 중단될 수 있습니다.",
        ],
      },
    ],
  },
  privacy: {
    title: "개인정보처리방침",
    sections: [
      {
        heading: "1. 수집하는 정보",
        body: [
          "서비스는 회원가입과 로그인이 없으며, 이름·연락처·이메일 등 개인을 직접 식별하는 정보를 수집하지 않습니다.",
          "분석을 위해 다음 정보를 처리합니다: 업로드한 영상 파일 또는 입력한 영상 링크, 영상에서 인식한 채팅 텍스트와 스트리머 음성 텍스트, 감정 분석 수치, 생성된 하이라이트 영상, 분석 요청 시각.",
          "서버 운영 과정에서 접속 IP 주소 등 접속 기록이 서버 로그에 남을 수 있습니다.",
        ],
      },
      {
        heading: "2. 이용 목적",
        body: [
          "수집한 정보는 하이라이트 분석과 결과 제공에만 사용하며, 다른 목적으로 이용하지 않습니다.",
        ],
      },
      {
        heading: "3. 보관 기간 및 파기",
        body: [
          "업로드한 원본 영상은 분석이 끝나면 즉시 서버에서 삭제됩니다.",
          "분석 결과와 하이라이트 영상은 분석 요청 후 4시간이 지나면 자동으로 삭제됩니다.",
        ],
      },
      {
        heading: "4. 브라우저에 저장되는 정보",
        body: [
          "최근 분석 내역(4시간), 화면 테마, 채팅창 위치 설정, 알림 설정, 시작 안내 숨김 여부가 이용자의 브라우저(localStorage)에만 저장됩니다.",
          "이 정보는 서버로 전송되지 않으며, 브라우저의 사이트 데이터를 삭제하면 함께 지워집니다.",
        ],
      },
      {
        heading: "5. 제3자 제공 및 처리 위탁",
        body: [
          "수집한 정보를 제3자에게 제공하지 않습니다.",
          "분석 결과 저장을 위해 클라우드 데이터베이스 MongoDB Atlas를 이용합니다.",
        ],
      },
      {
        heading: "6. 영상 속 제3자의 정보",
        body: [
          "영상 화면에 표시된 시청자 채팅(닉네임, 채팅 내용)이 분석 과정에서 인식될 수 있습니다. 이 정보는 하이라이트 분석에만 사용되며 4시간 후 결과와 함께 삭제됩니다.",
        ],
      },
      {
        heading: "7. 문의",
        body: [
          "개인정보 관련 문의는 GitHub 저장소의 이슈(ChatHighlightWBB/Capstone_WBB)로 남겨 주세요.",
        ],
      },
    ],
  },
};

export default function Legal({ type }) {
  const doc = DOCS[type] ?? DOCS.terms;
  const otherType = type === "privacy" ? "terms" : "privacy";

  // 푸터(페이지 맨 아래)에서 눌러 들어오므로, 문서는 맨 위부터 보이게
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [type]);

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <div className="results legal-doc">
          <h1 className="settings-title">{doc.title}</h1>
          <p className="legal-meta">시행일: {EFFECTIVE_DATE}</p>

          {doc.sections.map((s) => (
            <section key={s.heading} className="legal-section">
              <h2>{s.heading}</h2>
              {s.body.map((line, i) => (
                <p key={i}>{line}</p>
              ))}
            </section>
          ))}

          <p className="legal-meta">
            <Link to={`/${otherType}`}>{DOCS[otherType].title} 보기 →</Link>
          </p>
        </div>
        <Footer />
      </main>
    </div>
  );
}
