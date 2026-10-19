// 파이프라인이 실제로 사용하는 7대 감정 라벨과 1:1로 대응하는 색상 맵.
// 차트, 히어로 스크러버, 하이라이트 카드 테두리 등 어디서나 이 맵 하나만 사용합니다.
export const EMOTION_COLORS = {
  기쁨: "#FF8A3D",
  분노: "#E5484D",
  당황: "#8C6FFF",
  공포: "#4C9AFF",
  슬픔: "#5B8DB8",
  혐오: "#4FAE7A",
  평상: "#6B6478",
};

export const EMOTION_FIELD_COLORS = {
  joy_pct: EMOTION_COLORS["기쁨"],
  embarrass_pct: EMOTION_COLORS["당황"],
  anger_pct: EMOTION_COLORS["분노"],
  sadness_pct: EMOTION_COLORS["슬픔"],
  disgust_pct: EMOTION_COLORS["혐오"],
  fear_pct: EMOTION_COLORS["공포"],
  neutral_pct: EMOTION_COLORS["평상"],
};

export function colorForEmotion(label) {
  return EMOTION_COLORS[label] || EMOTION_COLORS["평상"];
}

// 예전에 저장된 분석 결과에는 감정 이름이 "중립"으로 들어 있어서, 화면에는 "평상"으로 바꿔 보여줌
export function displayEmotion(label) {
  return label === "중립" ? "평상" : label;
}
