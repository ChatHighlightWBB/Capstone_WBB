import { cropBoxToArray } from "./settingsStorage.js";

// 배포(Vercel) 환경에서는 VITE_API_BASE 환경변수로 백엔드(Colab ngrok 등) 주소를 지정합니다.
// 로컬 개발 중에는 비워두면 vite.config.js의 프록시가 처리해줍니다.
const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function startAnalysis(videoUrl) {
  // 유튜브 링크는 항상 서버 자동 탐지(Auto-ROI)를 쓴다. 저장된 수동 좌표는 업로드 화면에서만 쓴다.
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_url: videoUrl }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `분석 요청 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

/**
 * cropBoxOverride: 업로드 화면에서 이번 분석에만 쓸 [ymin, xmin, ymax, xmax].
 * 넘기지 않으면(undefined) 설정 페이지에 저장된 값을, null이면 crop_box 없이(Auto-ROI) 보냅니다.
 */
export async function startAnalysisFromFile(file, cropBoxOverride) {
  const formData = new FormData();
  formData.append("file", file);
  const cropBox = cropBoxOverride === undefined ? cropBoxToArray() : cropBoxOverride;
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

/**
 * 대기 중이거나 진행 중인 분석을 멈춥니다. 서버는 바로 응답하지만(status: "cancelling"),
 * 실제로 멈춰서 상태가 "cancelled" 가 되기까지는 몇 초~몇 분 걸릴 수 있어 폴링으로 확인합니다.
 */
export async function cancelAnalysis(videoId) {
  const res = await fetch(`${API_BASE}/api/v1/cancel/${videoId}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `분석 멈추기 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

/** 설정 페이지에서 보관 기간(RETENTION_HOURS) 등 서버 정보를 보여줄 때 씁니다. */
export async function getServerInfo() {
  const res = await fetch(`${API_BASE}/api/v1/info`);
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
      // 끝난 상태(완료·실패·사용자가 멈춤)면 더 묻지 않습니다.
      const status = data.video_info.status;
      if (status === "done" || status === "failed" || status === "cancelled") return;
    } catch (e) {
      onUpdate(null, e);
      return;
    }
    setTimeout(tick, intervalMs);
  };
  tick();
  return () => { stopped = true; };
}