import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar.jsx";
import Hero from "../components/Hero.jsx";
import RecentHistory from "../components/RecentHistory.jsx";
import HowItWorks from "../components/HowItWorks.jsx";
import Features from "../components/Features.jsx";
import { startAnalysis, startAnalysisFromFile } from "../api.js";
import { addToHistory } from "../history.js";

export default function Home() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (videoUrl) => {
    setError(null);
    setSubmitting(true);
    try {
      const accepted = await startAnalysis(videoUrl);
      addToHistory({ videoId: accepted.video_id, label: videoUrl });
      navigate(`/result/${accepted.video_id}`);
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
      navigate(`/result/${accepted.video_id}`);
    } catch (e) {
      setSubmitting(false);
      setError(e.message);
    }
  };

  return (
    <div className="app">
      <Navbar />
      <Hero onSubmit={handleSubmit} onFileSubmit={handleFileSubmit} disabled={submitting} />
      {error && (
        <div className="results">
          <div className="error-banner">⚠️ {error}</div>
        </div>
      )}
      <RecentHistory />
      <HowItWorks />
      <Features />
    </div>
  );
}