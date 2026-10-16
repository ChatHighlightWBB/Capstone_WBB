import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { AudioLines, Music, Volume2, VolumeX } from "lucide-react";
import {
  subscribe,
  setScene,
  unlock,
  sfx,
  setBgmEnabled,
  setBgmVolume,
  setSfxEnabled,
  setSfxVolume,
} from "../sound.js";
import "./SoundControls.css";

export function useSoundState() {
  const [s, setS] = useState(null);
  useEffect(() => subscribe(setS), []);
  return s;
}

// 소리 패널의 한 줄: [켜기/끄기 아이콘] 이름 ────●──── 45%
function SoundRow({ Icon, label, enabled, onToggle, volume, onVolume, onCommit, note }) {
  const percent = Math.round(volume * 100);
  return (
    <div className={`sound-row ${enabled ? "" : "is-muted"}`}>
      <div className="sound-row-head">
        <button
          type="button"
          className={`sound-row-toggle ${enabled ? "" : "is-off"}`}
          onClick={onToggle}
          aria-pressed={enabled}
          aria-label={enabled ? `${label} 끄기` : `${label} 켜기`}
          title={enabled ? `${label} 끄기` : `${label} 켜기`}
        >
          <Icon size={17} strokeWidth={2} />
        </button>
        <span className="sound-row-label">{label}</span>
        <span className="sound-row-value mono">{enabled ? `${percent}%` : "꺼짐"}</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        step="1"
        value={percent}
        disabled={!enabled}
        onChange={(e) => onVolume(Number(e.target.value) / 100)}
        onPointerUp={onCommit}
        onKeyUp={onCommit}
        aria-label={`${label} 볼륨`}
        style={{ "--v": `${percent}%` }}
      />
      {note && <p className="sound-row-note">{note}</p>}
    </div>
  );
}

// 스피커 버튼 + 누르면 열리는 소리 패널 (배경음악·효과음 각각 켜기/끄기와 볼륨)
// placement: "down"(상단 메뉴) | "up"(화면 아래쪽에 붙은 버튼)
export function SoundMenu({ className = "", placement = "down" }) {
  const s = useSoundState();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // 바깥을 누르거나 Esc를 누르면 닫기
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!s) return null;
  const allOff = (!s.bgm || s.bgmVolume === 0) && (!s.sfx || s.sfxVolume === 0);

  return (
    <div className={`sound-menu sound-menu-${placement}`} ref={ref}>
      <button
        type="button"
        className={`${className} sound-btn ${s.playing ? "is-playing" : ""}`}
        onClick={() => {
          unlock(); // 이 클릭으로 브라우저가 소리를 허락 → 켜짐 설정이면 배경음 시작
          setOpen((o) => !o);
        }}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="소리 설정"
        title="소리 설정"
      >
        {allOff ? <VolumeX size={18} strokeWidth={2} /> : <Volume2 size={18} strokeWidth={2} />}
      </button>

      {open && (
        <div className="sound-panel" role="dialog" aria-label="소리 설정">
          <div className="sound-panel-title">소리 설정</div>
          <SoundRow
            Icon={Music}
            label="배경음악"
            enabled={s.bgm}
            onToggle={() => setBgmEnabled(!s.bgm)}
            volume={s.bgmVolume}
            onVolume={setBgmVolume}
            note={!s.hasTrack ? "결과 화면에서는 배경음악이 나오지 않아요." : null}
          />
          <SoundRow
            Icon={AudioLines}
            label="효과음"
            enabled={s.sfx}
            onToggle={() => setSfxEnabled(!s.sfx)}
            volume={s.sfxVolume}
            onVolume={setSfxVolume}
            onCommit={() => sfx("blip")} // 손을 떼면 바뀐 크기로 미리 듣기
          />
        </div>
      )}
    </div>
  );
}

// 상단 메뉴가 없는 화면(설정·도움말·약관 등)용: 오른쪽 아래에 떠 있는 소리 버튼
// 이 화면들은 스스로 배경음 종류를 정하지 않으므로, 여기서 메인 곡으로 돌려놓음
// (입장·메인·분석/결과 화면은 각자 소리를 관리하고 상단 메뉴에 소리 버튼이 있음)
export function FloatingSound() {
  const { pathname } = useLocation();
  const managed = pathname === "/" || pathname === "/main" || pathname.startsWith("/result/");

  useEffect(() => {
    if (!managed) setScene("main");
  }, [pathname, managed]);

  if (managed) return null;
  return (
    <div className="sound-floating">
      <SoundMenu className="sound-floating-btn" placement="up" />
    </div>
  );
}
