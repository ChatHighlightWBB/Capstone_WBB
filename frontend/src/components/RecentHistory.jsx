import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getHistory, removeFromHistory } from "../history.js";
import { getResult } from "../api.js";

function timeAgo(createdAt) {
  const diffMin = Math.floor((Date.now() - createdAt) / 60000);
  if (diffMin < 1) return "방금 전";
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHour = Math.floor(diffMin / 60);
  return `${diffHour}시간 전`;
}

const STATUS_TEXT = {
  queued: "대기 중",
  downloading: "다운로드 중",
  analyzing: "분석 중",
  done: "완료",
  failed: "실패",
};

export default function RecentHistory() {
  const [items, setItems] = useState(() => getHistory());

  // 각 항목이 서버에 아직 살아있는지(4시간 자동 삭제 전인지) 확인하고,
  // 상태(분석 중/완료 등)도 최신으로 갱신합니다.
  useEffect(() => {
    let cancelled = false;

    async function checkAll() {
      const current = getHistory();
      const results = await Promise.all(
        current.map(async (item) => {
          try {
            const data = await getResult(item.videoId);
            return { ...item, status: data.video_info.status };
          } catch {
            // 서버에 없음 = 4시간 지나 자동 삭제됨 → 내 목록에서도 제거
            removeFromHistory(item.videoId);
            return null;
          }
        })
      );
      if (!cancelled) {
        setItems(results.filter(Boolean));
      }
    }

    if (getHistory().length > 0) {
      checkAll();
    }

    return () => {
      cancelled = true;
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <section className="recent-history">
      <h2>최근 내 분석 내역</h2>
      <p className="section-sub">이 브라우저에서 최근 4시간 안에 요청한 것만 보여요.</p>

      <ul className="recent-history-list">
        {items.map((item) => (
          <li key={item.videoId}>
            <Link to={`/result/${item.videoId}`} className="recent-history-item">
              <span className="recent-history-label">{item.label}</span>
              <span className="recent-history-meta">
                <span className={`recent-history-status status-${item.status}`}>
                  {STATUS_TEXT[item.status] ?? item.status ?? "확인 중"}
                </span>
                <span className="mono">{timeAgo(item.createdAt)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}