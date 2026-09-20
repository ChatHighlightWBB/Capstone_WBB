import { useParams, useLocation, Link } from "react-router-dom";
import { useEffect, useState, useRef } from "react";
import Sidebar from "../components/Sidebar.jsx";
import Topbar from "../components/Topbar.jsx";
import AnalyzingProgress from "../components/AnalyzingProgress.jsx";
import WbbScore from "../components/WbbScore.jsx";
import EmotionChart from "../components/EmotionChart.jsx";
import HighlightList from "../components/HighlightList.jsx";
import DownloadPanel from "../components/DownloadPanel.jsx";
import { pollResult } from "../api.js";
import { getNotifyOnDone } from "../settingsStorage.js";

export default function Result() {
  const { videoId } = useParams();
  const location = useLocation();
  const { previewUrl, sourceUrl } = location.state || {};
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const videoRef = useRef(null);
  const notifiedRef = useRef(false); // 같은 결과에 알림을 여러 번 안 쏘게 방지

  useEffect(() => {
    const stop = pollResult(videoId, {
      onUpdate: (data, err) => {
        if (err) {
          setError(err.message);
          return;
        }
        setResult(data);

        // [설정 연동] 분석이 막 완료된 시점에만, 켜져 있으면 브라우저 알림을 쏩니다.
        if (
          data.video_info.status === "done" &&
          !notifiedRef.current &&
          getNotifyOnDone() &&
          typeof Notification !== "undefined" &&
          Notification.permission === "granted"
        ) {
          notifiedRef.current = true;
          new Notification("와바바 분석 완료", {
            body: "하이라이트 요약이 준비됐어요. 확인해보세요!",
            icon: "/favicon.ico",
          });
        }
      },
    });
    return stop; // 페이지를 벗어나면 폴링을 멈춥니다.
  }, [videoId]);

  const status = result?.video_info.status;
  const isInProgress = status && status !== "done" && status !== "failed";

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <div className="results">
          <Link to="/" className="back-link">
            <span aria-hidden="true">←</span> 다시 분석하기
          </Link>

          {error && <div className="error-banner">⚠️ {error}</div>}

          {status === "failed" && (
            <div className="status-banner" data-status="failed">
              분석 실패{result.video_info.error && ` — ${result.video_info.error}`}
            </div>
          )}

          {isInProgress && (
            <AnalyzingProgress
              status={status}
              step={result.video_info.step}
              totalSteps={result.video_info.total_steps}
              stepLabel={result.video_info.step_label}
              previewUrl={previewUrl}
              sourceUrl={sourceUrl}
            />
          )}

          {!result && !error && (
            <AnalyzingProgress status="queued" previewUrl={previewUrl} sourceUrl={sourceUrl} />
          )}

          {result?.highlight_result && (
            <div id="score-section">
              <WbbScore highlights={result.highlight_result.highlights} />
            </div>
          )}
          {result?.final_video_url && (
            <div id="video-section">
              <video ref={videoRef} className="highlight-video" src={result.final_video_url} controls />
            </div>
          )}
          {(result?.final_video_url || result?.highlight_result) && (
            <div id="download-section">
              <DownloadPanel
                finalVideoUrl={result.final_video_url}
                highlights={result.highlight_result?.highlights}
              />
            </div>
          )}
          {result?.emotion_timeseries && (
            <div id="chart-section">
              <EmotionChart
                timeSeriesData={result.emotion_timeseries.time_series_data}
                recommendedJoyThreshold={result.emotion_timeseries.recommended_joy_threshold}
              />
            </div>
          )}
          {result?.highlight_result && (
            <div id="highlight-section">
              <HighlightList
                highlights={result.highlight_result.highlights}
                timeSeriesData={result.emotion_timeseries?.time_series_data}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}