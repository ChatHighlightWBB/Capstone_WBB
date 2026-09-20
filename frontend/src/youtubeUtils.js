// youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID 등 다양한 형태를 지원합니다.
export function extractYoutubeId(url) {
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtu.be")) return u.pathname.slice(1);
    if (u.pathname.startsWith("/shorts/")) return u.pathname.split("/")[2];
    return u.searchParams.get("v");
  } catch {
    return null;
  }
}