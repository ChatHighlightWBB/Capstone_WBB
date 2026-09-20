export default function Navbar() {
  const scrollTo = (id) => (e) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  const goToTry = (e) => {
    e.preventDefault();
    document.getElementById("try")?.scrollIntoView({ behavior: "smooth", block: "center" });
    // 스크롤만으론 티가 안 나니, 입력창에 포커스까지 줘서 체감되게 함
    setTimeout(() => document.getElementById("url-input")?.focus(), 400);
  };

  return (
    <header className="navbar">
      <a href="#top" className="navbar-brand" onClick={scrollTo("top")}>
        <span className="navbar-mascot" aria-hidden="true">W</span>
        <span className="navbar-word">와바바</span>
      </a>

      <nav className="navbar-links">
        <a href="#how" onClick={scrollTo("how")}>이용 방법</a>
        <a href="#features" onClick={scrollTo("features")}>기능</a>
        <a href="#try" onClick={goToTry} className="navbar-cta">시작하기</a>
      </nav>
    </header>
  );
}