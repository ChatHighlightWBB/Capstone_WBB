import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar.jsx";
import Topbar from "../components/Topbar.jsx";
import Hero from "../components/Hero.jsx";
import RecentHistory from "../components/RecentHistory.jsx";
import HowItWorks from "../components/HowItWorks.jsx";
import Features from "../components/Features.jsx";
import Footer from "../components/Footer.jsx";
import { startAnalysis, startAnalysisFromFile } from "../api.js";
import { addToHistory } from "../history.js";

export default function Home() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Result 페이지 등 다른 곳에서 "/#how" 처럼 해시를 달고 들어온 경우,
  // 페이지가 그려진 뒤 해당 위치로 스크롤합니다.
  useEffect(() => {
    if (window.location.hash) {
      const id = window.location.hash.slice(1);
      setTimeout(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    }
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

  const handleFileSubmit = async (file) => {
    setError(null);
    setSubmitting(true);
    try {
      const accepted = await startAnalysisFromFile(file);
      addToHistory({ videoId: accepted.video_id, label: file.name });
      // 방금 고른 파일은 서버 왕복 없이 브라우저에서 바로 재생할 수 있습니다.
      const previewUrl = URL.createObjectURL(file);
      navigate(`/result/${accepted.video_id}`, { state: { previewUrl } });
    } catch (e) {
      setSubmitting(false);
      setError(e.message);
    }
  };

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />
        <Hero onSubmit={handleSubmit} onFileSubmit={handleFileSubmit} disabled={submitting} />
        {error && (
          <div className="results">
            <div className="error-banner">⚠️ {error}</div>
          </div>
        )}
        <div id="recent-history-section">
          <RecentHistory />
        </div>
        <HowItWorks />
        <Features />
        <Footer />
      </main>
    </div>
  );
}