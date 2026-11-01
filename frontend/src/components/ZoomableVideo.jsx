import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Maximize2, X } from "lucide-react";

// 결과 화면 영상: 화면을 누르면 큰 창으로 확대해서 보던 위치부터 이어 봅니다.
// 영상이 기울어진 영역(transform) 안에 있어서 CSS 만으로는 화면 전체를 덮을 수 없으므로,
// 확대 창은 body 아래에 따로 띄우고 닫을 때 재생 위치만 원래 영상에 돌려줍니다.

// 재생 막대 높이. 이 영역을 누른 것은 재생·탐색 조작이라 확대하지 않습니다.
const CONTROLS_HEIGHT = 56;

function VideoLightbox({ src, title, startTime, onClose }) {
  const videoRef = useRef(null);
  const close = () => onClose(videoRef.current?.currentTime ?? startTime);

  const handleLoadedMetadata = (e) => {
    const video = e.currentTarget;
    video.currentTime = startTime;
    video.play().catch(() => {});
  };

  // 확대 창이 떠 있는 동안 뒤 페이지 스크롤을 막고, Esc 로 닫을 수 있게 합니다.
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === "Escape") close();
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  });

  return createPortal(
    <div className="rp-lightbox" role="dialog" aria-modal="true" aria-label={title} onClick={close}>
      <button type="button" className="rp-lightbox-close" onClick={close} aria-label="닫기" autoFocus>
        <X size={24} strokeWidth={2.4} />
      </button>
      <video
        ref={videoRef}
        src={src}
        controls
        playsInline
        onLoadedMetadata={handleLoadedMetadata}
        onClick={(e) => e.stopPropagation()}
      />
    </div>,
    document.body
  );
}

// videoRef 를 넘기면 바깥에서도 영상을 다룰 수 있습니다 (하이라이트 카드의 그래프·채팅 연동).
// 나머지 props 는 <video> 에 그대로 전달합니다.
export default function ZoomableVideo({ videoRef, src, title, ...videoProps }) {
  const innerRef = useRef(null);
  const ref = videoRef ?? innerRef;
  const [zoomStart, setZoomStart] = useState(null); // 확대를 시작한 재생 위치 (null 이면 닫힘)

  const openZoom = () => {
    const video = ref.current;
    video.pause();
    setZoomStart(video.currentTime);
  };

  const handleClick = (e) => {
    if (e.clientY > e.currentTarget.getBoundingClientRect().bottom - CONTROLS_HEIGHT) return;
    e.preventDefault(); // 브라우저 기본 동작(재생/일시정지 전환) 대신 확대
    openZoom();
  };

  const closeZoom = (time) => {
    if (ref.current) ref.current.currentTime = time;
    setZoomStart(null);
  };

  return (
    <div className="rp-zoomable">
      <video ref={ref} src={src} controls playsInline onClick={handleClick} {...videoProps} />
      <button type="button" className="rp-zoomable-btn" onClick={openZoom} aria-label={`${title} 크게 보기`}>
        <Maximize2 size={15} strokeWidth={2.4} /> 크게 보기
      </button>
      {zoomStart != null && <VideoLightbox src={src} title={title} startTime={zoomStart} onClose={closeZoom} />}
    </div>
  );
}
