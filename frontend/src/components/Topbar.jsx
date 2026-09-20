import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { getInitialTheme, applyTheme } from "../theme.js";
import { getServerInfo } from "../api.js";

const PAGE_META = {
  "/": { title: "홈", icon: "🏠" },
  "/settings": { title: "설정", icon: "⚙️" },
};

function getPageMeta(pathname) {
  if (PAGE_META[pathname]) return PAGE_META[pathname];
  if (pathname.startsWith("/result/")) return { title: "분석 결과", icon: "📊" };
  return { title: "와바바", icon: "🌊" };
}

export default function Topbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(getInitialTheme());
  const [serverStatus, setServerStatus] = useState("checking"); // checking | online | offline

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Sidebar의 토글과 상태를 공유하기 위해, 다른 곳에서 테마가 바뀌면
  // (예: Settings 페이지) 이 컴포넌트도 다시 읽어와 아이콘을 맞춥니다.
  useEffect(() => {
    const sync = () => setTheme(document.documentElement.getAttribute("data-theme") || "light");
    window.addEventListener("wbb-theme-change", sync);
    return () => window.removeEventListener("wbb-theme-change", sync);
  }, []);

  // [추가] 그냥 장식이 아니라, 실제로 백엔드(AI 파이프라인)가 응답하는지
  // 주기적으로 확인해서 보여줍니다. 분석 시작하기 전에 서버가 죽어있는지
  // 미리 알 수 있어서 실질적으로 도움이 됩니다.
  useEffect(() => {
    let cancelled = false;
    const check = () => {
      getServerInfo()
        .then((info) => {
          if (!cancelled) setServerStatus(info.ai_pipeline_loaded ? "online" : "offline");
        })
        .catch(() => {
          if (!cancelled) setServerStatus("offline");
        });
    };
    check();
    const id = setInterval(check, 30000); // 30초마다 재확인
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    applyTheme(next);
    window.dispatchEvent(new Event("wbb-theme-change"));
  };

  const meta = getPageMeta(location.pathname);
  const statusText = {
    checking: "서버 확인 중...",
    online: "AI 서버 연결됨",
    offline: "서버 연결 안 됨",
  }[serverStatus];

  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="topbar-icon" aria-hidden="true">{meta.icon}</span>
        <span className="topbar-title">{meta.title}</span>
        <span className={`topbar-status topbar-status-${serverStatus}`} title={statusText}>
          <span className="topbar-status-dot" />
          {statusText}
        </span>
      </div>

      <div className="topbar-right">
        {location.pathname !== "/" && (
          <button
            type="button"
            className="topbar-action-btn"
            onClick={() => navigate("/")}
            title="새 영상 분석 시작"
          >
            + 새 분석
          </button>
        )}
        <button
          type="button"
          className="topbar-theme-btn"
          onClick={toggleTheme}
          aria-label="라이트/다크 모드 전환"
          title="라이트/다크 모드 전환"
        >
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </div>
    </header>
  );
}