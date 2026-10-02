import { cropBoxToArray } from "./settingsStorage.js";

// 배포(Vercel) 환경에서는 VITE_API_BASE 환경변수로 백엔드(Colab ngrok 등) 주소를 지정합니다.
// 로컬 개발 중에는 비워두면 vite.config.js의 프록시가 처리해줍니다.
const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function startAnalysis(videoUrl) {
  const cropBox = cropBoxToArray(); // 설정 페이지에서 수동으로 지정했으면 실어 보냄
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_url: videoUrl, ...(cropBox ? { crop_box: cropBox } : {}) }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `분석 요청 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

export async function startAnalysisFromFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const cropBox = cropBoxToArray();
  if (cropBox) formData.append("crop_box", cropBox.join(","));

  const res = await fetch(`${API_BASE}/api/v1/analyze-upload`, { method: "POST", body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `업로드 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getResult(videoId) {
  const res = await fetch(`${API_BASE}/api/v1/result/${videoId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `결과 조회 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

/** 설정 페이지에서 보관 기간(RETENTION_HOURS) 등 서버 정보를 보여줄 때 씁니다. */
export async function getServerInfo() {
  const res = await fetch(`${API_BASE}/`);
  if (!res.ok) throw new Error(`서버 정보 조회 실패 (HTTP ${res.status})`);
  return res.json();
}

export function pollResult(videoId, { intervalMs = 3000, onUpdate }) {
  let stopped = false;
  const tick = async () => {
    if (stopped) return;
    try {
      const data = await getResult(videoId);
      onUpdate(data);
      if (data.video_info.status === "done" || data.video_info.status === "failed") return;
    } catch (e) {
      onUpdate(null, e);
      return;
    }
    setTimeout(tick, intervalMs);
  };
  tick();
  return () => { stopped = true; };
}