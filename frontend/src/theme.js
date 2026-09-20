const STORAGE_KEY = "wbb_theme";

export function getInitialTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // localStorage 접근 불가 시 무시
  }
  // 저장된 값이 없으면 시스템 설정을 따릅니다.
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // 저장 실패해도 화면 전환 자체는 계속 동작하게 둡니다.
  }
}