import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import Mascot from "../components/Mascot.jsx";
import { Check, Clapperboard, Download, ExternalLink, Flame, Laugh, Leaf, Moon, Star, Tv } from "lucide-react";
import EmotionChart from "../components/EmotionChart.jsx";
import ChatLogWindow from "../components/ChatLogWindow.jsx";
import { computeWbbScore } from "../components/WbbScore.jsx";
import { colorForEmotion } from "../emotionColors.js";
import { extractYoutubeId } from "../youtubeUtils.js";
import { pollResult } from "../api.js";
import { setScene, sfx } from "../sound.js";
import { getNotifyOnDone } from "../settingsStorage.js";
import { TopNav, PipelineDevice, Reveal, SectionHead, StreamScene, STEPS, useScrollProgress } from "./MainPreview.jsx";
import "./MainPreview.css";
import "./ResultPreview.css";

// 분석 중·결과 화면 (메인 페이지와 같은 디자인)
//   /result/:videoId  실제 분석 결과 (서버 응답을 3초마다 받아 옴)
//   /result/demo      서버 없이 보는 예시 — 아래 버튼으로 분석 중 / 결과 / 하이라이트 없음 / 실패를 바꿔 볼 수 있어요.

// ---------------------------------------------------------------------------
// 공통

function formatTime(rawSec) {
  const sec = Math.max(0, Math.round(rawSec));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`;
}

function formatElapsed(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}분 ${s}초` : `${s}초`;
}

// 와바바 스코어 등급 (기존 WbbScore.jsx와 같은 기준)
const GRADES = [
  { from: 0, to: 40, name: "차분한 방송", range: "40점 미만", color: "#3B8BFF", Icon: Moon, mood: "thinking" },
  { from: 40, to: 60, name: "잔잔한 방송", range: "40~59점", color: "#2FD18F", Icon: Leaf, mood: "happy" },
  { from: 60, to: 80, name: "재밌는 방송", range: "60~79점", color: "#FFB020", Icon: Laugh, mood: "excited" },
  { from: 80, to: 101, name: "역대급 방송", range: "80점 이상", color: "#FF6A5C", Icon: Flame, mood: "excited" },
];

function gradeOf(score) {
  return GRADES.find((g) => score >= g.from && score < g.to) ?? GRADES[0];
}

// 결과가 나왔을 때 바바의 한마디 (기존 Result.jsx와 같은 기준)
function babaReaction(count, score) {
  if (score >= 80) return { mood: "excited", text: `역대급 방송이에요! 하이라이트 ${count}개를 찾았어요.` };
  if (score >= 60) return { mood: "excited", text: `재밌는 장면이 많았어요! 하이라이트 ${count}개를 골랐어요.` };
  if (score >= 40) return { mood: "happy", text: `잔잔한 방송이지만 반응이 모인 구간 ${count}개를 찾았어요.` };
  return { mood: "happy", text: `차분한 방송이었어요. 그래도 시청자가 반응한 구간 ${count}개를 골랐어요.` };
}

const EMPTY_HIGHLIGHT_MESSAGE = {
  no_chats:
    "채팅을 인식하지 못해 하이라이트를 만들 수 없어요. 채팅창이 화면에 보이는 영상인지 확인하거나, 파일 업로드에서 채팅 영역을 직접 지정해 다시 시도해 보세요.",
  no_candidates: "채팅은 인식했지만 반응이 두드러진 구간을 찾지 못해 하이라이트를 만들지 않았어요.",
};

// 지금 값에서 목표값까지 부드럽게 움직이는 숫자 (처음엔 0에서 시작)
function useAnimatedNumber(target, duration = 1400) {
  const [value, setValue] = useState(0);
  const valueRef = useRef(0);
  valueRef.current = value;
  useEffect(() => {
    let raf;
    const from = valueRef.current;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      setValue(from + (target - from) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

function useElapsedSeconds() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const startedAt = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  return elapsed;
}

// ---------------------------------------------------------------------------
// 예시 데이터 (/result/demo)

const DEMO_DURATION = 1543; // 25:43
const DEMO_PEAKS = [
  { t: 190, joy: 0.9, fear: 0, emotion: "기쁨", score: 88.4, text: "아니 이게 들어간다고? 와 진짜 말도 안 돼 다시 봐야 돼 이거" },
  { t: 612, joy: 0.45, fear: 0.8, emotion: "공포", score: 81.2, text: "잠깐만 뭐야 저기 뭐 있었어 방금? 나 이거 진짜 못 하겠는데" },
  { t: 905, joy: 0.95, fear: 0, emotion: "기쁨", score: 92.7, text: "됐다 됐다 됐다! 이걸 잡네 이걸 잡아 와 미쳤다 진짜" },
  { t: 1180, joy: 0.55, fear: 0, emotion: "당황", score: 74.9, text: "어? 어어? 이거 내가 누른 거 아닌데 왜 이렇게 됐지" },
  { t: 1420, joy: 0.8, fear: 0, emotion: "기쁨", score: 79.3, text: "오늘 방송 여기까지! 와 마지막에 이렇게 끝나네 다들 고마워요" },
];
const DEMO_CHATS = [
  "ㅋㅋㅋㅋㅋㅋㅋㅋ", "와 미친", "역전 ㅋㅋㅋㅋㅋ", "홀리쉿", "신이다", "뭉서워요 ㄷㄷㄷ", "헐?", "뭔가 온다",
  "무빙 지리네", "와 대단하네;;", "재밌네 ㅋㅋ", "띠용", "캬ㅑㅑㅑ", "가주아 ~~~", "드가자~~~", "진짜루?",
];

function buildDemoResult(kind) {
  const rows = [];
  for (let t = 0; t <= DEMO_DURATION; t += 5) {
    const bump = (c, w) => Math.exp(-((t - c) ** 2) / (2 * w * w));
    let joy = 10 + 5 * Math.sin(t / 37) + 3 * Math.sin(t / 11);
    let fear = 3 + 2 * Math.abs(Math.sin(t / 61));
    let embarrass = 6 + 4 * Math.abs(Math.sin(t / 47));
    DEMO_PEAKS.forEach((p) => {
      joy += p.joy * 95 * bump(p.t, 30);
      fear += p.fear * 60 * bump(p.t, 20);
      embarrass += (p.emotion === "당황" ? 40 : 8) * bump(p.t + 10, 25);
    });
    const anger = 2 + 2 * Math.abs(Math.sin(t / 29));
    const sadness = 2 + 2 * Math.abs(Math.cos(t / 41));
    const r1 = (v) => Math.round(Math.min(100, v) * 10) / 10;
    rows.push({
      timestamp: t,
      joy_pct: r1(joy),
      fear_pct: r1(fear),
      embarrass_pct: r1(embarrass),
      anger_pct: r1(anger),
      sadness_pct: r1(sadness),
      neutral_pct: r1(Math.max(0, 100 - joy - fear - embarrass - anger - sadness)),
      chat_text: DEMO_CHATS[(t / 5) % DEMO_CHATS.length],
    });
  }

  const highlights = DEMO_PEAKS.map((p, i) => ({
    start_time: p.t - 20,
    end_time: p.t + 25,
    duration: 45,
    streamer_speech_text: p.text,
    streamer_speech_emotion: p.emotion,
    final_highlight_score: p.score,
    clip_url: `/videos/short${i + 1}.mp4`,
  }))
    .sort((a, b) => b.final_highlight_score - a.final_highlight_score)
    .map((h, i) => ({ ...h, rank: i + 1 }));

  const timeseries = { time_series_data: rows, recommended_joy_threshold: 45.2 };
  if (kind === "empty") {
    return {
      video_info: { status: "done" },
      emotion_timeseries: timeseries,
      highlight_result: { highlights: [], metadata: { empty_reason: "no_candidates" } },
    };
  }
  if (kind === "failed") {
    return { video_info: { status: "failed", error: "채팅창 영역을 찾지 못했어요 (예시 오류 문구)" } };
  }
  return {
    video_info: { status: "done" },
    final_video_url: "/videos/short1.mp4",
    emotion_timeseries: timeseries,
    highlight_result: { highlights, metadata: {} },
  };
}

// 분석 중 예시: 대기 → 1~5단계를 차례로 보여준 뒤 결과로 넘어감
function useDemoResult(mode, setResult) {
  useEffect(() => {
    if (!mode) return;
    if (mode !== "analyzing") {
      setResult(buildDemoResult(mode));
      return;
    }
    const seq = [
      { status: "queued" },
      { status: "analyzing", step: 1 },
      { status: "analyzing", step: 2 },
      { status: "analyzing", step: 3 },
      { status: "analyzing", step: 4 },
      { status: "analyzing", step: 5 },
    ];
    let i = 0;
    setResult({ video_info: { ...seq[0], total_steps: 5 } });
    const id = setInterval(() => {
      i += 1;
      if (i < seq.length) setResult({ video_info: { ...seq[i], total_steps: 5 } });
      else {
        clearInterval(id);
        setResult(buildDemoResult("done"));
      }
    }, 3200);
    return () => clearInterval(id);
  }, [mode, setResult]);
}

// ---------------------------------------------------------------------------
// 분석 중 화면

const STEP_COPY = {
  queued: { title: "곧 차례가 와요", desc: "앞 분석이 끝나길 기다리고 있어요.", baba: "앞 분석이 끝나길 기다리고 있어요. 곧 차례가 와요!" },
  downloading: { title: "영상을 받는 중", desc: "분석할 영상을 내려받고 있어요.", baba: "영상을 내려받고 있어요~" },
  1: { title: "채팅을 읽고 있어요", baba: "영상을 5초마다 넘겨 보면서 채팅을 읽고 있어요~" },
  2: { title: "감정을 분석하고 있어요", baba: "채팅에 담긴 감정을 분석하고 있어요~" },
  3: { title: "터진 구간을 찾고 있어요", baba: "시청자 반응이 몰린 구간을 찾고 있어요~" },
  4: { title: "목소리를 듣고 있어요", baba: "스트리머 목소리만 골라 듣고 있어요~" },
  5: { title: "영상을 자르고 있어요", baba: "하이라이트 영상을 자르고 붙이고 있어요. 거의 다 왔어요!" },
};

function AnalyzingStage({ status, step, totalSteps, previewUrl, sourceUrl }) {
  const isPre = status === "queued" || status === "downloading";
  const current = isPre ? 0 : step ?? 1;
  const total = totalSteps ?? 5;
  const percent = isPre ? 5 : Math.min(99, Math.round(((current - 1) / total) * 100 + (100 / total) * 0.4));
  const shownPercent = Math.round(useAnimatedNumber(percent, 900));
  const elapsed = useElapsedSeconds();
  const copy = STEP_COPY[isPre ? status : current] ?? STEP_COPY[1];
  const desc = isPre ? copy.desc : STEPS[current - 1]?.desc;
  const youtubeId = sourceUrl ? extractYoutubeId(sourceUrl) : null;
  const stepColor = isPre ? "#3B8BFF" : STEPS[current - 1]?.color;

  // 분석 중에는 분석 배경음악, 단계가 바뀔 때마다 '띠링'
  const lastStepRef = useRef(null);
  useEffect(() => {
    const key = isPre ? status : `step${current}`;
    if (lastStepRef.current === key) return; // 같은 단계에서 반복하지 않게
    lastStepRef.current = key;
    setScene(`analyze-${isPre ? 0 : current}`);
    if (!isPre) sfx("blip");
  }, [isPre, status, current]);

  return (
    <section className="rp-an" style={{ "--step-color": stepColor }}>
      <div className="np-hero-bg rp-an-bg" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>

      <div className="rp-an-head">
        <span className="np-eyebrow rp-an-eyebrow">
          <i className="rp-spinner" aria-hidden="true" /> 분석 진행 중
        </span>
        <h1 key={copy.title}>{copy.title}</h1>
        <p key={desc}>{desc}</p>
      </div>

      <div className="rp-an-progress">
        <div className="rp-an-percent">
          <strong className="mono">{shownPercent}</strong>
          <span>%</span>
          <em className="mono">경과 {formatElapsed(elapsed)}</em>
        </div>
        <div className="rp-an-track" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
          <i style={{ width: `${percent}%` }} />
        </div>
        <ol className="rp-an-steps">
          {STEPS.map((s, i) => {
            const n = i + 1;
            const state = !isPre && n < current ? "done" : !isPre && n === current ? "on" : "";
            return (
              <li key={s.name} className={state ? `is-${state}` : ""} style={{ "--c": s.color }}>
                <span className="rp-an-step-dot">{state === "done" ? <Check size={15} strokeWidth={3} /> : n}</span>
                <span className="rp-an-step-name">{s.name}</span>
                <span className="rp-an-step-tool mono">{s.tool}</span>
              </li>
            );
          })}
        </ol>
        {sourceUrl && (
          <a href={sourceUrl} target="_blank" rel="noreferrer" className="rp-an-source">
            <ExternalLink size={15} strokeWidth={2.2} /> 원본 영상 보러가기
          </a>
        )}
      </div>

      <div className="rp-an-grid">
        <div className="rp-an-left">
          <div className="rp-monitor">
            <div className="rp-monitor-screen">
              {previewUrl ? (
                <video src={previewUrl} muted autoPlay loop playsInline />
              ) : youtubeId ? (
                <iframe
                  src={`https://www.youtube.com/embed/${youtubeId}?autoplay=1&mute=1`}
                  title="분석 중인 영상"
                  allow="autoplay; encrypted-media; picture-in-picture"
                  allowFullScreen
                />
              ) : (
                <StreamScene scene={{ mood: "working", Icon: Tv, word: "분석 중", a: "#3B8BFF", b: "#151a33" }} on />
              )}
              {current === 1 && <div className="rp-monitor-scan" aria-hidden="true" />}
              <span className="rp-monitor-tag">{isPre ? "준비 중" : `STEP ${current}`}</span>
            </div>
          </div>
          <div className="rp-an-baba" role="status">
            <Mascot mood="working" size={76} />
            <div className="rp-an-bubble" key={copy.baba}>
              {copy.baba}
              {elapsed >= 180 && <small>긴 영상은 몇 분 더 걸릴 수 있어요. 이 화면을 닫지 말고 기다려 주세요.</small>}
            </div>
          </div>
        </div>

        <div className="rp-an-right">
          {isPre ? (
            <div className="np-flow-device rp-an-wait">
              <Mascot mood="working" size={110} />
              <span>{status === "queued" ? "대기열에서 기다리는 중" : "영상 내려받는 중"}</span>
              <div className="rp-an-dots">
                <i />
                <i />
                <i />
              </div>
            </div>
          ) : (
            <PipelineDevice step={current - 1} />
          )}
        </div>
      </div>

    </section>
  );
}

// ---------------------------------------------------------------------------
// 결과 화면

function ScoreRing({ score, color }) {
  const v = useAnimatedNumber(score, 1600);
  const r = 78;
  const c = 2 * Math.PI * r;
  return (
    <div className="rp-ring">
      <svg viewBox="0 0 200 200" aria-hidden="true">
        <defs>
          <linearGradient id="rp-ring-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#FF6A5C" />
            <stop offset="55%" stopColor="#2FD18F" />
            <stop offset="100%" stopColor="#3B8BFF" />
          </linearGradient>
        </defs>
        <circle cx="100" cy="100" r={r} className="rp-ring-track" />
        <circle
          cx="100"
          cy="100"
          r={r}
          className="rp-ring-bar"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v / 100)}
        />
      </svg>
      <div className="rp-ring-center">
        <strong>{Math.round(v)}</strong>
        <span style={{ color }}>와바바 스코어</span>
      </div>
    </div>
  );
}

// 점수 기준표: 네 등급 구간 위에 이 방송의 점수 위치를 표시
function ScoreScale({ score }) {
  const v = useAnimatedNumber(score, 1600);
  const current = gradeOf(score);
  return (
    <div className="rp-scale">
      <div className="rp-scale-head">
        <b>와바바 스코어 기준</b>
        <span>하이라이트 구간 채팅의 기쁨 반응을 0~100점으로 종합한 점수예요.</span>
      </div>
      <div className="rp-scale-bar">
        <span className="rp-scale-marker" style={{ left: `${Math.min(100, v)}%`, "--c": current.color }}>
          {Math.round(v)}
        </span>
        {GRADES.map((g) => (
          <div
            key={g.name}
            className={`rp-scale-seg ${g === current ? "is-on" : ""}`}
            style={{ flexGrow: Math.min(100, g.to) - g.from, "--c": g.color }}
          >
            <i />
            <b>
              <g.Icon size={14} strokeWidth={2.4} /> {g.name}
            </b>
            <span>{g.range}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResultHero({ highlights, timeSeries, finalVideoUrl }) {
  const score = Math.round(computeWbbScore(highlights, timeSeries));
  const grade = gradeOf(score);
  const reaction = babaReaction(highlights.length, score);
  const totalSec = highlights.reduce((sum, h) => sum + (h.end_time - h.start_time), 0);
  const peak = timeSeries?.length
    ? timeSeries.reduce((best, cur) => (cur.joy_pct > (best?.joy_pct ?? -Infinity) ? cur : best), null)
    : null;

  // 점수 게이지가 차오르는 1.6초 동안 음계가 올라가고, 다 차면 '짠!'
  const revealedRef = useRef(false);
  useEffect(() => {
    if (revealedRef.current) return;
    revealedRef.current = true;
    setScene("result");
    sfx("rise");
    setTimeout(() => sfx("reveal"), 1650);
  }, []);

  return (
    <section id="score" className="rp-hero">
      <div className="np-hero-bg rp-hero-bg" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="rp-hero-inner">
        <div className="rp-hero-left">
          <ScoreRing score={score} color={grade.color} />
          <span className="rp-grade" style={{ "--c": grade.color }}>
            <Mascot mood={grade.mood} size={30} />
            {grade.name}
          </span>
        </div>
        <div className="rp-hero-right">
          <span className="np-eyebrow">분석 완료</span>
          <div className="rp-hero-baba">
            <Mascot mood={reaction.mood} size={72} animate />
            <p>{reaction.text}</p>
          </div>
          <div className="rp-stats">
            <div>
              <strong>{highlights.length}개</strong>
              <span>하이라이트</span>
            </div>
            <div>
              <strong className="mono">{formatTime(totalSec)}</strong>
              <span>요약 영상 길이</span>
            </div>
            {peak && (
              <div>
                <strong className="mono rp-stat-star">
                  <Star size={20} fill="#FFB020" strokeWidth={0} /> {formatTime(peak.timestamp)}
                </strong>
                <span>가장 크게 터진 순간</span>
              </div>
            )}
          </div>
          <ScoreScale score={score} />
          <div className="rp-hero-actions">
            {finalVideoUrl && (
              <a href={finalVideoUrl} download className="rp-btn rp-btn-primary">
                <Download size={17} strokeWidth={2.4} /> 요약 영상 받기
              </a>
            )}
            <a href="#highlights" className="rp-btn" onClick={(e) => { e.preventDefault(); document.getElementById("highlights")?.scrollIntoView({ behavior: "smooth" }); }}>
              하이라이트 보기
            </a>
          </div>
          <p className="rp-hero-note">결과는 보관 기간이 지나면 자동으로 지워져요. 필요한 영상은 미리 받아 두세요.</p>
        </div>
      </div>
    </section>
  );
}

// 요약 영상: 기울어진 화면이 스크롤에 맞춰 펴지고, 아래에 방송 전체 타임라인
function VideoSection({ finalVideoUrl, highlights, duration, onPick }) {
  const ref = useScrollProgress();
  return (
    <section id="video" ref={ref} className="rp-video">
      <div className="np-sticky rp-video-sticky">
        <div className="rp-video-head">
          <span className="np-eyebrow">요약 영상</span>
          <h2 className="np-section-title">터진 순간만 모아서 한 편으로</h2>
        </div>
        <div className="rp-video-frame">
          <video src={finalVideoUrl} controls playsInline />
        </div>
        <div className="rp-timeline" aria-label="방송 전체에서 하이라이트 위치">
          <div className="rp-timeline-track" />
          {highlights.map((h) => (
            <button
              key={h.rank}
              type="button"
              className="rp-timeline-mark"
              style={{
                left: `${(h.start_time / duration) * 100}%`,
                width: `${Math.max(1.2, ((h.end_time - h.start_time) / duration) * 100)}%`,
                "--c": colorForEmotion(h.streamer_speech_emotion),
              }}
              onClick={() => onPick(h.rank)}
              title={`#${h.rank} ${formatTime(h.start_time)}`}
            >
              <span>#{h.rank}</span>
            </button>
          ))}
          <span className="rp-timeline-end mono">0:00</span>
          <span className="rp-timeline-end rp-timeline-end-r mono">{formatTime(duration)}</span>
        </div>
      </div>
    </section>
  );
}

function ChartSection({ timeSeries, threshold }) {
  return (
    <section id="chart" className="rp-section">
      <SectionHead eyebrow="감정 그래프" title="시간대별 시청자 반응" sub="⭐ 표시가 채팅 반응이 가장 뜨거웠던 와바바 포인트예요." />
      <Reveal className="rp-card rp-chart-card" delay={120}>
        <EmotionChart timeSeriesData={timeSeries} recommendedJoyThreshold={threshold} />
      </Reveal>
    </section>
  );
}

function HighlightItem({ h, timeSeries, open, onToggle, index }) {
  const color = colorForEmotion(h.streamer_speech_emotion);
  const sliced = (timeSeries || []).filter((d) => d.timestamp >= h.start_time && d.timestamp <= h.end_time);

  // [영상·그래프·채팅 연동] 셋을 모두 "원본 방송 기준 초"로 맞춥니다.
  //   원본 시각 = start_time - offset + 클립 재생 위치
  //   offset(클립 앞쪽 여분): -c copy 로 자르면 클립이 start_time 직전 키프레임부터 시작해 길어짐.
  //   늘어난 만큼을 앞쪽 여분으로 봄(근사). 최대 10초로 제한합니다.
  // 상태는 카드마다 따로라서 다른 카드·화면에는 영향이 없습니다.
  const videoRef = useRef(null);
  const [offset, setOffset] = useState(0);
  const [curSec, setCurSec] = useState(null);

  const handleLoadedMetadata = (e) => {
    const video = e.currentTarget;
    // 길이를 아직 모르면(NaN·Infinity) 여분 없이 계산합니다.
    const extra = Number.isFinite(video.duration) ? Math.max(0, Math.min(video.duration - h.duration, 10)) : 0;
    setOffset(extra);
    setCurSec(h.start_time - extra + video.currentTime);
  };

  const handleTimeUpdate = (e) => {
    setCurSec(h.start_time - offset + e.currentTarget.currentTime);
  };

  // 원본 시각 T → 클립 안의 시각 (0 ~ 클립 길이로 자름)
  const toClipSec = (t) => {
    const video = videoRef.current;
    const max = video && Number.isFinite(video.duration) ? video.duration : Infinity;
    return Math.min(Math.max(t - h.start_time + offset, 0), max);
  };

  // 그래프·채팅에서 누른 원본 시각 T 로 클립을 옮깁니다.
  const seekTo = (t) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = toClipSec(t);
    setCurSec(h.start_time - offset + video.currentTime);
  };

  // 클립이 없으면 연동할 영상이 없으니 props 를 넘기지 않아 예전 모습 그대로 둡니다.
  const syncProps = h.clip_url ? { curSec, onSeek: seekTo } : {};

  return (
    <Reveal as="li" id={`hl-${h.rank}`} className={`rp-hl ${open ? "is-open" : ""}`} delay={Math.min(index, 4) * 90} style={{ "--c": color }}>
      <button type="button" className="rp-hl-head" onClick={onToggle} aria-expanded={open}>
        <span className="rp-hl-rank">{String(h.rank).padStart(2, "0")}</span>
        <span className="rp-hl-main">
          <span className="rp-hl-meta">
            <span className="mono">
              {formatTime(h.start_time)} – {formatTime(h.end_time)}
            </span>
            <span className="rp-hl-emotion">{h.streamer_speech_emotion}</span>
          </span>
          <span className="rp-hl-quote">“{h.streamer_speech_text.length > 90 ? h.streamer_speech_text.slice(0, 90) + "…" : h.streamer_speech_text}”</span>
        </span>
        <span className="rp-hl-score">
          <strong className="mono">{h.final_highlight_score.toFixed(1)}</strong>
          <i>
            <b style={{ width: `${Math.min(100, h.final_highlight_score)}%` }} />
          </i>
        </span>
        <span className="rp-hl-chevron" aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div className="rp-hl-body">
          {h.clip_url ? (
            <video
              ref={videoRef}
              className="rp-hl-video"
              src={h.clip_url}
              controls
              playsInline
              onLoadedMetadata={handleLoadedMetadata}
              onTimeUpdate={handleTimeUpdate}
            />
          ) : (
            <div className="rp-hl-empty">이 하이라이트의 개별 클립이 아직 없어요.</div>
          )}
          <div className="rp-hl-panels">
            <div className="rp-hl-panel">
              <h4>이 구간 감정 변화</h4>
              <EmotionChart
                timeSeriesData={sliced}
                compact
                {...syncProps}
                {...(h.clip_url ? { toClipSec, range: [h.start_time, h.end_time] } : {})}
              />
            </div>
            <div className="rp-hl-panel">
              <h4>이 구간 채팅</h4>
              <ChatLogWindow timeSeriesData={timeSeries} startTime={h.start_time} endTime={h.end_time} {...syncProps} />
            </div>
          </div>
          {h.clip_url && (
            <a href={h.clip_url} download className="rp-btn rp-btn-small">
              <Download size={15} strokeWidth={2.4} /> 이 클립 받기
            </a>
          )}
        </div>
      )}
    </Reveal>
  );
}

function HighlightsSection({ highlights, timeSeries, openRank, setOpenRank }) {
  return (
    <section id="highlights" className="rp-section">
      <SectionHead
        eyebrow="하이라이트"
        title={`최종 하이라이트 ${highlights.length}개`}
        sub="카드 왼쪽 색은 그 구간에서 스트리머가 말할 때의 감정이에요. 눌러서 클립과 채팅을 확인하세요."
      />
      <ul className="rp-hl-list">
        {highlights.map((h, i) => (
          <HighlightItem
            key={h.rank}
            h={h}
            index={i}
            timeSeries={timeSeries}
            open={openRank === h.rank}
            onToggle={() => setOpenRank(openRank === h.rank ? null : h.rank)}
          />
        ))}
      </ul>
    </section>
  );
}

function DownloadSection({ finalVideoUrl, highlights }) {
  const clips = highlights.filter((h) => h.clip_url);
  if (!finalVideoUrl && clips.length === 0) return null;
  return (
    <section id="download" className="rp-section rp-section-alt">
      <SectionHead eyebrow="다운로드" title="필요한 영상만 골라 받기" sub="다시 인코딩하지 않아서 원본 화질 그대로예요." />
      <div className="rp-dl">
        {finalVideoUrl && (
          <Reveal as="a" href={finalVideoUrl} download className="rp-dl-main">
            <span className="rp-dl-icon">
              <Clapperboard size={28} strokeWidth={2} />
            </span>
            <span className="rp-dl-body">
              <b>전체 하이라이트 요약 영상</b>
              <span>모든 하이라이트를 이어 붙인 완성본</span>
            </span>
            <span className="rp-dl-btn">
              <Download size={15} strokeWidth={2.4} /> 다운로드
            </span>
          </Reveal>
        )}
        <div className="rp-dl-grid">
          {clips.map((h, i) => (
            <Reveal as="a" key={h.rank} href={h.clip_url} download className="rp-dl-clip" delay={i * 80} style={{ "--c": colorForEmotion(h.streamer_speech_emotion) }}>
              <span className="rp-dl-clip-rank mono">#{h.rank}</span>
              <span className="rp-dl-body">
                <b className="mono">
                  {formatTime(h.start_time)}–{formatTime(h.end_time)}
                </b>
                <span>
                  {h.streamer_speech_emotion} · {h.final_highlight_score.toFixed(1)}점
                </span>
              </span>
              <span className="rp-dl-btn">
                <Download size={15} strokeWidth={2.4} />
              </span>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

function StateCard({ mood, title, children, actions }) {
  return (
    <section className="rp-state">
      <div className="np-hero-bg rp-hero-bg" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="rp-state-card">
        <Mascot mood={mood} size={120} animate />
        <h1>{title}</h1>
        <div className="rp-state-text">{children}</div>
        <div className="rp-hero-actions">{actions}</div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

const RESULT_LINKS = [
  { id: "score", label: "스코어" },
  { id: "video", label: "요약 영상" },
  { id: "chart", label: "감정 그래프" },
  { id: "highlights", label: "하이라이트" },
  { id: "download", label: "다운로드" },
];

const DEMO_MODES = [
  { id: "analyzing", label: "분석 중" },
  { id: "done", label: "결과" },
  { id: "empty", label: "하이라이트 없음" },
  { id: "failed", label: "실패" },
];

export default function ResultPreview() {
  const { videoId } = useParams();
  const isDemo = videoId === "demo";
  const location = useLocation();
  const state = location.state || {};
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [demoMode, setDemoMode] = useState("analyzing");
  const [openRank, setOpenRank] = useState(1);
  const notifiedRef = useRef(false);

  // 실제 결과: 기존 결과 화면과 같은 방식으로 3초마다 서버에 물어봄
  useEffect(() => {
    if (isDemo) return;
    const stop = pollResult(videoId, {
      onUpdate: (data, err) => {
        if (err) {
          setError(err.message);
          return;
        }
        setResult(data);
        if (
          data.video_info.status === "done" &&
          !notifiedRef.current &&
          getNotifyOnDone() &&
          typeof Notification !== "undefined" &&
          Notification.permission === "granted"
        ) {
          notifiedRef.current = true;
          const noHighlights = !data.highlight_result?.highlights?.length;
          const noCandidates = data.highlight_result?.metadata?.empty_reason === "no_candidates";
          new Notification("와바바 분석 완료", {
            body: !noHighlights
              ? "하이라이트 요약이 준비됐어요. 확인해보세요!"
              : noCandidates
                ? "반응이 두드러진 구간을 찾지 못해 하이라이트를 만들지 않았어요."
                : "채팅을 인식하지 못해 하이라이트를 만들지 못했어요.",
            icon: "/favicon.ico",
          });
        }
      },
    });
    return stop;
  }, [videoId, isDemo]);

  useDemoResult(isDemo ? demoMode : null, isDemo ? setResult : noop);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [demoMode]);

  const previewUrl = isDemo ? "/videos/short4.mp4" : state.previewUrl;
  const sourceUrl = isDemo ? null : state.sourceUrl;

  const status = result?.video_info?.status;
  const inProgress = !error && (!result || (status !== "done" && status !== "failed"));
  const highlights = result?.highlight_result?.highlights ?? [];
  const timeSeries = result?.emotion_timeseries?.time_series_data;
  const done = status === "done";
  const hasHighlights = done && highlights.length > 0;
  const duration = Math.max(
    timeSeries?.length ? timeSeries[timeSeries.length - 1].timestamp : 0,
    ...highlights.map((h) => h.end_time),
    1
  );

  // 하이라이트가 없거나 실패하면 분석 곡을 멈추고 메인 곡으로
  useEffect(() => {
    if (error || status === "failed" || (done && !hasHighlights)) setScene("main");
  }, [error, status, done, hasHighlights]);

  const pickHighlight = (rank) => {
    setOpenRank(rank);
    setTimeout(() => document.getElementById(`hl-${rank}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
  };

  return (
    <div className="np rp">
      <TopNav
        links={hasHighlights ? RESULT_LINKS : []}
        cta={{ label: "새 분석", to: "/main#start" }}
        brandTo="/main"
        tone={inProgress ? "dark" : undefined}
      />

      {inProgress && (
        <AnalyzingStage
          status={result?.video_info?.status ?? "queued"}
          step={result?.video_info?.step}
          totalSteps={result?.video_info?.total_steps}
          previewUrl={previewUrl}
          sourceUrl={sourceUrl}
        />
      )}

      {(error || status === "failed") && (
        <StateCard
          mood="oops"
          title="분석 중에 문제가 생겼어요"
          actions={
            <>
              <Link to="/help" className="rp-btn">
                오류 대처 방법
              </Link>
              <Link to="/main#start" className="rp-btn rp-btn-primary">
                다시 분석하기
              </Link>
            </>
          }
        >
          <p>{error || result?.video_info?.error || "알 수 없는 오류가 났어요."}</p>
          <p className="rp-state-sub">오류 대처 방법에서 화면에 뜬 문구와 비슷한 항목을 찾아보세요.</p>
        </StateCard>
      )}

      {done && !hasHighlights && (
        <>
          <StateCard
            mood="thinking"
            title="하이라이트를 찾지 못했어요"
            actions={
              <Link to="/main#start" className="rp-btn rp-btn-primary">
                다른 영상 분석하기
              </Link>
            }
          >
            <p>{EMPTY_HIGHLIGHT_MESSAGE[result?.highlight_result?.metadata?.empty_reason] ?? "하이라이트로 만들 구간을 찾지 못했어요."}</p>
          </StateCard>
          {timeSeries?.length > 0 && (
            <ChartSection timeSeries={timeSeries} threshold={result.emotion_timeseries.recommended_joy_threshold} />
          )}
        </>
      )}

      {hasHighlights && (
        <>
          <ResultHero highlights={highlights} timeSeries={timeSeries} finalVideoUrl={result.final_video_url} />
          {result.final_video_url && (
            <VideoSection
              finalVideoUrl={result.final_video_url}
              highlights={highlights}
              duration={duration}
              onPick={pickHighlight}
            />
          )}
          {timeSeries?.length > 0 && (
            <ChartSection timeSeries={timeSeries} threshold={result.emotion_timeseries.recommended_joy_threshold} />
          )}
          <HighlightsSection
            highlights={highlights}
            timeSeries={timeSeries}
            openRank={openRank}
            setOpenRank={setOpenRank}
          />
          <DownloadSection finalVideoUrl={result.final_video_url} highlights={highlights} />
          <section className="rp-end">
            <Mascot mood="excited" size={84} animate />
            <h2 className="np-section-title">다른 방송도 분석해 볼까요?</h2>
            <Link to="/main#start" className="rp-btn rp-btn-primary">
              새 영상 분석하기
            </Link>
          </section>
        </>
      )}

      {isDemo && (
        <div className="rp-demo" role="group" aria-label="예시 화면 바꾸기">
          <span>예시 데이터</span>
          {DEMO_MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              className={demoMode === m.id ? "is-on" : ""}
              onClick={() => {
                setError(null);
                setResult(null);
                setDemoMode(m.id);
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function noop() {}
