import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import Topbar from "../components/Topbar.jsx";
import CropBoxSelector from "../components/CropBoxSelector.jsx";
import { getInitialTheme, applyTheme } from "../theme.js";
import { getServerInfo } from "../api.js";
import {
  getCropBoxSetting,
  setCropBoxSetting,
  getNotifyOnDone,
  setNotifyOnDone,
} from "../settingsStorage.js";

const THEME_OPTIONS = [
  { value: "light", label: "라이트 모드", icon: "☀️", desc: "밝은 배경, 기본 테마" },
  { value: "dark", label: "다크 모드", icon: "🌙", desc: "어두운 배경, 눈 편한 테마" },
];

const DEFAULT_CROP_BOX = { top: 0.15, left: 0.65, bottom: 0.6, right: 0.98 };

export default function Settings() {
  const [theme, setTheme] = useState(getInitialTheme());
  const [cropBox, setCropBox] = useState(getCropBoxSetting());
  const [previewImage, setPreviewImage] = useState(null);
  const [retentionHours, setRetentionHours] = useState(null);
  const [notifyEnabled, setNotifyEnabled] = useState(getNotifyOnDone());
  const [notifyPermission, setNotifyPermission] = useState(
    typeof Notification !== "undefined" ? Notification.permission : "unsupported"
  );

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    getServerInfo()
      .then((info) => setRetentionHours(info.retention_hours))
      .catch(() => setRetentionHours(null)); // 서버 꺼져있어도 설정 화면 자체는 보이게
  }, []);

  const selectTheme = (value) => {
    setTheme(value);
    applyTheme(value);
    window.dispatchEvent(new Event("wbb-theme-change"));
  };

  const cropValues = cropBox || DEFAULT_CROP_BOX;
  const isCustomCropBox = !!cropBox;

  const updateCropField = (field, value) => {
    const next = { ...cropValues, [field]: value };
    setCropBox(next);
    setCropBoxSetting(next);
  };

  const resetCropBox = () => {
    setCropBox(null);
    setCropBoxSetting(null);
  };

  const handleImagePick = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setPreviewImage(reader.result);
    reader.readAsDataURL(file);
  };

  const toggleNotify = async () => {
    if (!notifyEnabled) {
      if (typeof Notification === "undefined") return;
      const permission = await Notification.requestPermission();
      setNotifyPermission(permission);
      if (permission !== "granted") return; // 거부하면 켜지지 않음
    }
    const next = !notifyEnabled;
    setNotifyEnabled(next);
    setNotifyOnDone(next);
  };

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <div className="results">
          <h1 className="settings-title">설정</h1>
          <p className="section-sub" style={{ textAlign: "left", marginBottom: 32 }}>
            와바바를 사용하는 방식을 취향에 맞게 바꿔보세요.
          </p>

          {/* ===== 화면 테마 ===== */}
          <section className="settings-section">
            <h2>화면 테마</h2>
            <div className="theme-option-grid">
              {THEME_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`theme-option-card ${theme === opt.value ? "selected" : ""}`}
                  onClick={() => selectTheme(opt.value)}
                >
                  <span className="theme-option-icon">{opt.icon}</span>
                  <span className="theme-option-label">{opt.label}</span>
                  <span className="theme-option-desc">{opt.desc}</span>
                  {theme === opt.value && <span className="theme-option-check">✓ 사용 중</span>}
                </button>
              ))}
            </div>
          </section>

          {/* ===== 채팅창 위치 수동 조정 ===== */}
          <section className="settings-section">
            <h2>채팅창 위치 (고급)</h2>
            <p className="settings-desc">
              평소엔 자동으로 채팅창 위치를 찾아요(Auto-ROI). 특정 방송에서 위치를 잘못
              잡을 때만, 방송 화면 스크린샷을 올려서 채팅창 영역을 직접 드래그로
              지정할 수 있어요. 다음 분석부터 그 위치를 고정해서 씁니다.
            </p>

            <label className="settings-file-btn">
              📷 방송 화면 스크린샷 올리기
              <input type="file" accept="image/*" onChange={handleImagePick} hidden />
            </label>

            {previewImage && (
              <CropBoxSelector
                imageSrc={previewImage}
                initialBox={cropValues}
                onChange={(box) => {
                  setCropBox(box);
                  setCropBoxSetting(box);
                }}
              />
            )}

            <div className="cropbox-grid">
              {[
                { field: "top", label: "위쪽 경계" },
                { field: "left", label: "왼쪽 경계" },
                { field: "bottom", label: "아래쪽 경계" },
                { field: "right", label: "오른쪽 경계" },
              ].map(({ field, label }) => (
                <label key={field} className="cropbox-field">
                  {label}
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={cropValues[field]}
                    onChange={(e) => updateCropField(field, parseFloat(e.target.value) || 0)}
                  />
                </label>
              ))}
            </div>
            <p className="settings-desc" style={{ marginTop: 6 }}>
              위 숫자는 드래그한 영역이 자동으로 채워져요. 미세 조정하고 싶으면 직접 입력해도 돼요.
            </p>

            <div className="settings-inline-actions">
              <span className={`cropbox-status ${isCustomCropBox ? "active" : ""}`}>
                {isCustomCropBox ? "🔧 수동 좌표 사용 중" : "🤖 자동 탐지(Auto-ROI) 사용 중"}
              </span>
              {isCustomCropBox && (
                <button type="button" className="settings-text-btn" onClick={resetCropBox}>
                  자동 탐지로 되돌리기
                </button>
              )}
            </div>
          </section>

          {/* ===== 보관 기간 안내 ===== */}
          <section className="settings-section">
            <h2>데이터 보관 기간</h2>
            <p className="settings-desc">
              로그인 없이 사용하는 서비스라, 분석 결과(영상·그래프·채팅 기록)는{" "}
              <strong>
                {retentionHours != null ? `${retentionHours}시간` : "설정된 시간"}
              </strong>{" "}
              후 서버에서 자동으로 삭제돼요. "최근 내역"에서 다시 보고 싶다면 그 전에
              다운로드해두세요.
            </p>
          </section>

          {/* ===== 언어 (준비 중) ===== */}
          <section className="settings-section">
            <h2>언어</h2>
            <div className="language-option-list">
              <div className="language-option selected">
                한국어 <span className="settings-badge">사용 중</span>
              </div>
              <div className="language-option disabled">
                English <span className="settings-badge">준비 중</span>
              </div>
            </div>
          </section>

          {/* ===== 알림 ===== */}
          <section className="settings-section">
            <h2>알림</h2>
            <div className="settings-toggle-row">
              <div>
                <div className="settings-toggle-label">분석 완료 시 브라우저 알림</div>
                <p className="settings-desc" style={{ margin: "2px 0 0" }}>
                  분석이 몇 분 걸릴 수 있어서, 다른 탭을 보고 있어도 완료되면 알려드려요.
                </p>
              </div>
              <button
                type="button"
                className={`settings-switch ${notifyEnabled ? "on" : ""}`}
                onClick={toggleNotify}
                aria-pressed={notifyEnabled}
              >
                <span className="settings-switch-knob" />
              </button>
            </div>
            {notifyPermission === "denied" && (
              <p className="settings-desc" style={{ color: "var(--yt-red)" }}>
                브라우저 알림 권한이 차단되어 있어요. 브라우저 설정에서 이 사이트의
                알림을 허용해주세요.
              </p>
            )}
            {notifyPermission === "unsupported" && (
              <p className="settings-desc">이 브라우저는 알림 기능을 지원하지 않아요.</p>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}