export default function Footer() {
  const startYear = 2026; // 프로젝트 시작 연도
  const currentYear = new Date().getFullYear();
  const yearLabel = currentYear > startYear ? `${startYear}-${currentYear}` : `${startYear}`;

  const scrollTo = (id) => (e) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <footer className="site-footer">
      <div className="footer-top">
        <div className="footer-brand">
          <div className="footer-brand-title">
            <span className="navbar-mascot" aria-hidden="true">W</span>
            <span>와바바</span>
          </div>
          <p>
            채팅·화면·음성을 함께 읽어 방송의 진짜 하이라이트만 골라내는
            멀티모달 분석 플랫폼입니다.
          </p>
          <div className="footer-socials">
            <a
              href="https://github.com/ChatHighlightWBB/Capstone_WBB"
              target="_blank"
              rel="noreferrer"
              aria-label="GitHub 저장소"
            >
              {/* 심플한 GitHub 아이콘 (외부 아이콘 폰트 없이 인라인 SVG) */}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.57.1.79-.25.79-.55
                  0-.27-.01-1.16-.02-2.11-3.2.7-3.88-1.36-3.88-1.36-.52-1.34-1.28-1.69-1.28-1.69
                  -1.04-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96
                  .1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09
                  -.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49
                  3.17-1.18 3.17-1.18.64 1.59.24 2.76.12 3.05.74.81 1.18 1.83 1.18 3.09
                  0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.05.78 2.12 0 1.53-.01 2.76-.01 3.14
                  0 .3.21.66.79.55A10.52 10.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
              </svg>
            </a>
          </div>
        </div>

        <div className="footer-col">
          <h4>제품</h4>
          <a href="#features" onClick={scrollTo("features")}>기능</a>
          <a href="#how" onClick={scrollTo("how")}>이용 방법</a>
        </div>

        <div className="footer-col">
          <h4>법적 고지</h4>
          <span className="footer-muted">이용약관 (준비 중)</span>
          <span className="footer-muted">개인정보처리방침 (준비 중)</span>
        </div>

        <div className="footer-col">
          <h4>지원</h4>
          <a
            href="https://github.com/ChatHighlightWBB/Capstone_WBB/issues"
            target="_blank"
            rel="noreferrer"
          >
            문의 / 이슈 등록
          </a>
        </div>
      </div>

      <div className="footer-bottom">
        <span>© {yearLabel} 와바바(WBB). All rights reserved.</span>
        <span className="footer-status">
          <span className="footer-status-dot" />
          베타 운영 중
        </span>
      </div>
    </footer>
  );
}
