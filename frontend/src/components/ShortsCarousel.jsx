const PLACEHOLDER_SHORTS = [
  { duration: "0:47", tag: "게임 방송" },
  { duration: "1:12", tag: "토크 방송" },
  { duration: "0:35", tag: "공포 게임" },
  { duration: "0:58", tag: "버라이어티" },
  { duration: "1:03", tag: "합방" },
];

// 실제 채널/썸네일 없이, 그라데이션 카드로 "쇼츠가 흘러가는 느낌"만 재현합니다.
export default function ShortsCarousel() {
  const loopItems = [...PLACEHOLDER_SHORTS, ...PLACEHOLDER_SHORTS];

  return (
    <div className="shorts-carousel" aria-hidden="true">
      <div className="shorts-track">
        {loopItems.map((item, i) => (
          <div key={i} className={`shorts-card shorts-card-${i % PLACEHOLDER_SHORTS.length}`}>
            <span className="shorts-duration">{item.duration}</span>
            <span className="shorts-tag">{item.tag}</span>
          </div>
        ))}
      </div>
    </div>
  );
}