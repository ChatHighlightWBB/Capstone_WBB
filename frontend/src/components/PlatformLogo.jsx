import { useState } from "react";

// 지원 플랫폼 로고 (유튜브·치지직·SOOP)
// 각 회사의 상표이므로 "이 플랫폼 영상을 지원한다"는 안내 용도로만, 색·모양을 바꾸지 않고 씁니다.
//
// - 유튜브: Simple Icons(CC0)의 YouTube 아이콘 경로를 그대로 사용
// - 치지직·SOOP: 공개 아이콘 모음에 없어서, 공식 브랜드 자료에서 받은 파일을
//   frontend/public/logos/ 폴더에 chzzk.svg(또는 .png), soop.svg(또는 .png) 이름으로 넣으면 자동으로 표시됩니다.
//   파일이 없으면 이름 글자로만 표시합니다. (로고를 임의로 따라 그리지 않음)

const YOUTUBE_PATH =
  "M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z";

const PLATFORMS = {
  youtube: { name: "YouTube", label: "YouTube" },
  chzzk: { name: "치지직", label: "CHZZK", files: ["/logos/chzzk.svg", "/logos/chzzk.png"] },
  soop: { name: "SOOP", label: "SOOP", files: ["/logos/soop.svg", "/logos/soop.png"] },
};

export default function PlatformLogo({ platform, size = 22, showName = false, className = "" }) {
  const p = PLATFORMS[platform];
  const [fileIndex, setFileIndex] = useState(0);

  if (platform === "youtube") {
    return (
      <span className={`platform-logo platform-youtube ${className}`} title={p.name}>
        <svg viewBox="0 0 24 24" width={size} height={size} role="img" aria-label={p.name}>
          <path d={YOUTUBE_PATH} fill="#FF0000" />
        </svg>
        {showName && <span className="platform-logo-name">{p.label}</span>}
      </span>
    );
  }

  const file = p.files[fileIndex];
  return (
    <span className={`platform-logo platform-${platform} ${className}`} title={p.name}>
      {file ? (
        <img
          src={file}
          alt={p.name}
          height={size}
          style={{ height: size, width: "auto" }}
          onError={() => setFileIndex((i) => i + 1)}
        />
      ) : (
        <span className="platform-logo-text" style={{ fontSize: Math.round(size * 0.62) }}>
          {p.label}
        </span>
      )}
      {showName && file && <span className="platform-logo-name">{p.label}</span>}
    </span>
  );
}

// 세 플랫폼을 나란히 보여주는 줄
export function PlatformRow({ size = 22, showName = true, className = "" }) {
  return (
    <span className={`platform-row ${className}`}>
      <PlatformLogo platform="youtube" size={size} showName={showName} />
      <PlatformLogo platform="chzzk" size={size} showName={showName} />
      <PlatformLogo platform="soop" size={size} showName={showName} />
    </span>
  );
}
