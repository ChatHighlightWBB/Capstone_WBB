import { useEffect, useRef, useState } from "react";

// 홈 화면 예시 영상 6개 (frontend/public/videos/ 폴더에 넣은 짧은 클립)
// 파일 이름이나 태그를 바꾸려면 이 배열만 수정하면 됩니다.
const SAMPLE_SHORTS = [
  { video: "/videos/short1.mp4", tag: "게임 방송" },
  { video: "/videos/short2.mp4", tag: "공포 게임" },
  { video: "/videos/short3.mp4", tag: "게임 방송 2" },
  { video: "/videos/short4.mp4", tag: "버라이어티" },
  { video: "/videos/short5.mp4", tag: "합방" },
  { video: "/videos/short6.mp4", tag: "스포츠 중계" },
];

function formatDuration(sec) {
  if (!Number.isFinite(sec)) return "";
  const s = Math.round(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// 가로(16:9) 영상 6개를 전체 화면 그대로(잘리지 않게) 보여주며 음소거 상태로 동시에 반복 재생하고,
// 마우스를 올린 카드만 소리를 켭니다.
// (소리가 나려면 페이지에서 한 번 클릭이 필요한데, 이건 WelcomeOverlay의
//  "시작하기" 버튼이 대신 받아줍니다.)
export default function ShortsCarousel() {
  const videoRefs = useRef([]);
  const [hoverIndex, setHoverIndex] = useState(null);
  const [durations, setDurations] = useState({});
  // 페이지 첫 클릭/키 입력이 일어났는지 (안내 화면을 "하루 동안 보지 않기"로
  // 건너뛴 경우, 이 첫 클릭 순간에 마우스가 올라가 있던 카드의 소리를 켜기 위함)
  const [activated, setActivated] = useState(false);

  useEffect(() => {
    if (activated) return;
    const onFirstAction = () => setActivated(true);
    window.addEventListener("pointerdown", onFirstAction);
    window.addEventListener("keydown", onFirstAction);
    return () => {
      window.removeEventListener("pointerdown", onFirstAction);
      window.removeEventListener("keydown", onFirstAction);
    };
  }, [activated]);

  // 처음 화면이 뜨면 6개 모두 음소거로 재생 시작
  useEffect(() => {
    videoRefs.current.forEach((v) => {
      if (!v) return;
      v.muted = true;
      v.play().catch(() => {});
    });
  }, []);

  // 마우스를 올린 카드 하나만 소리 켜기, 나머지는 음소거
  useEffect(() => {
    // 아직 페이지에서 클릭이 한 번도 없었으면 소리를 켜지 않음
    // (클릭 전에 소리를 켜면 크롬/엣지가 영상을 멈춰버리기 때문)
    const canPlaySound = navigator.userActivation
      ? navigator.userActivation.hasBeenActive
      : activated;
    videoRefs.current.forEach((v, i) => {
      if (!v) return;
      v.muted = !(canPlaySound && i === hoverIndex);
      if (v.paused) {
        v.play().catch(() => {
          // 브라우저가 소리 재생을 막으면(첫 클릭 전) 음소거로 되돌려 재생만 유지
          v.muted = true;
          v.play().catch(() => {});
        });
      }
    });
  }, [hoverIndex, activated]);

  // 다른 탭으로 넘어가면 6개 모두 일시정지, 돌아오면 다시 재생 (실습실 PC 부담 줄이기)
  useEffect(() => {
    const onVisibility = () => {
      videoRefs.current.forEach((v) => {
        if (!v) return;
        if (document.hidden) v.pause();
        else v.play().catch(() => {});
      });
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  return (
    <div className="shorts-carousel">
      <div className="shorts-track">
        {SAMPLE_SHORTS.map((item, i) => (
          <div
            key={item.video}
            className="shorts-card"
            onMouseEnter={() => setHoverIndex(i)}
            onMouseLeave={() => setHoverIndex((cur) => (cur === i ? null : cur))}
          >
            <video
              ref={(el) => (videoRefs.current[i] = el)}
              className="shorts-video"
              src={item.video}
              muted
              loop
              autoPlay
              playsInline
              preload="auto"
              onLoadedMetadata={(e) => {
                const d = e.currentTarget.duration;
                setDurations((prev) => ({ ...prev, [i]: d }));
              }}
            />
            {durations[i] != null && (
              <span className="shorts-duration">{formatDuration(durations[i])}</span>
            )}
            <span className="shorts-tag">{item.tag}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
