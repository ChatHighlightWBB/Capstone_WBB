import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Mascot from "../components/Mascot.jsx";
import { SAMPLE_CHATS } from "../components/LiveChatDecor.jsx";
import PlatformLogo, { PlatformRow } from "../components/PlatformLogo.jsx";
import { SoundMenu } from "../components/SoundControls.jsx";
import { setScene, setDuck } from "../sound.js";
import {
  ArrowDown, ChevronLeft, ChevronRight, Clapperboard, Download, Drama, Eye, FileVideo, Film, FolderUp,
  Gamepad2, Ghost, Goal, Hourglass, Laugh, MessageCircle, MessagesSquare, Mic, Moon, MousePointer2, Palette,
  Radio, ScanText, Scissors, Settings, Star, Sun, Target, Timer, TriangleAlert, Trophy, Tv, Volume2, VolumeX,
} from "lucide-react";
import UploadForm from "../components/UploadForm.jsx";
import RecentHistory from "../components/RecentHistory.jsx";
import Footer from "../components/Footer.jsx";
import { startAnalysis, startAnalysisFromFile } from "../api.js";
import { addToHistory } from "../history.js";
import { getInitialTheme, applyTheme } from "../theme.js";
import "./MainPreview.css";

// 메인 페이지 (/main): 토스 홈페이지처럼 스크롤에 맞춰 화면이 움직이는 구성입니다.
// 각 섹션은 "스크롤 진행도(--p, 0~1)"를 CSS 변수로 받아 3D 회전·확대·전환을 계산합니다.
// 업로드·최근 내역은 공용 컴포넌트(UploadForm, RecentHistory)를 그대로 씁니다.
// 실제 영상은 "어떤 방송이든" 구간의 예시 영상 6개만 쓰고, 나머지 화면은 CSS로 그린 장면입니다.

// ---------------------------------------------------------------------------
// 스크롤 유틸

// 섹션(높이가 화면보다 긴 트랙)이 얼마나 스크롤됐는지 0~1로 계산해 --p에 넣습니다.
export function useScrollProgress(onChange) {
  const ref = useRef(null);
  const cb = useRef(onChange);
  cb.current = onChange;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      const r = el.getBoundingClientRect();
      const total = r.height - window.innerHeight;
      const p = total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 0;
      el.style.setProperty("--p", p.toFixed(4));
      cb.current?.(p, el);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return ref;
}

// 화면에 처음 들어왔는지 (한 번 true가 되면 유지)
export function useInView(threshold = 0.25) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || inView) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      { threshold }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [inView, threshold]);
  return [ref, inView];
}

// 화면에 들어오면 아래에서 떠오르는 블록
export function Reveal({ as: Tag = "div", className = "", delay = 0, style, children, ...rest }) {
  const [ref, inView] = useInView(0.2);
  return (
    <Tag
      ref={ref}
      className={`np-reveal ${inView ? "np-in" : ""} ${className}`}
      style={{ transitionDelay: `${delay}ms`, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

// 숫자가 0부터 올라가는 카운터
export function CountUp({ to, suffix = "", duration = 1400 }) {
  const [ref, inView] = useInView(0.5);
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!inView) return;
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(to * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, duration]);
  return (
    <span ref={ref}>
      {value.toLocaleString()}
      {suffix}
    </span>
  );
}

// 섹션 머리말 (작은 색 라벨 + 큰 제목 + 설명)
export function SectionHead({ eyebrow, title, sub, dark = false, align = "center" }) {
  return (
    <Reveal className={`np-head np-head-${align} ${dark ? "np-head-dark" : ""}`}>
      <span className="np-eyebrow">{eyebrow}</span>
      <h2 className="np-section-title">{title}</h2>
      {sub && <p className="np-head-sub">{sub}</p>}
    </Reveal>
  );
}

const clamp01 = (v) => Math.min(1, Math.max(0, v));
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// ---------------------------------------------------------------------------
// 데이터

const NICK_COLORS = ["#8c6fff", "#ff8a3d", "#00c875", "#0182ff", "#ff3b30"];

const HERO_CHATS = [
  ["따마커", "ㅋㅋㅋㅋㅋㅋㅋㅋ", "#ff8a3d"],
  ["새벽세시라면", "역전 ㅋㅋㅋㅋㅋ", "#00c875"],
  ["딸기우유원샷", "와 미친", "#0182ff"],
  ["감자칩한봉지", "미친 원더골 ㄷㄷ", "#8c6fff"],
  ["반숙계란", "홀리쉿", "#ff3b30"],
  ["김밥한줄", "신이다", "#ff8a3d"],
  ["바닐라라떼", "뛰어 ㅋㅋㅋㅋㅋㅋㅋ", "#00c875"],
  ["노을지는밤", "캬ㅑㅑㅑ", "#0182ff"],
];

// 첫 화면 모니터에 그려지는 장면. 영상 대신 하이라이트 종류에 맞춘 그림이라 채팅과 어긋나지 않습니다.
const IDLE_SCENE = { mood: "happy", Icon: Tv, word: "방송 중", a: "#3B8BFF", b: "#151a33" };

// 첫 화면에서 순서대로 발견되는 하이라이트 5개 (채팅은 LiveChatDecor와 같은 학습 데이터셋 문구)
// min: 방송 전체(130분) 중 위치(분), chats: 그 순간 좌우에 뜨는 채팅
const TOTAL_MIN = 130;
const HIGHLIGHTS = [
  {
    time: "00:12:40", min: 12.7, tag: "역전", mood: "excited", Icon: Trophy, word: "역전!", a: "#FF6A5C", b: "#7a2a10",
    chats: [["새벽세시라면", "역전 ㅋㅋㅋㅋㅋㅋㅋ"], ["딸기우유원샷", "와 미친"], ["반숙계란", "홀리쉿"], ["커피세잔째", "가주아 ~~~"], ["김밥한줄", "신이다"], ["노을지는밤", "캬ㅑㅑㅑ"]],
  },
  {
    time: "00:47:05", min: 47.1, tag: "공포", mood: "oops", Icon: Ghost, word: "으악!", a: "#6B4BD8", b: "#0d0a1f", star: true,
    chats: [["오늘도출석", "뭉서워요 ㄷㄷㄷ"], ["퇴근하고싶다", "지하실 헉"], ["밤샘장인", "헐?"], ["알람다섯개", "소리봐라 ㄷㄷ"], ["주말만기다려", "뭔가 온다"], ["팝콘준비완료", "진짜루?"]],
  },
  {
    time: "01:05:12", min: 65.2, tag: "슈퍼플레이", mood: "excited", Icon: Gamepad2, word: "슈퍼플레이", a: "#2FD18F", b: "#0c3b5c",
    chats: [["고양이발바닥", "무빙 지리네"], ["민트초코파", "회피궁 ㄷㄷ"], ["펭귄걸음", "던지는거 개쩌네 ㅋㅋㅋ"], ["햄스터볼", "탑미드 레전드 ㅋㅋㅋㅋㅋ"], ["떡볶이중독", "와 대단하네;;"], ["졸린판다", "gggggggggg"]],
  },
  {
    time: "01:22:31", min: 82.5, tag: "빵 터진 리액션", mood: "excited", Icon: Laugh, word: "빵 터짐", a: "#FFB020", b: "#8a3b00",
    chats: [["치즈볼러버", "재밌네 ㅋㅋ"], ["멍뭉이집사", "띠용"], ["따마커", "ㅋㅋㅋㅋㅋㅋㅋㅋㅋ"], ["초코송이", "부담감 maxㅋㅋㅋ"], ["호떡굽는곰", "사투리도 대박 ㅋㅋ"], ["택배언제와", "합체 ㅋㅋ"]],
  },
  {
    time: "01:58:44", min: 118.7, tag: "원더골", mood: "excited", Icon: Goal, word: "골!!!", a: "#00C875", b: "#06331f",
    chats: [["감자칩한봉지", "미친 원더골 ㄷㄷ"], ["귤까는중", "파울 아니네 ㅋㅋㅋㅋ"], ["토끼풀", "와 골대"], ["붕어빵팥파", "노골~~~~~~~"], ["별보러가자", "드가자~~~"], ["양말한짝", "한골만"]],
  },
];

// 모니터 위로 떠오르는 반응 (처음 화면 장식)
const REACTIONS = ["ㅋㅋㅋ", "대박", "ㄷㄷ", "레전드", "!!", "ㅠㅠ", "ㅋㅋㅋㅋ", "GG", "?", "와"];

const NAV = [
  { id: "how", label: "이용 방법" },
  { id: "pipeline", label: "분석 과정" },
  { id: "features", label: "기능" },
  { id: "result", label: "결과 화면" },
  { id: "baba", label: "바바" },
];

const GUIDE = [
  { Icon: FolderUp, title: "영상 올리기", desc: "영상 파일을 올리거나 유튜브 링크를 붙여넣어요. 치지직·SOOP 다시보기는 파일로 올려 주세요.", mock: "upload" },
  { Icon: ScanText, title: "채팅창 확인", desc: "채팅창 위치를 자동으로 찾아요. 안 맞으면 미리보기 화면에서 드래그로 바로 지정해요.", mock: "crop" },
  { Icon: Hourglass, title: "자동 분석", desc: "다섯 단계 분석이 진행돼요. 지금 몇 번째 단계인지 실시간으로 보여드려요.", mock: "progress" },
  { Icon: Clapperboard, title: "결과 받기", desc: "요약 영상, 하이라이트별 클립, 감정 그래프를 한 화면에서 보고 내려받아요.", mock: "download" },
];

export const STEPS = [
  {
    name: "채팅 읽기",
    tool: "OCR",
    title: "화면 속 채팅을\n그대로 읽어요",
    desc: "5초마다 채팅창만 잘라내고, 방송 채팅 글씨로 따로 학습시킨 모델로 글자를 읽어요.",
    color: "#2FD18F",
  },
  {
    name: "감정 분석",
    tool: "KoBERT",
    title: "ㅋㅋㅋ에 담긴\n감정까지",
    desc: "방송 말투로 학습한 한국어 모델이 채팅을 7가지 감정으로 나눠요.",
    color: "#FFB020",
  },
  {
    name: "후보 찾기",
    tool: "30초 단위",
    title: "이 방송에 맞는\n기준으로 골라요",
    desc: "영상 전체 반응을 먼저 보고, 그 영상에 맞는 기준을 넘는 구간만 후보로 남겨요.",
    color: "#3B8BFF",
  },
  {
    name: "목소리 확인",
    tool: "Whisper",
    title: "스트리머 목소리로\n한 번 더 확인",
    desc: "게임 소리를 걷어내고 목소리만 남겨, 실제로 무슨 말을 했는지 듣고 최종 구간을 정해요.",
    color: "#8C6FFF",
  },
  {
    name: "잘라 붙이기",
    tool: "FFmpeg",
    title: "화질 그대로\n잘라 붙여요",
    desc: "다시 인코딩하지 않고 원본에서 구간만 잘라 요약 영상과 클립을 만들어요.",
    color: "#FF6A5C",
  },
];

const EMOTIONS = [
  { name: "기쁨", v: 0.92, c: "#FFB020" },
  { name: "당황", v: 0.55, c: "#8C6FFF" },
  { name: "분노", v: 0.18, c: "#FF3B30" },
  { name: "슬픔", v: 0.12, c: "#3B8BFF" },
  { name: "혐오", v: 0.08, c: "#2FB07A" },
  { name: "공포", v: 0.22, c: "#555A66" },
  { name: "중립", v: 0.4, c: "#A6A3B0" },
];

// 감정 그래프 예시 (0~100)
const CURVE = [22, 28, 25, 34, 30, 48, 82, 74, 40, 32, 36, 30, 44, 91, 86, 50, 38, 30, 34, 62, 70, 42, 30, 26];
const THRESHOLD = 60;

function curvePath(values, w, h) {
  const step = w / (values.length - 1);
  return values
    .map((v, i) => `${i ? "L" : "M"}${(i * step).toFixed(1)} ${(h - (v / 100) * h).toFixed(1)}`)
    .join(" ");
}

const SAMPLES = [
  { video: "/videos/short1.mp4", tag: "게임 방송" },
  { video: "/videos/short2.mp4", tag: "공포 게임" },
  { video: "/videos/short3.mp4", tag: "게임 방송 2" },
  { video: "/videos/short4.mp4", tag: "버라이어티" },
  { video: "/videos/short5.mp4", tag: "합방" },
  { video: "/videos/short6.mp4", tag: "스포츠 중계" },
];

const NUMBERS = [
  { Icon: MessagesSquare, to: 15000, suffix: "+", label: "학습한 방송 채팅 줄", note: "방송 말투 그대로 파인튜닝" },
  { Icon: Drama, to: 7, label: "가지 감정", note: "기쁨·당황·분노·슬픔·혐오·공포·중립" },
  { Icon: Timer, to: 5, suffix: "초", label: "마다 채팅을 읽어요", note: "30초 구간을 5초씩 옮겨 가며 비교" },
  { Icon: Film, to: 0, label: "번 재인코딩", note: "원본 화질 그대로 잘라내요" },
];

const FEATURES = [
  { platforms: true, title: "어떤 플랫폼이든", desc: "화면에 채팅창만 보이면 유튜브·치지직·SOOP 어디서 온 영상이든 똑같이 읽어요.", fact: "방송 채팅 전용 OCR 모델" },
  { Icon: Laugh, title: "방송 말투 그대로", desc: "\"ㅋㅋㅋ\", \"ㅠㅠ\", 줄임말까지 학습한 모델이 감정을 알아들어요.", fact: "채팅 1만 5천여 줄로 학습한 KoBERT" },
  { Icon: Target, title: "영상마다 다른 기준", desc: "시끄러운 게임 방송도, 잔잔한 토크 방송도 각자에 맞는 기준으로 골라요.", fact: "영상 전체 반응으로 기준 자동 설정" },
  { Icon: Mic, title: "목소리까지 확인", desc: "채팅만 보지 않고 스트리머가 실제로 한 말을 듣고 최종 결정을 내려요.", fact: "Demucs 목소리 분리 + Whisper" },
  { Icon: Star, title: "와바바 포인트", desc: "가장 크게 터진 순간을 별로 짚고, 방송 분위기를 스코어 한 숫자로 보여줘요.", fact: "역대급부터 차분한 방송까지 4단계" },
  { Icon: Scissors, title: "무손실 클립", desc: "원본 화질 그대로 요약 영상과 하이라이트별 클립을 내려받아요.", fact: "FFmpeg 무인코딩 클리핑" },
];

// 바바 표정별 상세 (BabaIntro의 설명을 바탕으로 확장)
const BABA_MOODS = [
  {
    mood: "happy",
    name: "기본",
    line: "영상 하나만 주세요!",
    where: ["홈 화면", "사이드바 로고"],
    desc: "평소의 바바예요. 홈 화면에서 예시 영상과 업로드 방법을 안내하고, 어느 페이지에 있든 왼쪽 위 로고 자리에서 지켜보고 있어요.",
    look: "동그란 눈과 살짝 웃는 입, 분홍 볼",
  },
  {
    mood: "excited",
    name: "신남",
    line: "여기 터졌어요!",
    where: ["처음 안내 화면", "재밌는 결과 화면"],
    desc: "채팅이 크게 터진 순간을 찾았을 때 나오는 표정이에요. 와바바 스코어가 높게 나온 결과 화면에서 같이 기뻐해요.",
    look: "> < 모양으로 감은 눈, 크게 벌린 입",
  },
  {
    mood: "working",
    name: "일하는 중",
    line: "잠깐만요, 읽는 중이에요…",
    where: ["분석 진행 화면"],
    desc: "분석하는 동안 땀을 흘리며 채팅을 한 줄 한 줄 읽어요. 지금 몇 번째 단계인지도 바바 옆 말풍선으로 알려줘요.",
    look: "치켜올린 눈썹, 앙 다문 입, 흘러내리는 땀방울",
  },
  {
    mood: "thinking",
    name: "생각 중",
    line: "음… 조용한 방송이었나 봐요",
    where: ["결과 읽는 법 안내", "하이라이트가 없을 때"],
    desc: "결과 화면의 숫자와 표시를 설명해 주거나, 기준을 넘는 순간을 찾지 못했을 때 고민하는 표정이에요.",
    look: "위를 올려다보는 눈, 머리 위 물음표",
  },
  {
    mood: "oops",
    name: "당황",
    line: "앗, 뭔가 잘못됐어요",
    where: ["분석 실패 화면", "오류 대처 방법 페이지"],
    desc: "분석 중 문제가 생기면 나와요. 당황하면서도 무엇을 해 보면 되는지 오류 대처 방법으로 안내해요.",
    look: "물결 모양 입, 식은땀 한 방울",
  },
];

const BABA_PROFILE = [
  { label: "이름", value: "바바 (와바바의 '바바')" },
  { label: "태어난 곳", value: "어느 방송의 채팅창. 시청자들이 친 말풍선 하나가 바바가 됐어요." },
  { label: "하는 일", value: "몇 시간짜리 방송 채팅을 처음부터 끝까지 읽고, 시청자가 크게 반응한 순간을 찾아와요." },
  { label: "좋아하는 것", value: "끝없이 이어지는 ㅋㅋㅋㅋ, 한꺼번에 쏟아지는 ???" },
  { label: "싫어하는 것", value: "아무도 채팅을 치지 않는 조용한 구간" },
];

const BABA_LOOKS = [
  { Icon: MessageCircle, part: "몸", desc: "채팅 말풍선이에요. 왼쪽 아래 꼬리까지 그대로예요." },
  { Icon: Palette, part: "몸 색", desc: "빨강·초록·파랑. 유튜브, 치지직, SOOP 어느 방송이든 읽는다는 뜻이에요." },
  { Icon: Radio, part: "안테나", desc: "끝에 재생 버튼이 달려 있어요. 영상 신호를 받는 안테나예요." },
];

// ---------------------------------------------------------------------------
// 공통 그림

// 모니터 화면에 그려지는 방송 장면 (영상 대신): 바바 표정 + 상황 아이콘 + 큰 글자
export function StreamScene({ scene, on }) {
  return (
    <div className={`np-art ${on ? "is-on" : ""}`} style={{ "--a": scene.a, "--b": scene.b }}>
      <div className="np-art-rays" />
      <div className="np-art-floor" />
      <div className="np-art-center">
        <span className="np-art-figure">
          <Mascot mood={scene.mood} size={120} outline="#17171B" className="np-art-mascot" />
          {scene.Icon && (
            <span className="np-art-badge" aria-hidden="true">
              <scene.Icon strokeWidth={2.2} />
            </span>
          )}
        </span>
        <span className="np-art-word">{scene.word}</span>
      </div>
      <div className="np-art-meter">
        {Array.from({ length: 32 }, (_, i) => (
          <i key={i} style={{ "--i": i, "--h": 0.25 + 0.75 * Math.abs(Math.sin(i * 0.9) * Math.cos(i * 0.31)) }} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 섹션

// links: 가운데 메뉴 [{id,label}] · cta: 오른쪽 파란 버튼 {label, target(같은 페이지 id) | to(다른 페이지)}
// brandTo: 로고를 눌렀을 때 갈 페이지 (없으면 맨 위로 스크롤)
// tone="dark": 어두운 배경 위에 올라갈 때(분석 중 화면) 글자를 밝게
export function TopNav({ links = NAV, cta = { label: "분석 시작", target: "start" }, brandTo, tone }) {
  const [theme, setTheme] = useState(getInitialTheme());
  const [scrolled, setScrolled] = useState(false);
  const [current, setCurrent] = useState(null);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // 스크롤 위치에 맞춰 지금 보고 있는 구간의 메뉴를 표시
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      setScrolled(window.scrollY > 8);
      const line = window.innerHeight * 0.4;
      let found = null;
      for (const n of links) {
        const el = document.getElementById(n.id);
        if (el && el.getBoundingClientRect().top <= line) found = n.id;
      }
      const start = document.getElementById("start");
      if (start && start.getBoundingClientRect().top <= line) found = null;
      setCurrent(found);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
    };
  }, [links]);

  const go = (id) => (e) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    window.dispatchEvent(new Event("wbb-theme-change"));
  };

  return (
    <header className={`np-nav ${scrolled ? "np-nav-scrolled" : ""} ${tone === "dark" ? "np-nav-on-dark" : ""}`}>
      {brandTo ? (
        <Link to={brandTo} className="np-nav-brand">
          <Mascot size={30} />
          <span>와바바</span>
        </Link>
      ) : (
        <a href="#top" className="np-nav-brand" onClick={go("top")}>
          <Mascot size={30} />
          <span>와바바</span>
        </a>
      )}
      <nav className="np-nav-links">
        {links.map((n) => (
          <a key={n.id} href={`#${n.id}`} onClick={go(n.id)} className={current === n.id ? "is-current" : ""}>
            {n.label}
          </a>
        ))}
      </nav>
      <div className="np-nav-right">
        <SoundMenu className="np-nav-icon" />
        <Link to="/help" className="np-nav-sub">
          도움말
        </Link>
        <Link to="/settings" className="np-nav-icon" aria-label="설정" title="설정">
          <Settings size={18} strokeWidth={2} />
        </Link>
        <button type="button" className="np-nav-icon" onClick={toggleTheme} aria-label="테마 전환" title="테마 전환">
          {theme === "light" ? <Moon size={18} strokeWidth={2} /> : <Sun size={18} strokeWidth={2} />}
        </button>
        {cta.to ? (
          <Link to={cta.to} className="np-nav-cta">
            {cta.label}
          </Link>
        ) : (
          <a href={`#${cta.target}`} className="np-nav-cta" onClick={go(cta.target)}>
            {cta.label}
          </a>
        )}
      </div>
    </header>
  );
}

// 1. 히어로: 책상 위 모니터·폰이 떠 있다가, 스크롤하면 카메라가 모니터 화면 안으로 줌인.
//    화면이 꽉 차면 하이라이트가 하나씩 발견되며 그 순간의 채팅이 좌우에 뜸.
// 진행도 구간: 0~0.04 대기 · 0.04~0.38 줌인 · 0.42~0.92 하이라이트 5개 · 0.93~ 완료
function HeroSection() {
  const [active, setActive] = useState(-1);
  const screenRef = useRef(null);

  const ref = useScrollProgress((p, el) => {
    el.style.setProperty("--k", easeInOut(clamp01((p - 0.04) / 0.34)).toFixed(4));
    el.style.setProperty("--e", clamp01((p - 0.93) / 0.05).toFixed(4));
    const h = (p - 0.42) / 0.5;
    const n = h < 0 ? -1 : Math.min(HIGHLIGHTS.length - 1, Math.floor(h * HIGHLIGHTS.length));
    setActive((cur) => (cur === n ? cur : n));
  });

  // 모니터 화면이 뷰포트를 꽉 덮으려면 몇 배 확대해야 하는지 계산 (--zoom)
  useEffect(() => {
    const measure = () => {
      const s = screenRef.current;
      const el = ref.current;
      if (!s || !el || !s.offsetWidth) return;
      const z = Math.max(window.innerWidth / s.offsetWidth, window.innerHeight / s.offsetHeight) * 1.04;
      el.style.setProperty("--zoom", z.toFixed(3));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [ref]);

  const current = active >= 0 ? HIGHLIGHTS[active] : null;

  return (
    <section id="top" ref={ref} className="np-hero">
      <div className="np-sticky np-hero-sticky">
        <div className="np-hero-bg" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>

        <div className="np-hero-copy">
          <span className="np-eyebrow">AI 방송 하이라이트</span>
          <h1>
            몇 시간짜리 방송,
            <br />
            <span className="np-grad-text">터진 순간만</span> 자동으로.
          </h1>
          <p>시청자 채팅과 스트리머 목소리를 함께 읽어서 진짜 하이라이트만 골라냅니다.</p>
          <PlatformRow size={20} className="np-hero-platforms" />
        </div>

        {/* 모니터 주변으로 떠오르는 반응 */}
        <div className="np-reactions" aria-hidden="true">
          {REACTIONS.map((r, i) => (
            <span key={i} style={{ "--i": i, "--x": `${8 + ((i * 37) % 84)}%` }}>
              {r}
            </span>
          ))}
        </div>

        <div className="np-rig-float">
          <div className="np-rig">
            <div ref={screenRef} className="np-rig-screen">
              <StreamScene scene={IDLE_SCENE} on={active < 0} />
              {HIGHLIGHTS.map((hl, i) => (
                <StreamScene key={hl.time} scene={hl} on={i === active} />
              ))}
              <div className="np-rig-ui" aria-hidden="true">
                <span className="np-rig-live">● LIVE</span>
                <span className="np-rig-viewers">
                  <Eye size={12} strokeWidth={2.4} /> 12,408
                </span>
                <div className="np-rig-progress">
                  <i />
                </div>
              </div>
              <div className="np-rig-glare" aria-hidden="true" />
            </div>
            <div className="np-rig-stand" aria-hidden="true">
              <i />
              <b />
            </div>

            {/* 옆에 세워둔 폰: 채팅 앱 */}
            <div className="np-phone" aria-hidden="true">
              <div className="np-phone-inner">
                <div className="np-phone-notch" />
                <div className="np-phone-head">실시간 채팅</div>
                <div className="np-phone-chat">
                  <div className="np-phone-track">
                    {[...HERO_CHATS, ...HERO_CHATS].map(([nick, text, color], i) => (
                      <div key={i}>
                        <b style={{ color }}>{nick}</b> {text}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 화면 안으로 들어간 뒤 보이는 정보 */}
        <div className="np-hud" aria-hidden={active < 0}>
          <div className="np-hud-vignette" />

          <div className={`np-hud-badge ${active >= 0 ? "is-on" : ""}`}>
            <Mascot mood="excited" size={52} />
            <div className="np-hud-badge-text">
              <span>
                하이라이트 <b key={active}>{Math.max(0, active + 1)}</b>개 발견
              </span>
              <em>{current ? `${current.time} · ${current.tag}` : ""}</em>
            </div>
          </div>

          {current && (
            <>
              <div className="np-hud-chats np-hud-left" key={`l${active}`}>
                {current.chats
                  .filter((_, i) => i % 2 === 0)
                  .map(([nick, text], j) => (
                    <div key={nick} className="np-hud-chat" style={{ "--d": `${j * 260}ms`, "--r": `${j % 2 ? 2 : -2}deg` }}>
                      <b style={{ color: NICK_COLORS[(active + j * 2) % NICK_COLORS.length] }}>{nick}</b>
                      <span>{text}</span>
                    </div>
                  ))}
              </div>
              <div className="np-hud-chats np-hud-right" key={`r${active}`}>
                {current.chats
                  .filter((_, i) => i % 2 === 1)
                  .map(([nick, text], j) => (
                    <div
                      key={nick}
                      className="np-hud-chat"
                      style={{ "--d": `${130 + j * 260}ms`, "--r": `${j % 2 ? -2 : 2}deg` }}
                    >
                      <b style={{ color: NICK_COLORS[(active + j * 2 + 1) % NICK_COLORS.length] }}>{nick}</b>
                      <span>{text}</span>
                    </div>
                  ))}
              </div>
            </>
          )}

          <div className="np-hud-timeline">
            <div className="np-hud-track" />
            {HIGHLIGHTS.map((hl, i) => (
              <div
                key={hl.time}
                className={`np-hud-mark ${i <= active ? "is-lit" : ""} ${i === active ? "is-active" : ""} ${hl.star ? "is-star" : ""}`}
                style={{ left: `${(hl.min / TOTAL_MIN) * 100}%` }}
              >
                <span className="np-hud-mark-label">
                  {hl.star && (
                    <i>
                      <Star size={12} fill="currentColor" strokeWidth={0} /> 와바바 포인트
                    </i>
                  )}
                  {hl.time}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="np-scroll-hint" aria-hidden="true">
          <span className="np-scroll-mouse" />
        </div>
      </div>
    </section>
  );
}

// 2. 이용 방법: 화면이 고정된 채 스크롤하면 카드가 아래에서 3D로 하나씩 날아와 자리 잡음
//    (카드 i는 진행도 i*0.2 ~ i*0.2+0.2 구간에서 등장, 연결선도 함께 채워짐)
function GuideMock({ type }) {
  if (type === "upload")
    return (
      <div className="np-mock np-mock-upload">
        <div className="np-mock-drop">
          <span className="np-mock-file">
            <FileVideo size={14} strokeWidth={2.2} /> 방송_다시보기.mp4
          </span>
        </div>
      </div>
    );
  if (type === "crop")
    return (
      <div className="np-mock np-mock-crop">
        <div className="np-mock-frame">
          <div className="np-mock-chatbox">
            <i />
            <i />
            <i />
            <i />
          </div>
          <span className="np-mock-cursor">
            <MousePointer2 size={16} fill="#fff" strokeWidth={1.5} />
          </span>
        </div>
      </div>
    );
  if (type === "progress")
    return (
      <div className="np-mock np-mock-progress">
        <Mascot mood="working" size={40} />
        <div className="np-mock-bars">
          {STEPS.map((s, i) => (
            <i key={s.name} style={{ "--i": i, "--c": s.color }} />
          ))}
        </div>
      </div>
    );
  return (
    <div className="np-mock np-mock-download">
      {["요약 영상", "클립 1", "클립 2"].map((t) => (
        <span key={t}>
          {t} <Download size={13} strokeWidth={2.4} />
        </span>
      ))}
    </div>
  );
}

function GuideSection() {
  const [landed, setLanded] = useState(0);
  const ref = useScrollProgress((p) => {
    const n = GUIDE.filter((_, i) => p >= i * 0.2 + 0.2).length;
    setLanded((cur) => (cur === n ? cur : n));
  });

  return (
    <section id="how" ref={ref} className="np-guide">
      <div className="np-sticky np-guide-sticky">
        <SectionHead eyebrow="이용 방법" title="네 단계면 끝나요" sub="회원가입도, 편집도 필요 없어요." />
        <div className="np-guide-grid">
          <div className="np-guide-line" aria-hidden="true">
            <i />
          </div>
          {GUIDE.map((g, i) => (
            <div
              key={g.title}
              className={`np-guide-card ${i < landed ? "is-landed" : ""} ${i === landed - 1 ? "is-current" : ""}`}
              style={{ "--i": i, "--rz": `${i % 2 ? 7 : -7}deg` }}
            >
              <div className="np-guide-top">
                <span className="np-guide-num">{i + 1}</span>
                <span className="np-icon-tile np-guide-icon" aria-hidden="true">
                  <g.Icon size={22} strokeWidth={2} />
                </span>
              </div>
              <GuideMock type={g.mock} />
              <h3>{g.title}</h3>
              <p>{g.desc}</p>
            </div>
          ))}
        </div>
        <div className="np-guide-steps" aria-hidden="true">
          {GUIDE.map((g, i) => (
            <span key={g.title} className={i < landed ? "is-on" : ""} />
          ))}
        </div>
      </div>
    </section>
  );
}

// 스트리머 발화 예시 (Whisper 받아쓰기 장면). 페이지를 열 때마다 무작위로 골라 보여줍니다.
const EMO_COLOR = { 기쁨: "#FFB020", 당황: "#8C6FFF", 공포: "#6B8BFF", 분노: "#FF5A4F" };
const SPEECH_POOL = [
  ["와 이게 되네?", "기쁨"],
  ["잠깐만, 이거 뭐야?", "당황"],
  ["아 진짜 말도 안 돼", "기쁨"],
  ["됐다 됐다 됐다!", "기쁨"],
  ["여러분 방금 보셨어요?", "기쁨"],
  ["아니 왜 여기서 나와!", "공포"],
  ["한 번만 더 해볼게요", "분노"],
  ["와 소름 돋았어", "공포"],
  ["이건 클립 따야 돼", "기쁨"],
  ["오늘 최고의 순간이다", "기쁨"],
  ["어? 어어? 잠깐만", "당황"],
  ["이걸 잡네 이걸?", "기쁨"],
  ["아 깜짝이야 진짜", "공포"],
  ["이거 실화냐고", "당황"],
  ["아 이걸 놓치네", "분노"],
];

const pickOne = (arr) => arr[Math.floor(Math.random() * arr.length)];
let sceneSeq = 0;

// exclude: 지금 화면에 보이는 문구 (같은 문구가 연달아 나오지 않게)
function randomChat(exclude = []) {
  const c = pickOne(SAMPLE_CHATS.filter((x) => !exclude.includes(x.text)));
  return { nick: c.nick, text: c.text, color: c.nickColor, id: ++sceneSeq };
}

function randomSpeech(exclude = []) {
  const [text, emotion] = pickOne(SPEECH_POOL.filter(([t]) => !exclude.includes(t)));
  return { text, emotion, color: EMO_COLOR[emotion], conf: (0.62 + Math.random() * 0.35).toFixed(2), id: ++sceneSeq };
}

// 채팅 읽기 장면: 처음 7줄을 무작위로 고르고, 그 장면이 보이는 동안 새 채팅이 아래에서 계속 올라옴
function useOcrLines(active) {
  const [lines, setLines] = useState(() => {
    const out = [];
    for (let i = 0; i < 7; i++) out.push(randomChat(out.map((c) => c.text)));
    return out;
  });
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setLines((ls) => [...ls.slice(1), randomChat(ls.map((c) => c.text))]), 1100);
    return () => clearInterval(id);
  }, [active]);
  return lines;
}

// 목소리 확인 장면: 받아쓴 발화 3개를 무작위로 보여주고, 보이는 동안 하나씩 새 발화로 바뀜
function useSpeeches(active) {
  const [list, setList] = useState(() => {
    const out = [];
    for (let i = 0; i < 3; i++) out.push(randomSpeech(out.map((s) => s.text)));
    return out;
  });
  useEffect(() => {
    if (!active) return;
    const id = setInterval(
      () => setList((ls) => [...ls.slice(1), randomSpeech(ls.map((s) => s.text))]),
      2400
    );
    return () => clearInterval(id);
  }, [active]);
  return list;
}

// 분석 단계(0~4)에 맞는 그림이 나오는 3D 창. 분석 과정 구간과 분석 중 화면(ResultPreview)에서 함께 씁니다.
export function PipelineDevice({ step }) {
  const W = 480;
  const H = 200;
  const thresholdY = H - (THRESHOLD / 100) * H;
  const safe = Math.max(0, Math.min(STEPS.length - 1, step));
  const ocrLines = useOcrLines(step === 0);
  const speeches = useSpeeches(step === 3);
  const lastOcrId = ocrLines[ocrLines.length - 1].id;
  return (
    <div className="np-flow-device" data-step={step}>
      <div className="np-flow-device-bar" aria-hidden="true">
        <i />
        <i />
        <i />
        <span>wbb · {STEPS[safe].name}</span>
      </div>

      {/* 0. 채팅 읽기 */}
      <div className={`np-scene ${step === 0 ? "is-active" : ""}`}>
        <div className="np-ocr">
          {/* 새 줄이 들어올 때마다 목록 전체가 한 줄만큼 부드럽게 올라가도록 key로 다시 그림 */}
          <div className="np-ocr-list" key={lastOcrId}>
            {ocrLines.map((c, i) => (
              <div key={c.id} className={`np-ocr-line ${i === ocrLines.length - 1 ? "is-new" : ""}`}>
                <b style={{ color: c.color }}>{c.nick}</b>
                <span>{c.text}</span>
              </div>
            ))}
          </div>
          <div className="np-ocr-scan" />
        </div>
      </div>

      {/* 1. 감정 분석 */}
      <div className={`np-scene ${step === 1 ? "is-active" : ""}`}>
        <div className="np-emo">
          {EMOTIONS.map((e, i) => (
            <div key={e.name} className="np-emo-col" style={{ "--v": e.v, "--c": e.c, "--i": i }}>
              <div className="np-emo-bar" />
              <span>{e.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 2. 후보 구간 */}
      <div className={`np-scene ${step === 2 ? "is-active" : ""}`}>
        <svg className="np-curve" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
          <defs>
            <linearGradient id="np-curve-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3B8BFF" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#3B8BFF" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[
            [5, 8],
            [12, 15],
            [18, 21],
          ].map(([a, b]) => {
            const unit = W / (CURVE.length - 1);
            return (
              <rect key={a} className="np-curve-hit" x={a * unit} y="0" width={(b - a) * unit} height={H} rx="6" />
            );
          })}
          <path d={`${curvePath(CURVE, W, H)} L${W} ${H} L0 ${H} Z`} fill="url(#np-curve-fill)" />
          <path className="np-curve-line" d={curvePath(CURVE, W, H)} />
          <line className="np-curve-th" x1="0" x2={W} y1={thresholdY} y2={thresholdY} />
        </svg>
      </div>

      {/* 3. 목소리 확인 */}
      <div className={`np-scene ${step === 3 ? "is-active" : ""}`}>
        <div className="np-voice">
          <div className="np-voice-row np-voice-bg">
            {Array.from({ length: 36 }, (_, i) => (
              <i key={i} style={{ "--h": 0.25 + 0.7 * Math.abs(Math.sin(i * 1.7)) }} />
            ))}
          </div>
          <div className="np-voice-row np-voice-fg">
            {Array.from({ length: 36 }, (_, i) => (
              <i key={i} style={{ "--h": 0.15 + 0.85 * Math.abs(Math.sin(i * 0.55) * Math.cos(i * 0.21)) }} />
            ))}
          </div>
          <div className="np-voice-bubbles">
            {speeches.map((sp, i) => (
              <div key={sp.id} className={`np-voice-bubble ${i % 2 ? "is-right" : ""}`}>
                <span>"{sp.text}"</span>
                <em style={{ color: sp.color }}>
                  {sp.emotion} {sp.conf}
                </em>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 4. 잘라 붙이기 */}
      <div className={`np-scene ${step === 4 ? "is-active" : ""}`}>
        <div className="np-cut">
          <div className="np-cut-source">
            {[12, 34, 58, 80].map((x, i) => (
              <span key={x} style={{ left: `${x}%`, "--i": i }} />
            ))}
          </div>
          <div className="np-cut-arrow">
          <ArrowDown size={26} strokeWidth={2} />
        </div>
          <div className="np-cut-result">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} style={{ "--i": i }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// 3. 분석 과정: 스크롤하면 왼쪽 설명과 오른쪽 3D 화면이 단계별로 바뀜
function FlowSection() {
  const [step, setStep] = useState(0);
  const ref = useScrollProgress((p, el) => {
    const raw = p * STEPS.length;
    const s = Math.min(STEPS.length - 1, Math.floor(raw));
    el.style.setProperty("--sp", clamp01(raw - s).toFixed(4));
    setStep((cur) => (cur === s ? cur : s));
  });

  return (
    <section
      id="pipeline"
      ref={ref}
      className="np-flow"
      style={{ height: `${STEPS.length * 150 + 80}vh`, "--step-color": STEPS[step].color }}
    >
      <div className="np-sticky np-flow-sticky">
        <div className="np-flow-glow" aria-hidden="true" />
        <div className="np-flow-text">
          <span className="np-eyebrow">분석 과정</span>
          <div className="np-flow-count">
            <span>{String(step + 1).padStart(2, "0")}</span> / {String(STEPS.length).padStart(2, "0")}
          </div>
          <div className="np-flow-steps">
            {STEPS.map((s, i) => (
              <div key={s.tool} className={`np-flow-step ${i === step ? "is-active" : ""}`} aria-hidden={i !== step}>
                <span className="np-flow-tool">{s.tool}</span>
                <h2>{s.title}</h2>
                <p>{s.desc}</p>
              </div>
            ))}
          </div>
          <ol className="np-flow-nav">
            {STEPS.map((s, i) => (
              <li key={s.tool} className={i < step ? "is-done" : i === step ? "is-on" : ""}>
                <span className="np-flow-nav-bar">
                  <i />
                </span>
                {s.name}
              </li>
            ))}
          </ol>
        </div>

        <div className="np-flow-stage">
          <PipelineDevice step={step} />
        </div>
      </div>
    </section>
  );
}

// 4. 숫자로 보는 와바바
function NumbersSection() {
  return (
    <section className="np-numbers">
      <SectionHead eyebrow="숫자로 보는 와바바" title="꼼꼼하게, 빠르게" />
      <div className="np-numbers-grid">
        {NUMBERS.map((n, i) => (
          <Reveal key={n.label} className="np-number" delay={i * 120}>
            <span className="np-icon-tile np-number-icon" aria-hidden="true">
              <n.Icon size={22} strokeWidth={2} />
            </span>
            <strong>
              <CountUp to={n.to} suffix={n.suffix} />
            </strong>
            <span className="np-number-label">{n.label}</span>
            <span className="np-number-note">{n.note}</span>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

// 5. 예시 영상: 세로 스크롤이 가로 이동으로 바뀌는 구간 (기존 예시 영상 6개)
function SamplesSection() {
  const trackRef = useRef(null);
  const videoRefs = useRef([]);
  const [hover, setHover] = useState(null);
  const ref = useScrollProgress((p) => {
    const track = trackRef.current;
    if (!track) return;
    const max = Math.max(0, track.scrollWidth - window.innerWidth + 64);
    track.style.transform = `translate3d(${-p * max}px, 0, 0)`;
  });

  // 마우스를 올린 카드만 소리 켜기 (페이지에서 한 번이라도 클릭한 뒤에만 가능)
  useEffect(() => {
    const canSound = navigator.userActivation ? navigator.userActivation.hasBeenActive : true;
    videoRefs.current.forEach((v, i) => {
      if (!v) return;
      v.muted = !(canSound && i === hover);
    });
    setDuck("sample-video", canSound && hover !== null);
  }, [hover]);

  useEffect(() => () => setDuck("sample-video", false), []);

  return (
    <section ref={ref} className="np-samples">
      <div className="np-sticky np-samples-sticky">
        <div className="np-samples-head">
          <span className="np-eyebrow">예시 영상</span>
          <h2 className="np-section-title">
            어떤 방송이든,
            <br />
            터진 순간을 찾아요
          </h2>
          <p className="np-samples-hint">
            <Volume2 size={16} strokeWidth={2} /> 영상에 마우스를 올리면 소리가 나와요
          </p>
        </div>
        <div ref={trackRef} className="np-samples-track">
          {SAMPLES.map((s, i) => (
            <div
              key={s.video}
              className={`np-sample ${hover === i ? "is-hover" : ""}`}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((cur) => (cur === i ? null : cur))}
            >
              <video
                ref={(el) => (videoRefs.current[i] = el)}
                src={s.video}
                muted
                loop
                autoPlay
                playsInline
                preload="metadata"
              />
              <span className="np-sample-num">{String(i + 1).padStart(2, "0")}</span>
              <span className="np-sample-tag">{s.tag}</span>
              <span className="np-sample-sound" aria-hidden="true">{hover === i ? <Volume2 size={15} strokeWidth={2.2} /> : <VolumeX size={15} strokeWidth={2.2} />}</span>
            </div>
          ))}
        </div>
        <div className="np-samples-progress" aria-hidden="true">
          <i />
        </div>
      </div>
    </section>
  );
}

// 6. 기능 카드: 화면 곳곳에 흩어져 기울어 있던 카드들이 스크롤에 맞춰 날아와 격자로 모임
//    (카드 i는 진행도 i*0.1 ~ i*0.1+0.3 구간에서 이동, 제목 둘째 줄은 왼쪽부터 칠해지듯 나타남)
const FEATURE_SCATTER = [
  { sx: "-34vw", sy: "-38vh", sr: "-16deg", sry: "40deg" },
  { sx: "0vw", sy: "-55vh", sr: "10deg", sry: "-30deg" },
  { sx: "34vw", sy: "-36vh", sr: "18deg", sry: "-40deg" },
  { sx: "-38vw", sy: "42vh", sr: "14deg", sry: "35deg" },
  { sx: "0vw", sy: "60vh", sr: "-12deg", sry: "25deg" },
  { sx: "38vw", sy: "40vh", sr: "-18deg", sry: "-35deg" },
];

function FeaturesSection() {
  const [landed, setLanded] = useState(0);
  const ref = useScrollProgress((p) => {
    const n = FEATURES.filter((_, i) => p >= i * 0.1 + 0.3).length;
    setLanded((cur) => (cur === n ? cur : n));
  });

  return (
    <section id="features" ref={ref} className="np-features">
      <div className="np-sticky np-features-sticky">
        <div className="np-head np-head-center np-features-head">
          <span className="np-eyebrow">기능</span>
          <h2 className="np-section-title">
            소리만 큰 순간이 아니라,
            <br />
            <span className="np-features-wipe">
              <span className="np-grad-text">함께 터진 순간</span>을 찾아요
            </span>
          </h2>
          <span className="np-features-count">
            <b>{landed}</b> / {FEATURES.length}
          </span>
        </div>
        <div className="np-features-grid">
          {FEATURES.map((f, i) => (
            <div
              key={f.title}
              className={`np-feature ${i < landed ? "is-landed" : ""}`}
              style={{ "--i": i, "--sx": FEATURE_SCATTER[i].sx, "--sy": FEATURE_SCATTER[i].sy, "--sr": FEATURE_SCATTER[i].sr, "--sry": FEATURE_SCATTER[i].sry }}
            >
              {f.platforms ? (
                <span className="np-feature-platforms">
                  <PlatformRow size={20} showName={false} />
                </span>
              ) : (
                <span className="np-icon-tile np-feature-emoji" aria-hidden="true">
                  <f.Icon size={24} strokeWidth={2} />
                </span>
              )}
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
              <span className="np-feature-fact">{f.fact}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// 7. 결과 화면 미리보기: 기울어진 대시보드가 스크롤에 맞춰 펴지고, 설명 말풍선이 붙음
function ResultSection() {
  const ref = useScrollProgress();
  const W = 480;
  const H = 120;
  return (
    <section id="result" ref={ref} className="np-result">
      <div className="np-sticky np-result-sticky">
        <div className="np-result-head">
          <span className="np-eyebrow">결과 화면</span>
          <h2 className="np-section-title">결과는 한 화면에</h2>
        </div>
        <div className="np-dash-wrap">
          <div className="np-dash">
            <div className="np-dash-score">
              <span className="np-dash-label">와바바 스코어</span>
              <strong>87</strong>
              <span className="np-dash-chip">역대급 방송</span>
            </div>
            <div className="np-dash-player">
              <div className="np-dash-player-art">
                <Mascot mood="excited" size={64} />
                <span className="np-dash-play">▶</span>
              </div>
              <div className="np-dash-player-bar">
                <span className="mono">요약 영상 · 4:32</span>
                <div className="np-dash-chapters">
                  {[22, 14, 26, 18, 20].map((w, i) => (
                    <i key={i} style={{ flexGrow: w }} />
                  ))}
                  <b className="np-dash-playhead" />
                </div>
              </div>
            </div>
            <div className="np-dash-chart">
              <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
                <path className="np-dash-line" d={curvePath(CURVE, W, H)} />
              </svg>
              <span className="np-dash-star" style={{ left: `${(13 / (CURVE.length - 1)) * 100}%` }}>
                <Star size={22} fill="#FFB020" strokeWidth={0} />
              </span>
            </div>
            <div className="np-dash-list">
              {["00:12:40", "00:47:05", "01:22:31"].map((t, i) => (
                <div key={t} className="np-dash-item" style={{ "--i": i }}>
                  <span className="mono">{t}</span>
                  <i />
                  <span className="np-dash-dl">
                    <Download size={16} strokeWidth={2.4} />
                  </span>
                </div>
              ))}
            </div>
          </div>

          <span className="np-callout np-callout-1">방송 전체 분위기를 한 숫자로</span>
          <span className="np-callout np-callout-2">
            <Star size={13} fill="#FFB020" strokeWidth={0} /> 가장 크게 터진 순간
          </span>
          <span className="np-callout np-callout-3">클립마다 바로 내려받기</span>
        </div>
      </div>
    </section>
  );
}

// 8. 바바 소개: 표정을 누르면 가운데에서 커지며 설명이 튀어나옴
function BabaSection() {
  const [sel, setSel] = useState(0);
  const m = BABA_MOODS[sel];

  return (
    <section id="baba" className="np-baba">
      <div className="np-baba-stars" aria-hidden="true" />
      <SectionHead
        dark
        eyebrow="캐릭터"
        title="와바바의 길잡이, 바바"
        sub="시청자 채팅 말풍선 하나가 바바가 됐어요. 표정을 눌러 보세요."
      />

      <div className="np-baba-stage">
        <div className="np-baba-orbit">
          <div className="np-baba-ring">
            {BABA_MOODS.map((b, i) => (
              <button
                key={b.mood}
                type="button"
                className={`np-baba-moon ${i === sel ? "is-sel" : ""}`}
                style={{ "--i": i, "--n": BABA_MOODS.length }}
                onClick={() => setSel(i)}
                aria-pressed={i === sel}
                aria-label={`${b.name} 표정 보기`}
              >
                <span className="np-baba-moon-inner">
                  <Mascot mood={b.mood} size={60} />
                  <em>{b.name}</em>
                </span>
              </button>
            ))}
          </div>
          <div className="np-baba-center" key={m.mood}>
            <span className="np-baba-say">{m.line}</span>
            <Mascot mood={m.mood} size={170} animate />
          </div>
        </div>

        <div className="np-baba-card" key={`card-${m.mood}`} aria-live="polite">
          <span className="np-baba-card-kicker">바바의 표정 {sel + 1} / {BABA_MOODS.length}</span>
          <h3>{m.name}</h3>
          <p className="np-baba-card-desc">{m.desc}</p>
          <dl>
            <div>
              <dt>만나는 곳</dt>
              <dd>
                {m.where.map((w) => (
                  <span key={w} className="np-baba-chip">
                    {w}
                  </span>
                ))}
              </dd>
            </div>
            <div>
              <dt>특징</dt>
              <dd>{m.look}</dd>
            </div>
          </dl>
          <div className="np-baba-card-nav">
            <button type="button" onClick={() => setSel((sel + BABA_MOODS.length - 1) % BABA_MOODS.length)}>
              <ChevronLeft size={16} strokeWidth={2.4} /> 이전
            </button>
            <button type="button" onClick={() => setSel((sel + 1) % BABA_MOODS.length)}>
              다음 <ChevronRight size={16} strokeWidth={2.4} />
            </button>
          </div>
        </div>
      </div>

      <div className="np-baba-info">
        <Reveal className="np-baba-panel">
          <h3>프로필</h3>
          <dl className="np-baba-profile">
            {BABA_PROFILE.map((p) => (
              <div key={p.label}>
                <dt>{p.label}</dt>
                <dd>{p.value}</dd>
              </div>
            ))}
          </dl>
        </Reveal>
        <Reveal className="np-baba-panel" delay={120}>
          <h3>이렇게 생겼어요</h3>
          <ul className="np-baba-looks">
            {BABA_LOOKS.map((l) => (
              <li key={l.part}>
                <span aria-hidden="true">
                  <l.Icon size={22} strokeWidth={2} />
                </span>
                <div>
                  <b>{l.part}</b>
                  <p>{l.desc}</p>
                </div>
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

export default function MainPreview() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setScene("main");
  }, []);

  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (id) setTimeout(() => document.getElementById(id)?.scrollIntoView(), 100);
  }, []);

  const handleSubmit = async (videoUrl) => {
    setError(null);
    setSubmitting(true);
    try {
      const accepted = await startAnalysis(videoUrl);
      addToHistory({ videoId: accepted.video_id, label: videoUrl });
      navigate(`/result/${accepted.video_id}`, { state: { sourceUrl: videoUrl } });
    } catch (e) {
      setSubmitting(false);
      setError(e.message);
    }
  };

  const handleFileSubmit = async (file, cropBox) => {
    setError(null);
    setSubmitting(true);
    try {
      const accepted = await startAnalysisFromFile(file, cropBox);
      addToHistory({ videoId: accepted.video_id, label: file.name });
      const previewUrl = URL.createObjectURL(file);
      navigate(`/result/${accepted.video_id}`, { state: { previewUrl } });
    } catch (e) {
      setSubmitting(false);
      setError(e.message);
    }
  };

  return (
    <div className="np">
      <TopNav />
      <HeroSection />
      <GuideSection />
      <FlowSection />
      <NumbersSection />
      <SamplesSection />
      <FeaturesSection />
      <ResultSection />
      <BabaSection />

      <section id="start" className="np-start">
        <div className="np-start-card">
          <div className="np-start-mascot" aria-hidden="true">
            <Mascot mood="excited" size={96} animate />
          </div>
          <SectionHead eyebrow="시작하기" title="지금 바로 시작해요" sub="영상 파일이나 유튜브 링크 하나면 충분해요." />
          <div className="np-start-platforms">
            <span>
              <PlatformLogo platform="youtube" size={18} /> 링크 · 파일
            </span>
            <span>
              <PlatformLogo platform="chzzk" size={18} />
              <PlatformLogo platform="soop" size={18} /> 다시보기 파일
            </span>
          </div>
          <Reveal className="np-start-form" delay={200}>
            <UploadForm onSubmit={handleSubmit} onFileSubmit={handleFileSubmit} disabled={submitting} />
            {error && (
              <div className="error-banner">
                <TriangleAlert size={16} strokeWidth={2.2} /> {error}
              </div>
            )}
          </Reveal>
        </div>
        <div id="recent-history-section" className="np-start-history">
          <RecentHistory />
        </div>
      </section>

      <Footer />
    </div>
  );
}
