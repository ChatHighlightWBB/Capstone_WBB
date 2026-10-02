import { useState } from "react";

export default function UploadForm({ onSubmit, onFileSubmit, disabled }) {
  const [url, setUrl] = useState("");

  const handleUrlSubmit = (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim());
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) onFileSubmit(file);
  };

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

      <label className="upload-file-label">
        📁 영상 파일 직접 업로드
        <input
          type="file"
          accept="video/*"
          onChange={handleFileChange}
          disabled={disabled}
          hidden
        />
      </label>
    </div>
  );
}