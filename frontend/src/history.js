// 로그인 없이 "내가 분석한 것" 을 구분하기 위해 브라우저 localStorage를 씁니다.
// 서버는 누가 요청했는지 전혀 모르고, 이 목록은 순전히 이 브라우저에만 남습니다.

const STORAGE_KEY = "wbb_history";
const RETENTION_MS = 4 * 60 * 60 * 1000; // 백엔드 RETENTION_HOURS(기본 4시간)와 맞춰주세요

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

// 4시간 지난 항목은 화면에서도 자동으로 안 보이게 걸러냅니다.
// (서버 삭제는 최대 15분 늦게 도니, 여기서도 한 번 더 걸러주는 안전장치)
function pruneExpired(items) {
  const now = Date.now();
  return items.filter((item) => now - item.createdAt < RETENTION_MS);
}

/** 분석을 시작한 직후 호출 — video_id를 "내 내역"에 추가합니다. */
export function addToHistory({ videoId, label }) {
  const items = pruneExpired(readAll());
  items.unshift({
    videoId,
    label: label || videoId,
    createdAt: Date.now(),
  });
  writeAll(items.slice(0, 30)); // 최대 30개만 보관
}

/** 만료되지 않은 내 분석 내역을 최신순으로 반환 */
export function getHistory() {
  const items = pruneExpired(readAll());
  writeAll(items); // 걸러진 결과로 정리
  return items;
}

/** 서버에서 이미 지워진(404) 항목을 목록에서 제거 */
export function removeFromHistory(videoId) {
  const items = readAll().filter((item) => item.videoId !== videoId);
  writeAll(items);
}