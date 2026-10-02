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
import BabaSays from "../components/BabaSays.jsx";

// 분석은 끝났지만 하이라이트가 0개일 때 (서버가 metadata.empty_reason으로 이유를 알려줌)
const EMPTY_HIGHLIGHT_MESSAGE = {
  no_chats:
    "채팅을 인식하지 못해 하이라이트를 만들 수 없어요. 채팅창이 화면에 보이는 영상인지 확인하거나, 파일 업로드에서 채팅 영역을 직접 지정해 다시 시도해보세요.",
  no_candidates:
    "채팅은 인식했지만 반응이 두드러진 구간을 찾지 못해 하이라이트를 만들지 않았어요.",
};

// 결과가 나왔을 때 바바의 한마디 (와바바 스코어 등급과 같은 기준: WbbScore.jsx)
function babaReaction(highlights) {
  const count = highlights.length;
  const avg = highlights.reduce((sum, h) => sum + h.final_highlight_score, 0) / count;
  const score = Math.round(avg);
  if (score >= 80)
    return { mood: "excited", text: `역대급 방송이에요! 하이라이트 ${count}개를 찾았어요. 감정 그래프의 ⭐ 와바바 포인트부터 확인해 보세요.` };
  if (score >= 60)
    return { mood: "excited", text: `재밌는 장면이 많았어요! 하이라이트 ${count}개를 골랐어요.` };
  if (score >= 40)
    return { mood: "happy", text: `잔잔한 방송이지만 반응이 모인 구간 ${count}개를 찾았어요.` };
  return { mood: "happy", text: `차분한 방송이었어요. 그래도 시청자가 반응한 구간 ${count}개를 골랐어요.` };
}

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
    return stop; // 페이지를 벗어나면 폴링을 멈춥니다.
  }, [videoId]);

  const status = result?.video_info.status;
  const isInProgress = status && status !== "done" && status !== "failed";
  const hasNoHighlights = status === "done" && !result.highlight_result?.highlights?.length;
  const emptyReason = result?.highlight_result?.metadata?.empty_reason;
  const highlights = result?.highlight_result?.highlights;
  const reaction = status === "done" && highlights?.length ? babaReaction(highlights) : null;

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

          {(error || status === "failed") && (
            <BabaSays mood="oops" className="result-baba">
              분석 중에 문제가 생겼어요. <Link to="/help">오류 대처 방법</Link>에서 화면에 뜬 문구와
              비슷한 항목을 찾아보세요.
            </BabaSays>
          )}

          {status === "failed" && (
            <div className="status-banner" data-status="failed">
              분석 실패{result.video_info.error && ` — ${result.video_info.error}`}
            </div>
          )}

          {hasNoHighlights && (
            <BabaSays mood="thinking" className="result-baba">
              {EMPTY_HIGHLIGHT_MESSAGE[emptyReason] ?? "하이라이트로 만들 구간을 찾지 못했어요."}
            </BabaSays>
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
              {reaction && (
                <BabaSays mood={reaction.mood} className="result-baba">
                  {reaction.text}
                  <span className="baba-says-sub">
                    결과는 4시간 뒤 사라져요. 필요한 영상은 아래 다운로드에서 받아 두세요.
                  </span>
                </BabaSays>
              )}
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