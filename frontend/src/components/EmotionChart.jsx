import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
  ReferenceLine,
} from "recharts";
import { EMOTION_FIELD_COLORS } from "../emotionColors.js";

// backend가 반환하는 emotion_timeseries.time_series_data 를 그대로 입력받습니다.
// 필드: timestamp, joy_pct, embarrass_pct, anger_pct, anxiety_pct, hurt_pct, sadness_pct, neutral_pct
// 색상은 emotionColors.js 하나로 통일 — 하이라이트 카드 테두리, 히어로 스크러버와 동일한 팔레트입니다.
const EMOTION_LINES = [
  { key: "joy_pct", label: "기쁨" },
  { key: "anger_pct", label: "분노" },
  { key: "embarrass_pct", label: "당황" },
  { key: "sadness_pct", label: "슬픔" },
  { key: "fear_pct", label: "공포" },
];

// [버그 수정] timestamp는 프레임 계산 과정에서 생긴 부동소수점 오차가
// 섞여있어(예: 114.34999999999999), 그대로 분:초로 나누면
// "1:54.349999999999994" 같은 지저분한 값이 그대로 노출됩니다.
// 먼저 정수 초로 반올림한 뒤에 분:초를 계산합니다.
function formatMinSec(rawSec) {
  const sec = Math.round(rawSec);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// [영상 연동] 하이라이트 카드에서만 넘기는 props (없으면 예전과 똑같이 그립니다)
//   curSec    : 클립의 지금 재생 위치를 원본 방송 기준 초로 바꾼 값 → 세로선으로 표시
//   onSeek    : 그래프를 누른 지점(원본 초)으로 클립을 옮기는 함수
//   toClipSec : 원본 초 → 클립 안의 초 (툴팁에 "영상 m:ss" 를 같이 보여 주려고)
//   range     : [구간 시작, 구간 끝] 원본 초. x 축을 이 범위의 숫자 축으로 고정합니다.
export default function EmotionChart({
  timeSeriesData,
  recommendedJoyThreshold,
  compact = false,
  curSec,
  onSeek,
  toClipSec,
  range,
}) {
  const [showHelp, setShowHelp] = useState(false);
  if (!timeSeriesData || timeSeriesData.length === 0) return null;

  // onSeek 가 있을 때만 연동 모드. 기본 x 축(category)은 데이터에 있는 값에만 선을 그을 수 있어서,
  // 재생 위치(소수 초)를 그대로 따라가도록 숫자 축으로 바꿉니다.
  const sync = typeof onSeek === "function";

  // ["와바바 포인트"] 채팅 반응(기쁨 지수)이 가장 높았던 지점을 찾아
  // 그래프 위에 별 마커로 표시합니다. 사용자가 "가장 뜨거웠던 순간"을
  // 그래프만 보고도 바로 짚을 수 있게 하기 위함입니다.
  let peakPoint = null;
  if (!compact) {
    peakPoint = timeSeriesData.reduce(
      (best, cur) => (cur.joy_pct > (best?.joy_pct ?? -Infinity) ? cur : best),
      null
    );
  }

  return (
    <div className="emotion-chart">
      {!compact && (
        <div className="chart-header">
          <h3>시간대별 감정 변화</h3>
          <button
            type="button"
            className="chart-help-icon"
            onMouseEnter={() => setShowHelp(true)}
            onMouseLeave={() => setShowHelp(false)}
            onClick={() => setShowHelp((v) => !v)}
            aria-label="그래프 설명 보기"
          >
            ⓘ
            {showHelp && (
              <span className="chart-help-tooltip">
                채팅에서 인식한 시청자 반응을 기쁨·분노·당황·슬픔·공포 5가지로
                나눠 시간대별 비율(%)로 보여줘요. ⭐ 표시는 채팅 반응이
                가장 뜨거웠던 "와바바 포인트"예요.
              </span>
            )}
          </button>
        </div>
      )}
      {!compact && recommendedJoyThreshold != null && (
        <p className="chart-subtitle">
          자동 산출 임계점 <span className="mono">{recommendedJoyThreshold.toFixed(2)}%</span>
        </p>
      )}
      <ResponsiveContainer width="100%" height={compact ? 160 : 320}>
        <LineChart
          data={timeSeriesData}
          margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
          // 누른 지점에서 가장 가까운 데이터의 timestamp(원본 초)가 activeLabel 로 옵니다.
          // recharts 가 그래프 바깥 div 에 cursor: default 를 직접 넣어서, 손가락 커서는 style 로 덮어씁니다.
          onClick={sync ? (state) => state?.activeLabel != null && onSeek(state.activeLabel) : undefined}
          style={sync ? { cursor: "pointer" } : undefined}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatMinSec}
            hide={compact}
            {...(sync ? { type: "number", domain: range ?? ["dataMin", "dataMax"] } : {})}
          />
          <YAxis unit="%" hide={compact} width={compact ? 0 : undefined} />
          <Tooltip
            labelFormatter={(sec) =>
              sync && toClipSec
                ? `${formatMinSec(sec)} 지점 · 영상 ${formatMinSec(toClipSec(sec))}`
                : `${formatMinSec(sec)} 지점`
            }
            formatter={(value) => `${value}%`}
          />
          {!compact && <Legend />}
          {EMOTION_LINES.map((line) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.label}
              stroke={EMOTION_FIELD_COLORS[line.key]}
              dot={false}
              strokeWidth={compact ? 1.5 : 2}
            />
          ))}
          {/* 클립의 지금 재생 위치. 구간 밖(클립 앞쪽 여분 등)이면 recharts 가 그리지 않습니다. */}
          {sync && curSec != null && (
            <ReferenceLine x={curSec} stroke="#FF6A5C" strokeWidth={2} />
          )}
          {peakPoint && (
            <ReferenceDot
              x={peakPoint.timestamp}
              y={peakPoint.joy_pct}
              r={9}
              fill="#FFD166"
              stroke="#fff"
              strokeWidth={2}
              className="wbb-point-marker"
              label={{
                value: "⭐ 와바바 포인트",
                position: "top",
                fill: "#B8860B",
                fontSize: 12,
                fontWeight: 700,
              }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}