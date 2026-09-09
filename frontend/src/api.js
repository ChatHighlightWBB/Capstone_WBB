export async function startAnalysis(videoUrl) {
  const res = await fetch("/api/v1/analyze", {
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

export async function startAnalysisFromFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/v1/analyze-upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `업로드 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

export async function getResult(videoId) {
  const res = await fetch(`/api/v1/result/${videoId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `결과 조회 실패 (HTTP ${res.status})`);
  }
  return res.json();
}

export function pollResult(videoId, { intervalMs = 3000, onUpdate }) {
  let stopped = false;

  const tick = async () => {
    if (stopped) return;
    try {
      const data = await getResult(videoId);
      onUpdate(data);
      if (data.video_info.status === "done" || data.video_info.status === "failed") {
        return;
      }
    } catch (e) {
      onUpdate(null, e);
      return;
    }
    setTimeout(tick, intervalMs);
  };

  tick();

  return () => {
    stopped = true;
  };
}