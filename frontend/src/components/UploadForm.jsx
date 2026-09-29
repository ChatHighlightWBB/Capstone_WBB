import { useEffect, useRef, useState } from "react";
import CropBoxSelector from "./CropBoxSelector.jsx";
import { captureVideoFrame } from "../videoFrame.js";
import { getCropBoxSetting, setCropBoxSetting } from "../settingsStorage.js";

// 처음엔 영상 10% 지점, "다른 장면 보기"는 인트로/엔딩을 피해 20~80% 사이에서 무작위로 고릅니다.
const pickFirstFrame = (duration) => duration * 0.1;
const pickRandomFrame = (duration) => duration * (0.2 + Math.random() * 0.6);

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function UploadForm({ onSubmit, onFileSubmit, disabled }) {
  const [url, setUrl] = useState("");

  // 파일을 고르면 바로 업로드하지 않고, 한 장면을 보여주며 채팅창 위치를 먼저 확인받습니다.
  const [selectedFile, setSelectedFile] = useState(null);
  const [frame, setFrame] = useState(null); // { url, time } — 미리보기 장면 (Blob URL)
  const [frameStatus, setFrameStatus] = useState("idle"); // idle | loading | ready | error
  const [cropBox, setCropBox] = useState(null); // {top,left,bottom,right} 0~1 비율, 이번 업로드에만 사용
  const [saveAsDefault, setSaveAsDefault] = useState(false);
  const frameRequestRef = useRef(0); // 늦게 끝난 이전 추출이 새 장면을 덮어쓰지 않게

  // 장면이 바뀌거나 화면을 떠날 때 이전 Blob URL을 해제합니다.
  useEffect(() => {
    return () => {
      if (frame) URL.revokeObjectURL(frame.url);
    };
  }, [frame]);

  const loadFrame = async (file, pickTime) => {
    const requestId = ++frameRequestRef.current;
    setFrameStatus("loading");
    try {
      const { blob, time } = await captureVideoFrame(file, pickTime);
      if (requestId !== frameRequestRef.current) return;
      setFrame({ url: URL.createObjectURL(blob), time });
      setFrameStatus("ready");
    } catch {
      if (requestId !== frameRequestRef.current) return;
      setFrame(null);
      setFrameStatus("error");
    }
  };

  const handleUrlSubmit = (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim());
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // 같은 파일을 다시 골라도 onChange가 오도록 초기화
    if (!file) return;
    setSelectedFile(file);
    setFrame(null); // 이전 파일의 장면/드래그 사각형이 남지 않게
    setCropBox(getCropBoxSetting()); // 설정 페이지에 저장된 위치가 있으면 그걸로 시작
    setSaveAsDefault(false);
    loadFrame(file, pickFirstFrame);
  };

  // crop_box 없이 보내면 서버가 Auto-ROI(또는 .env의 CHAT_CROP_BOX)로 찾습니다.
  const startWithAutoDetect = () => onFileSubmit(selectedFile, null);

  const startWithCropBox = () => {
    if (!cropBox) return;
    if (saveAsDefault) setCropBoxSetting(cropBox);
    onFileSubmit(selectedFile, [cropBox.top, cropBox.left, cropBox.bottom, cropBox.right]);
  };

  const canPreview = frameStatus !== "error";

  return (
    <div className="upload-wrap">
      <form className="upload-form" onSubmit={handleUrlSubmit}>
        <input
          id="url-input"
          type="url"
          placeholder="유튜브, 치지직, SOOP TV 링크를 붙여넣으세요"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={disabled}
        />
        <button type="submit" disabled={disabled}>
          {disabled ? "분석 중..." : "하이라이트 요약 시작"}
        </button>
      </form>

      <div className="upload-divider">또는</div>

      <input
        id="upload-file-input"
        type="file"
        accept="video/*"
        onChange={handleFileChange}
        disabled={disabled}
        hidden
      />

      {!selectedFile ? (
        <label htmlFor="upload-file-input" className="upload-file-label">
          📁 영상 파일 직접 업로드
        </label>
      ) : (
        <div className="upload-preview">
          <div className="upload-preview-head">
            <span className="upload-preview-name" title={selectedFile.name}>
              🎞️ {selectedFile.name}
            </span>
            <label htmlFor="upload-file-input" className="upload-text-btn">
              다른 파일 선택
            </label>
          </div>

          {frameStatus === "loading" && !frame && (
            <p className="upload-preview-msg">장면을 불러오는 중...</p>
          )}

          {!canPreview && (
            <p className="upload-preview-msg">
              이 브라우저에서는 영상 미리보기를 열 수 없어요. 채팅창 위치는 자동으로
              찾아서 분석할게요.
            </p>
          )}

          {canPreview && frame && (
            <>
              <CropBoxSelector imageSrc={frame.url} initialBox={cropBox} onChange={setCropBox} />
              <p className="upload-preview-msg">
                {formatTime(frame.time)} 지점 장면
                {frameStatus === "loading" && " · 다른 장면 불러오는 중..."}
                {!cropBox && " · 채팅창 영역을 드래그로 지정하면 그 영역으로 분석할 수 있어요."}
              </p>
              <label className="upload-preview-save">
                <input
                  type="checkbox"
                  checked={saveAsDefault}
                  onChange={(e) => setSaveAsDefault(e.target.checked)}
                  disabled={disabled}
                />
                이 위치를 기본값으로 저장
              </label>
            </>
          )}

          <div className="upload-preview-actions">
            {canPreview && (
              <button
                type="button"
                className="upload-btn-secondary"
                onClick={() => loadFrame(selectedFile, pickRandomFrame)}
                disabled={disabled || frameStatus === "loading"}
              >
                다른 장면 보기
              </button>
            )}
            <button
              type="button"
              className="upload-btn-secondary"
              onClick={startWithAutoDetect}
              disabled={disabled}
            >
              자동 탐지로 분석
            </button>
            {canPreview && (
              <button
                type="button"
                className="upload-btn-primary"
                onClick={startWithCropBox}
                disabled={disabled || !frame || !cropBox}
              >
                {disabled ? "분석 요청 중..." : "이 영역으로 분석 시작"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
