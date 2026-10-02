import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Mascot from "./Mascot.jsx";

// 페이지를 새로 열 때 보여주는 시작 안내 화면입니다.
// 이 화면의 "시작하기" 클릭이 브라우저가 요구하는 "사용자 첫 클릭"이 되어,
// 그 뒤부터 홈 화면 영상에 마우스를 올리면 바로 소리가 나옵니다.
//
// [하루 동안 보지 않기]
// 체크하고 닫으면 지금부터 24시간 동안 안내 화면이 뜨지 않습니다.
// 이 기간에는 첫 클릭을 받지 못하므로, 페이지 아무 곳이나 한 번 클릭하기
// 전까지는 영상 소리가 나오지 않습니다. (ShortsCarousel이 첫 클릭을 감지해서
// 그 순간 마우스가 올라가 있던 카드의 소리를 켭니다)

const HIDE_KEY = "wbb_welcome_hide_until";
const HIDE_MS = 24 * 60 * 60 * 1000; // 24시간

// 새로고침 없이 페이지를 오갈 때(결과 → 홈) 다시 뜨지 않게 하는 메모리 표시
let dismissedThisPageLoad = false;

function isHiddenByUser() {
  try {
    const until = Number(localStorage.getItem(HIDE_KEY));
    return Number.isFinite(until) && Date.now() < until;
  } catch {
    return false; // localStorage를 못 쓰는 환경이면 그냥 매번 보여줌
  }
}

function hideForOneDay() {
  try {
    localStorage.setItem(HIDE_KEY, String(Date.now() + HIDE_MS));
  } catch {
    // 저장 실패 시 조용히 무시 (다음 새로고침 때 다시 뜰 뿐)
  }
}

export default function WelcomeOverlay() {
  const [open, setOpen] = useState(() => !dismissedThisPageLoad && !isHiddenByUser());
  const [hideToday, setHideToday] = useState(false);

  const close = () => {
    if (hideToday) hideForOneDay();
    dismissedThisPageLoad = true;
    setOpen(false);
  };

  // Enter 키로도 닫을 수 있게 (키 입력도 "첫 사용자 동작"으로 인정됨)
  // Esc는 브라우저가 "첫 사용자 동작"으로 인정하지 않아서(닫아도 소리가 안 남) 뺐고,
  // Space는 체크박스 토글에 쓰이므로 뺐습니다.
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Enter") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, hideToday]);

  if (!open) return null;

  return (
    <div className="welcome-overlay" role="dialog" aria-modal="true" aria-labelledby="welcome-title">
      <div className="welcome-card">
        <Mascot mood="excited" size={88} className="welcome-mascot" />
        <h2 id="welcome-title">와바바에 오신 걸 환영해요</h2>
        <p className="welcome-lead">
          몇 시간짜리 방송에서 터진 순간만 자동으로 골라드려요.
          <br />
          아래 영상에 마우스를 올리면 소리와 함께 미리 볼 수 있어요.
        </p>

        <div className="welcome-block">
          <h3>이렇게 사용해요</h3>
          <ol className="welcome-steps">
            <li>
              <b>영상 파일을 올리세요.</b> 유튜브·치지직·SOOP 링크도 되지만, 파일 업로드가 가장
              안정적이에요.
            </li>
            <li>
              <b>채팅창 위치를 확인하세요.</b> 자동으로 찾아주고, 안 맞으면 미리보기 화면에서 드래그로
              지정할 수 있어요.
            </li>
            <li>
              <b>분석이 끝나면</b> 요약 영상, 감정 그래프, 하이라이트별 클립을 보고 내려받을 수 있어요.
            </li>
          </ol>
        </div>

        <div className="welcome-block">
          <h3>알아두세요</h3>
          <ul className="welcome-notes">
            <li>화면에 <b>채팅창이 보이는 방송 영상</b>이어야 하이라이트를 찾을 수 있어요.</li>
            <li>분석은 영상 길이에 따라 몇 분 걸리고, 한 번에 하나씩 순서대로 처리돼요.</li>
            <li>
              분석 결과는 <b>4시간 뒤 자동 삭제</b>돼요. 필요한 영상은 미리 내려받으세요.
            </li>
            <li>본인이 이용 권한을 가진 영상만 올려 주세요.</li>
            <li>
              문제가 생기면 왼쪽 메뉴 아래의 <b>오류 대처 방법</b>을 확인하세요.
            </li>
          </ul>
        </div>

        <button type="button" className="welcome-start" onClick={close} autoFocus>
          시작하기
        </button>
        <p className="welcome-agree">
          시작하면 <Link to="/terms">이용약관</Link>과{" "}
          <Link to="/privacy">개인정보처리방침</Link>에 동의한 것으로 봅니다.
        </p>
        <label className="welcome-hide">
          <input
            type="checkbox"
            checked={hideToday}
            onChange={(e) => setHideToday(e.target.checked)}
          />
          하루 동안 보지 않기
        </label>
      </div>
    </div>
  );
}
