import { useRef, useState } from "react";
import Navbar from "./components/Navbar.jsx";
import Hero from "./components/Hero.jsx";
import HowItWorks from "./components/HowItWorks.jsx";
import Features from "./components/Features.jsx";
import WbbScore from "./components/WbbScore.jsx";
import EmotionChart from "./components/EmotionChart.jsx";
import HighlightList from "./components/HighlightList.jsx";
import { startAnalysis, pollResult } from "./api.js";

const STATUS_LABEL = {
  queued: "대기 중...",
  downloading: "영상 스트림 다운로드 중 (프록시 360p)...",
  analyzing: "OCR·KoBERT·멀티모달 분석 중... (수 분 소요될 수 있습니다)",
  done: "분석 완료",
  failed: "분석 실패",
};

export default function App() {
  const [result, setResult] = useState(null); // AnalyzeResultResponse
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const videoRef = useRef(null);

  const isBusy =
    submitting ||
    (result && !["done", "failed"].includes(result.video_info.status));

  const handleSubmit = async (videoUrl) => {
    setError(null);
    setResult(null);
    setSubmitting(true);

    // 제출하는 순간 결과 화면(로딩 상태)으로 바로 전환
    setTimeout(() => {
      document.getElementById("result")?.scrollIntoView({ behavior: "smooth" });
    }, 100);

    try {
      const accepted = await startAnalysis(videoUrl);
      setSubmitting(false);
      pollResult(accepted.video_id, {
        onUpdate: (data, err) => {
          if (err) {
            setError(err.message);
            return;
          }
          setResult(data);
        },
      });
    } catch (e) {
      setSubmitting(false);
      setError(e.message);
    }
  };

  const handleSeek = (startTimeSec) => {
    if (videoRef.current) {
      videoRef.current.currentTime = startTimeSec;
      videoRef.current.play();
    }
  };

  const currentStatus = result?.video_info.status ?? (submitting ? "queued" : null);

  return (
    <div className="app">
      <Navbar />
      <Hero onSubmit={handleSubmit} disabled={isBusy} />
      <HowItWorks />
      <Features />

      <main id="result" className="results">
        {error && <div className="error-banner">⚠️ {error}</div>}

        {currentStatus && (
          <div className="status-banner" data-status={currentStatus}>
            {STATUS_LABEL[currentStatus] ?? currentStatus}
            {result?.video_info.error && ` — ${result.video_info.error}`}
          </div>
        )}

        {result?.highlight_result && (
          <WbbScore highlights={result.highlight_result.highlights} />
        )}

        {result?.final_video_url && (
          <video
            ref={videoRef}
            className="highlight-video"
            src={result.final_video_url}
            controls
          />
        )}

        {result?.emotion_timeseries && (
          <EmotionChart
            timeSeriesData={result.emotion_timeseries.time_series_data}
            recommendedJoyThreshold={result.emotion_timeseries.recommended_joy_threshold}
          />
        )}

        {result?.highlight_result && (
          <HighlightList
            highlights={result.highlight_result.highlights}
            onSeek={handleSeek}
          />
        )}
      </main>
    </div>
  );
}