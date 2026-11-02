// 로그인 없이 "내가 분석한 것" 을 구분하기 위해 브라우저 localStorage를 씁니다.
// 서버는 누가 요청했는지 전혀 모르고, 이 목록은 순전히 이 브라우저에만 남습니다.

const STORAGE_KEY = "wbb_history";
// 시간으로 지우는 RETENTION_MS(4시간 고정)를 없앴습니다. 서버 보관 기간(RETENTION_HOURS)을 늘려도
// 목록만 4시간 뒤 사라지는 문제가 있어서, 지우는 기준을 "서버에 결과가 없을 때(404)" 하나로 통일했습니다.
// 404 확인과 삭제는 RecentHistory.jsx 의 checkAll 이 removeFromHistory 로 처리합니다.

function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeAll(items) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // localStorage를 못 쓰는 환경(프라이빗 모드 등)이면 조용히 무시
  }
}

/** 분석을 시작한 직후 호출 — video_id를 "내 내역"에 추가합니다. */
export function addToHistory({ videoId, label }) {
  const items = readAll(); // 시간 만료로 거르던 pruneExpired 를 없애서, 저장된 목록을 그대로 씀
  items.unshift({
    videoId,
    label: label || videoId,
    createdAt: Date.now(),
  });
  writeAll(items.slice(0, 30)); // 최대 30개만 보관
}

/** 내 분석 내역을 최신순으로 반환 (서버에서 지워진 항목은 removeFromHistory 로 따로 정리) */
export function getHistory() {
  // 시간이 지났다고 숨기거나 지우지 않음. 걸러서 다시 저장하던 writeAll 도 필요 없어져서 뺌
  return readAll();
}

/** 서버에서 이미 지워진(404) 항목을 목록에서 제거 */
export function removeFromHistory(videoId) {
  const items = readAll().filter((item) => item.videoId !== videoId);
  writeAll(items);
}