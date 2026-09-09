import { useParams, Link } from "react-router-dom";
import { useState, useRef } from "react";
import Navbar from "../components/Navbar.jsx";
import WbbScore from "../components/WbbScore.jsx";
import EmotionChart from "../components/EmotionChart.jsx";
import HighlightList from "../components/HighlightList.jsx";
import { pollResult } from "../api.js";

export default function Result() {
  const { videoId } = useParams();
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const videoRef = useRef(null);

  useState(() => {
    pollResult(videoId, {
      onUpdate: (data, err) => {
        if (err) setError(err.message);
        else setResult(data);
      },
    });
  }, [videoId]);

  return (
    <div className="app">
      <Navbar />
      <main className="results" style={{ paddingTop: 48 }}>
        <Link to="/" className="mono">← 다시 분석하기</Link>

        {error && <div className="error-banner">⚠️ {error}</div>}
        {!result && <div className="status-banner">분석 중...</div>}

        {result?.highlight_result && (
          <WbbScore highlights={result.highlight_result.highlights} />
        )}
        {result?.final_video_url && (
          <video ref={videoRef} className="highlight-video" src={result.final_video_url} controls />
        )}
        {result?.emotion_timeseries && (
          <EmotionChart
            timeSeriesData={result.emotion_timeseries.time_series_data}
            recommendedJoyThreshold={result.emotion_timeseries.recommended_joy_threshold}
          />
        )}
        {result?.highlight_result && (
          <HighlightList highlights={result.highlight_result.highlights} />
        )}
      </main>
    </div>
  );
}