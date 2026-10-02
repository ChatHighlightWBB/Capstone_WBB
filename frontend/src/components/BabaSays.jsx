import Mascot from "./Mascot.jsx";

// 바바가 말풍선으로 한마디 하는 줄. 분석 중 화면과 결과 화면에서 씁니다.
// mood는 Mascot과 같고, children이 말풍선 내용입니다.
export default function BabaSays({ mood = "happy", size = 84, animate = false, className = "", children }) {
  return (
    <div className={`baba-says ${className}`} role="status">
      <Mascot mood={mood} size={size} animate={animate} />
      <div className="baba-says-bubble">{children}</div>
    </div>
  );
}
