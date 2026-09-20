// 파이프라인이 실제로 사용하는 7대 감정 라벨과 1:1로 대응하는 색상 맵.
// 차트, 히어로 스크러버, 하이라이트 카드 테두리 등 어디서나 이 맵 하나만 사용합니다.
export const EMOTION_COLORS = {
  기쁨: "#FF8A3D",
  분노: "#E5484D",
  당황: "#8C6FFF",
  불안: "#4C9AFF",
  슬픔: "#5B8DB8",
  혐오: "#4FAE7A",
  중립: "#6B6478",
};

export const EMOTION_FIELD_COLORS = {
  joy_pct: EMOTION_COLORS["기쁨"],
  anger_pct: EMOTION_COLORS["분노"],
  embarrass_pct: EMOTION_COLORS["당황"],
  anxiety_pct: EMOTION_COLORS["불안"],
  sadness_pct: EMOTION_COLORS["슬픔"],
  hurt_pct: EMOTION_COLORS["혐오"],
  neutral_pct: EMOTION_COLORS["중립"],
};

export function colorForEmotion(label) {
  return EMOTION_COLORS[label] || EMOTION_COLORS["중립"];
}
