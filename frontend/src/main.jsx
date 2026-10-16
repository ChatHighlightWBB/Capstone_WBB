import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Entry from "./pages/Entry.jsx";
import MainPreview from "./pages/MainPreview.jsx";
import ResultPreview from "./pages/ResultPreview.jsx";
import Settings from "./pages/Settings.jsx";
import Legal from "./pages/Legal.jsx";
import Help from "./pages/Help.jsx";
import { FloatingSound } from "./components/SoundControls.jsx";
import "./App.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <FloatingSound />
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route path="/main" element={<MainPreview />} />
        {/* 분석 중·결과 화면 (/result/demo 는 서버 없이 보는 예시 화면) */}
        <Route path="/result/:videoId" element={<ResultPreview />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/terms" element={<Legal type="terms" />} />
        <Route path="/privacy" element={<Legal type="privacy" />} />
        <Route path="/help" element={<Help />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);