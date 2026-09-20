import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getInitialTheme, applyTheme } from "../theme.js";
import { getHistory } from "../history.js";

// 어느 페이지에 있든 항상 보이는 전역 메뉴
const GLOBAL_LINKS = [
  { to: "/", label: "🏠 홈" },
  { to: "/settings", label: "⚙️ 설정" },
];

// 홈 화면 안에서만 의미 있는 구간 이동 링크
const HOME_SECTION_LINKS = [
  { id: "recent-history-section", label: "최근 내역" },
  { id: "how", label: "이용 방법" },
  { id: "features", label: "기능" },
];

// 결과(대시보드) 화면 안에서만 의미 있는 구간 이동 링크
const RESULT_SECTION_LINKS = [
  { id: "score-section", label: "와바바 스코어" },
  { id: "video-section", label: "요약 영상" },
  { id: "download-section", label: "다운로드" },
  { id: "chart-section", label: "감정 그래프" },
  { id: "highlight-section", label: "하이라이트" },
];

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const isHome = location.pathname === "/";
  const isResult = location.pathname.startsWith("/result/");
  const [theme, setTheme] = useState(getInitialTheme());
  const [toast, setToast] = useState(null);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Topbar나 Settings 페이지에서 테마를 바꿔도 이 사이드바 토글의
  // 표시(🌙/☀️)가 같이 바뀌도록 동기화합니다.
  useEffect(() => {
    const sync = () => setTheme(document.documentElement.getAttribute("data-theme") || "light");
    window.addEventListener("wbb-theme-change", sync);
    return () => window.removeEventListener("wbb-theme-change", sync);
  }, []);

  // 토스트는 2.5초 뒤 자동으로 사라집니다.
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(t);
  }, [toast]);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    applyTheme(next);
    window.dispatchEvent(new Event("wbb-theme-change"));
  };

  const handleSectionClick = (id) => (e) => {
    e.preventDefault();

    // [요청 반영] "최근 내역"을 눌렀는데 저장된 내역이 없으면,
    // 조용히 스크롤만 하지 않고 팝업으로 바로 알려줍니다.
    if (id === "recent-history-section" && getHistory().length === 0) {
      setToast("아직 분석한 내역이 없어요.");
    }

    if (isHome || isResult) {
      scrollToId(id);
    } else {
      navigate(`/#${id}`);
    }
  };

  const sectionLinks = isResult ? RESULT_SECTION_LINKS : isHome ? HOME_SECTION_LINKS : [];

  return (
    <aside className="sidebar">
      <Link to="/" className="sidebar-brand">
        <span className="navbar-mascot" aria-hidden="true">W</span>
        <span className="sidebar-word">와바바</span>
      </Link>

      <nav className="sidebar-nav">
        {GLOBAL_LINKS.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={location.pathname === link.to ? "active" : ""}
          >
            {link.label}
          </Link>
        ))}

        {sectionLinks.length > 0 && (
          <>
            <div className="sidebar-divider" />
            {sectionLinks.map((link) => (
              <a key={link.id} href={`#${link.id}`} onClick={handleSectionClick(link.id)}>
                {link.label}
              </a>
            ))}
          </>
        )}
      </nav>

      <div className="sidebar-bottom">
        <Link to="/" className="sidebar-cta">
          {isHome ? "새로 시작하기" : "다시 분석하기"}
        </Link>

        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="라이트/다크 모드 전환"
        >
          {theme === "light" ? "🌙 다크 모드" : "☀️ 라이트 모드"}
        </button>
      </div>

      {toast && <div className="sidebar-toast">{toast}</div>}
    </aside>
  );
}