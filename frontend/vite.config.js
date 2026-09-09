import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 백엔드(FastAPI, 기본 8000포트)로의 CORS 이슈를 피하기 위해 개발 서버에 프록시를 걸어둡니다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/files": "http://localhost:8000",
    },
  },
});
