import { useEffect, useState } from "react";
import { extractYoutubeId } from "../youtubeUtils.js";
import BabaSays from "./BabaSays.jsx";

const STEP_LIST = [
  { n: 1, label: "채팅 텍스트 인식 (OCR)" },
  { n: 2, label: "감정 분석 (KoBERT)" },
  { n: 3, label: "1차 하이라이트 후보 탐지" },
  { n: 4, label: "스트리머 발화 정밀 검증 (Whisper)" },
  { n: 5, label: "하이라이트 영상 생성 (FFmpeg)" },
];

// queued/downloading은 파이프라인 5단계에 들어가기 전 단계라 별도로 표시합니다.
const PRE_STEP_LABEL = {
  queued: "분석 대기 중...",
  downloading: "영상 다운로드 중...",
};

// 바바가 단계마다 하는 말 (진행 화면의 말풍선)
const BABA_LINES = {
  queued: "앞 분석이 끝나길 기다리고 있어요. 곧 차례가 와요!",
  downloading: "영상을 내려받고 있어요~",
  1: "영상을 5초마다 넘겨 보면서 채팅을 읽고 있어요~",
  2: "채팅 하나하나에 담긴 감정을 분석하고 있어요~",
  3: "시청자 반응이 몰린 구간을 찾고 있어요~",
  4: "스트리머 목소리만 골라 듣고 있어요~",
  5: "하이라이트 영상을 자르고 붙이고 있어요. 거의 다 왔어요!",
};

function useElapsedSeconds(active) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!active) return;
    const startedAt = Date.now();
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [active]);
  return elapsed;
}

function formatElapsed(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}분 ${s}초` : `${s}초`;
}

export default function AnalyzingProgress({ status, step, totalSteps, stepLabel, previewUrl, sourceUrl }) {
  const isPreStep = status === "queued" || status === "downloading";
  const currentStep = isPreStep ? 0 : (step ?? 0);
  const total = totalSteps ?? 5;

  // Step 진입 직후엔 아직 진행률이 없어 막대가 0%로 보이면 어색하므로,
  // 현재 단계 "시작"만으로도 (n-1)/total 만큼은 채워서 보여줍니다.
  const percent = isPreStep
    ? 5 // 대기/다운로드 중엔 살짝만 채워서 "시작됐다"는 느낌만 줌
    : Math.min(100, Math.round(((currentStep - 1) / total) * 100 + 100 / total * 0.4));

  const elapsed = useElapsedSeconds(true);
  const label = isPreStep ? PRE_STEP_LABEL[status] : (stepLabel || STEP_LIST[currentStep - 1]?.label);
  const youtubeId = sourceUrl ? extractYoutubeId(sourceUrl) : null;
  const babaLine = BABA_LINES[isPreStep ? status : currentStep] ?? "열심히 분석하고 있어요~";

  return (
    <div className="analyzing-screen">
      {/* [추가] 업로드한 파일은 브라우저에 이미 있는 원본을 바로 재생하고,
          유튜브 링크는 임베드 플레이어로 보여줘서 대기 화면을 덜 밋밋하게 합니다.
          치지직/SOOP 링크는 공식 임베드 방법이 마땅치 않아 미리보기를 생략합니다. */}
      {previewUrl && (
        <video className="analyzing-preview-video" src={previewUrl} controls muted />
      )}
      {!previewUrl && youtubeId && (
        <div className="analyzing-preview-embed">
          <iframe
            src={`https://www.youtube.com/embed/${youtubeId}`}
            title="분석 중인 영상"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      )}

      {/* [추가] 치지직/SOOP처럼 임베드가 안 되는 플랫폼도, 최소한 원본으로
          바로 이동할 수 있는 버튼은 항상 보여줍니다. */}
      {sourceUrl && (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noreferrer"
          className="analyzing-source-link"
        >
          🔗 원본 영상 보러가기!
        </a>
      )}

      <div className="analyzing-badge">
        <span className="analyzing-spinner" aria-hidden="true" />
        분석 진행 중
      </div>

      {/* 바바가 땀 흘리며 일하는 모습 + 지금 하는 일 */}
      <BabaSays mood="working" size={96} className="analyzing-baba">
        {babaLine}
        {elapsed >= 180 && (
          <span className="baba-says-sub">긴 영상은 몇 분 더 걸릴 수 있어요. 이 화면을 닫지 말고 기다려 주세요.</span>
        )}
      </BabaSays>

      <h2 className="analyzing-label">{label}</h2>
      <p className="analyzing-elapsed mono">경과 시간 {formatElapsed(elapsed)}</p>

      <div className="progress-bar-track" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div className="progress-bar-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="progress-bar-percent mono">{percent}%</div>

      <ul className="step-checklist">
        {STEP_LIST.map((s) => {
          const state =
            !isPreStep && s.n < currentStep ? "done" :
            !isPreStep && s.n === currentStep ? "active" :
            "pending";
          return (
            <li key={s.n} className={`step-item step-${state}`}>
              <span className="step-icon" aria-hidden="true">
                {state === "done" ? "✓" : state === "active" ? "●" : s.n}
              </span>
              {s.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}