import { useRef, useState, useEffect, useCallback } from "react";

// 이미지 위에 드래그로 사각형을 그리면, 그 위치를 이미지 크기 대비
// 0~1 비율(top/left/bottom/right)로 변환해서 onChange로 넘깁니다.
// 좌표를 직접 계산해서 타이핑하는 대신, 화면 보면서 바로 그릴 수 있게 하기 위함입니다.
export default function CropBoxSelector({ imageSrc, initialBox, onChange }) {
  const containerRef = useRef(null);
  const [box, setBox] = useState(null); // {x, y, w, h} — 컨테이너 기준 픽셀
  const [dragStart, setDragStart] = useState(null);

  // 이미지가 바뀌거나 처음 로드될 때, 저장되어 있던 비율값을 픽셀 박스로 환산해 보여줍니다.
  const applyInitialBox = useCallback(() => {
    const el = containerRef.current;
    if (!el || !initialBox) return;
    const { width, height } = el.getBoundingClientRect();
    setBox({
      x: initialBox.left * width,
      y: initialBox.top * height,
      w: (initialBox.right - initialBox.left) * width,
      h: (initialBox.bottom - initialBox.top) * height,
    });
  }, [initialBox]);

  useEffect(() => {
    applyInitialBox();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageSrc]);

  const getRelativePoint = (e) => {
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.min(Math.max(e.clientX - rect.left, 0), rect.width);
    const y = Math.min(Math.max(e.clientY - rect.top, 0), rect.height);
    return { x, y, width: rect.width, height: rect.height };
  };

  const handleMouseDown = (e) => {
    const p = getRelativePoint(e);
    setDragStart(p);
    setBox({ x: p.x, y: p.y, w: 0, h: 0 });
  };

  const handleMouseMove = (e) => {
    if (!dragStart) return;
    const p = getRelativePoint(e);
    const x = Math.min(dragStart.x, p.x);
    const y = Math.min(dragStart.y, p.y);
    const w = Math.abs(p.x - dragStart.x);
    const h = Math.abs(p.y - dragStart.y);
    setBox({ x, y, w, h });
  };

  const finishDrag = () => {
    if (!dragStart || !containerRef.current || !box) {
      setDragStart(null);
      return;
    }
    setDragStart(null);
    if (box.w < 8 || box.h < 8) return; // 너무 작으면(실수 클릭) 무시

    const { width, height } = containerRef.current.getBoundingClientRect();
    const ratios = {
      left: +(box.x / width).toFixed(3),
      top: +(box.y / height).toFixed(3),
      right: +((box.x + box.w) / width).toFixed(3),
      bottom: +((box.y + box.h) / height).toFixed(3),
    };
    onChange(ratios);
  };

  return (
    <div className="cropbox-selector-wrap">
      <div
        ref={containerRef}
        className="cropbox-selector"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={finishDrag}
        onMouseLeave={finishDrag}
      >
        <img src={imageSrc} alt="채팅창 위치 지정용 미리보기" draggable={false} />
        {box && (
          <div
            className="cropbox-selector-rect"
            style={{ left: box.x, top: box.y, width: box.w, height: box.h }}
          />
        )}
      </div>
      <p className="cropbox-selector-hint">
        이미지 위에서 채팅창이 있는 영역을 마우스로 드래그해서 사각형을 그려주세요.
      </p>
    </div>
  );
}