// 사용자가 고른 로컬 영상 파일(File)에서 한 장면을 이미지(Blob)로 뽑습니다.
// 업로드 화면에서 채팅창 위치를 드래그로 지정할 때 미리보기로 씁니다.
// 원본 해상도 그대로 그려서, 이 이미지 기준 비율값이 서버가 분석하는 프레임과 일치합니다.

const LOAD_TIMEOUT_MS = 15000;

/**
 * @param {File} file
 * @param {(duration: number) => number} pickTime 영상 길이(초)를 받아 뽑을 시점(초)을 돌려주는 함수
 * @returns {Promise<{ blob: Blob, time: number }>}
 */
export function captureVideoFrame(file, pickTime = (duration) => duration * 0.1) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    let done = false;

    const finish = (error, result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(url);
      if (error) reject(error);
      else resolve(result);
    };

    // 코덱을 못 읽는데 onerror도 안 오는 브라우저가 있어서, 일정 시간 지나면 실패로 처리
    const timer = setTimeout(
      () => finish(new Error("영상 장면을 불러오는 데 시간이 너무 오래 걸려요.")),
      LOAD_TIMEOUT_MS
    );

    video.muted = true;
    video.playsInline = true; // iOS Safari에서 전체화면 재생으로 넘어가지 않게
    video.preload = "auto";

    video.onerror = () => finish(new Error("이 브라우저에서 열 수 없는 영상 형식이에요."));

    video.onloadedmetadata = () => {
      if (!video.videoWidth || !video.videoHeight) {
        finish(new Error("영상 트랙을 찾을 수 없어요."));
        return;
      }
      const duration = Number.isFinite(video.duration) ? video.duration : 0;
      // 0초로 두면 currentTime이 안 바뀌어서 seeked가 오지 않으므로 최소 0.1초
      const t = Math.min(Math.max(pickTime(duration), 0.1), Math.max(duration - 0.1, 0.1));
      video.currentTime = t;
    };

    video.onseeked = () => {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
      const time = video.currentTime;
      canvas.toBlob(
        (blob) =>
          blob
            ? finish(null, { blob, time })
            : finish(new Error("장면 이미지를 만들지 못했어요.")),
        "image/jpeg",
        0.85
      );
    };

    video.src = url;
  });
}
