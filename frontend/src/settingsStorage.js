const CROP_BOX_KEY = "wbb_crop_box"; // { top, left, bottom, right } (0~1 비율) 또는 null
const NOTIFY_KEY = "wbb_notify_on_done";

export function getCropBoxSetting() {
  try {
    const raw = localStorage.getItem(CROP_BOX_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setCropBoxSetting(box) {
  try {
    if (box) {
      localStorage.setItem(CROP_BOX_KEY, JSON.stringify(box));
    } else {
      localStorage.removeItem(CROP_BOX_KEY);
    }
  } catch {
    // 저장 실패해도 조용히 무시 (다음 분석부턴 기본값으로 동작)
  }
}

/** 백엔드가 기대하는 [ymin, xmin, ymax, xmax] 배열로 변환. 설정 없으면 null. */
export function cropBoxToArray() {
  const box = getCropBoxSetting();
  if (!box) return null;
  return [box.top, box.left, box.bottom, box.right];
}

export function getNotifyOnDone() {
  try {
    return localStorage.getItem(NOTIFY_KEY) === "true";
  } catch {
    return false;
  }
}

export function setNotifyOnDone(enabled) {
  try {
    localStorage.setItem(NOTIFY_KEY, enabled ? "true" : "false");
  } catch {
    // 무시
  }
}