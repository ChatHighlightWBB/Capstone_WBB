import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { EMOTION_FIELD_COLORS } from "../emotionColors.js";

// backend가 반환하는 emotion_timeseries.time_series_data 를 그대로 입력받습니다.
// 필드: timestamp, joy_pct, embarrass_pct, anger_pct, anxiety_pct, hurt_pct, sadness_pct, neutral_pct
// 색상은 emotionColors.js 하나로 통일 — 하이라이트 카드 테두리, 히어로 스크러버와 동일한 팔레트입니다.
const EMOTION_LINES = [
  { key: "joy_pct", label: "기쁨" },
  { key: "anger_pct", label: "분노" },
  { key: "embarrass_pct", label: "당황" },
  { key: "anxiety_pct", label: "불안" },
  { key: "sadness_pct", label: "슬픔" },
];

export default function EmotionChart({ timeSeriesData, recommendedJoyThreshold }) {
  if (!timeSeriesData || timeSeriesData.length === 0) return null;

  return (
    <div className="emotion-chart">
      <h3>시간대별 감정 변화</h3>
      {recommendedJoyThreshold != null && (
        <p className="chart-subtitle">
          자동 산출 임계점 <span className="mono">{recommendedJoyThreshold.toFixed(2)}%</span>
        </p>
      )}
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={timeSeriesData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(sec) => `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`}
          />
          <YAxis unit="%" />
          <Tooltip
            labelFormatter={(sec) => `${Math.floor(sec / 60)}분 ${sec % 60}초`}
            formatter={(value) => `${value}%`}
          />
          <Legend />
          {EMOTION_LINES.map((line) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.label}
              stroke={EMOTION_FIELD_COLORS[line.key]}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
