// 와바바 소리 담당: 배경음악(음원 파일) · 효과음
//
// [배경음악] public/bgm/ 폴더의 음원을 끝없이 반복 재생합니다.
//   - main.mp3    : 입장 · 메인 화면
//   - analyze.mp3 : 분석 중 화면
//   - 결과 화면   : 배경음악 없음 (점수 공개 효과음만)
//   화면이 바뀌면(setScene) 필요한 곡으로 부드럽게 넘어가고, 다시 돌아오면 멈췄던 곳부터 이어서 나옵니다.
// [효과음] 분석 단계가 바뀔 때 '띠링', 결과 점수 공개 때 '짠!' — 파일 없이 브라우저 Web Audio로 만듭니다.
// [볼륨] 배경음악·효과음을 각각 켜고 끄고 0~100%로 조절할 수 있고, 브라우저에 기억됩니다.
// [브라우저 제한] 사용자가 한 번 클릭하기 전에는 소리를 낼 수 없어서, 첫 클릭 때 시작합니다.
//   입장 페이지의 "와바바 바로가기" 버튼이 그 첫 클릭 역할을 합니다.

const TRACKS = {
  main: "/bgm/main.mp3",
  analyze: "/bgm/analyze.mp3",
};

// 화면 이름 → 곡 (null이면 배경음악 없음)
function trackForScene(scene) {
  if (!scene) return null;
  if (scene === "result") return null;
  return scene.startsWith("analyze") ? "analyze" : "main";
}

const DUCK_RATIO = 0.25; // 영상 소리가 날 때 배경음을 이 비율로 줄임
const FADE_MS = 800;

// ---------------------------------------------------------------------------
// 설정 (켜짐/꺼짐·볼륨은 브라우저에 기억)

const KEYS = {
  bgm: "wbb_sound_bgm",
  sfx: "wbb_sound_sfx",
  bgmVolume: "wbb_sound_bgm_volume",
  sfxVolume: "wbb_sound_sfx_volume",
};

function load(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return fallback;
    if (typeof fallback === "boolean") return v === "1";
    const n = Number(v);
    return Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : fallback;
  } catch {
    return fallback;
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
  } catch {
    // 저장 실패해도 이번 방문 동안은 동작
  }
}

const state = {
  bgm: load(KEYS.bgm, true), // 배경음악 켜짐
  sfx: load(KEYS.sfx, true), // 효과음 켜짐
  bgmVolume: load(KEYS.bgmVolume, 0.45), // 0~1
  sfxVolume: load(KEYS.sfxVolume, 0.7), // 0~1
  scene: null, // 지금 화면 ("main" | "analyze-N" | "result")
  playing: false, // 배경음악이 실제로 나오는 중인지
};

const listeners = new Set();
function emit() {
  listeners.forEach((fn) => fn({ ...state, hasTrack: !!trackForScene(state.scene ?? "main") }));
}

export function subscribe(fn) {
  listeners.add(fn);
  fn({ ...state, hasTrack: !!trackForScene(state.scene ?? "main") });
  return () => listeners.delete(fn);
}

// ---------------------------------------------------------------------------
// 배경음악 (음원 파일)

const audios = {}; // 곡 이름 → <audio>
const fades = new Map(); // <audio> → 진행 중인 페이드 타이머
let current = null; // 지금 재생 중인 곡 이름
const duckers = new Set(); // 배경음을 줄이게 만든 원인들 (예시 영상 소리 등)

function getAudio(name) {
  if (!audios[name]) {
    const a = new Audio(TRACKS[name]);
    a.loop = true; // 끝나면 처음부터 계속 반복
    a.preload = "auto";
    a.volume = 0;
    // loop를 무시하는 환경을 위한 대비: 끝나면 처음으로 돌아가 다시 재생
    a.addEventListener("ended", () => {
      if (current === name && state.playing) {
        a.currentTime = 0;
        a.play().catch(() => {});
      }
    });
    a.addEventListener("error", () => {
      console.warn(`[와바바] 배경음악 파일을 찾을 수 없어요: public${TRACKS[name]}`);
      if (current === name) {
        state.playing = false;
        emit();
      }
    });
    audios[name] = a;
  }
  return audios[name];
}

function targetLevel() {
  return state.bgmVolume * (duckers.size > 0 ? DUCK_RATIO : 1);
}

function fadeTo(audio, level, ms = FADE_MS, onDone) {
  clearInterval(fades.get(audio));
  const from = audio.volume;
  const start = performance.now();
  const id = setInterval(() => {
    const t = Math.min(1, (performance.now() - start) / ms);
    audio.volume = Math.max(0, Math.min(1, from + (level - from) * t));
    if (t >= 1) {
      clearInterval(id);
      fades.delete(audio);
      onDone?.();
    }
  }, 40);
  fades.set(audio, id);
}

function fadeOutCurrent(ms = FADE_MS) {
  if (!current) return;
  const a = getAudio(current);
  fadeTo(a, 0, ms, () => a.pause());
}

function playTrack(name) {
  if (current && current !== name) fadeOutCurrent();
  current = name;
  const a = getAudio(name);
  const p = a.play();
  if (p && typeof p.then === "function") {
    p.then(() => {
      if (current !== name) return; // 그사이 다른 화면으로 넘어감
      state.playing = true;
      fadeTo(a, targetLevel());
      emit();
    }).catch(() => {
      // 아직 클릭 전이라 브라우저가 막았거나 파일이 없음 → 다음 클릭 때 다시 시도
      state.playing = false;
      emit();
    });
  }
}

// 지금 화면에 맞는 곡을 틀거나(있으면) 조용히 함(없으면)
function applyScene() {
  const want = trackForScene(state.scene);
  if (!state.bgm || !want) {
    fadeOutCurrent(want ? 500 : FADE_MS);
    current = null;
    state.playing = false;
    return;
  }
  if (current !== want || !state.playing) playTrack(want);
}

// 예시 영상 소리가 나는 동안 배경음을 잠깐 줄임
export function setDuck(source, on) {
  if (on) duckers.add(source);
  else duckers.delete(source);
  if (state.playing && current) fadeTo(getAudio(current), targetLevel(), 400);
}

// 화면이 바뀔 때 부름: "main" | "analyze-0"~"analyze-5" | "result"
export function setScene(scene) {
  state.scene = scene;
  const allowed = navigator.userActivation ? navigator.userActivation.hasBeenActive : state.playing;
  if (allowed || !trackForScene(scene)) applyScene();
  emit();
}

// 사용자 클릭 안에서 불러야 소리가 허용됨 (입장 버튼, 소리 버튼 등)
export function unlock() {
  ensureCtx();
  if (state.scene) applyScene();
  emit();
}

export function setBgmEnabled(on) {
  state.bgm = on;
  save(KEYS.bgm, on);
  if (!state.scene) state.scene = "main";
  applyScene();
  emit();
}

export function setBgmVolume(v) {
  state.bgmVolume = Math.min(1, Math.max(0, v));
  save(KEYS.bgmVolume, state.bgmVolume);
  if (state.playing && current) fadeTo(getAudio(current), targetLevel(), 120);
  emit();
}

export function setSfxEnabled(on) {
  state.sfx = on;
  save(KEYS.sfx, on);
  emit();
}

export function setSfxVolume(v) {
  state.sfxVolume = Math.min(1, Math.max(0, v));
  save(KEYS.sfxVolume, state.sfxVolume);
  if (sfxGain) sfxGain.gain.value = state.sfxVolume;
  emit();
}

// 다른 탭으로 가면 잠깐 멈췄다가 돌아오면 이어서
if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (!current || !state.playing) return;
    const a = getAudio(current);
    if (document.hidden) a.pause();
    else a.play().catch(() => {});
  });
}

// 어느 페이지에서든 첫 클릭이 일어나면 그때 배경음 시작
if (typeof window !== "undefined") {
  const first = (e) => {
    // 소리 메뉴 안의 클릭은 메뉴가 직접 처리
    if (e.target?.closest?.(".sound-menu")) return;
    window.removeEventListener("pointerdown", first);
    window.removeEventListener("keydown", first);
    if (state.scene) unlock();
  };
  window.addEventListener("pointerdown", first);
  window.addEventListener("keydown", first);
}

// ---------------------------------------------------------------------------
// 효과음 (Web Audio로 직접 만든 짧은 소리)

let ctx = null;
let sfxGain = null;

function ensureCtx() {
  if (typeof window === "undefined") return null;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  if (!ctx) {
    ctx = new AC();
    sfxGain = ctx.createGain();
    sfxGain.gain.value = state.sfxVolume;
    sfxGain.connect(ctx.destination);
  }
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return ctx;
}

const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);

export function sfx(name) {
  if (!state.sfx || state.sfxVolume <= 0 || !ensureCtx()) return;
  const t = ctx.currentTime + 0.02;
  const tone = (freq, start, dur, level, type = "sine") => {
    const o = ctx.createOscillator();
    o.type = type;
    o.frequency.value = freq;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, start);
    g.gain.exponentialRampToValueAtTime(level, start + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    o.connect(g).connect(sfxGain);
    o.start(start);
    o.stop(start + dur + 0.05);
  };

  if (name === "blip") {
    // 분석 단계가 바뀔 때 '띠링' (볼륨 조절할 때 미리 듣기로도 씀)
    tone(880, t, 0.14, 0.12, "triangle");
    tone(1318.5, t + 0.08, 0.2, 0.1, "triangle");
  } else if (name === "rise") {
    // 점수 게이지가 차오르는 동안 올라가는 음계
    [60, 64, 67, 72, 76, 79, 84, 88].forEach((m, i) => tone(mtof(m), t + i * 0.17, 0.25, 0.07, "triangle"));
  } else if (name === "reveal") {
    // 점수 공개 순간 '짠!' (밝은 화음 + 반짝이는 고음)
    [72, 76, 79, 84].forEach((m) => {
      tone(mtof(m), t, 1.8, 0.09);
      tone(mtof(m) * 2, t, 0.9, 0.025);
    });
    [96, 100, 103].forEach((m, i) => tone(mtof(m), t + 0.05 + i * 0.07, 0.4, 0.04, "triangle"));
  }
}
