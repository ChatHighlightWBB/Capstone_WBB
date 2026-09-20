import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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

// 다른 곳(다른 브라우저, 공유받은 링크 등)에서 받은 video_id로 바로 이동할 때 씁니다.
function QuickJump() {
  const navigate = useNavigate();
  const [videoId, setVideoId] = useState("");
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const id = videoId.trim();
    if (!id) return;
    setError(null);
    try {
      await getResult(id); // 존재하는 결과인지 먼저 확인
      navigate(`/result/${id}`);
    } catch {
      setError("해당 ID의 결과를 찾을 수 없어요. (만료됐거나 잘못된 ID일 수 있어요)");
    }
  };

  return (
    <form className="quick-jump" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="video_id를 붙여넣으면 결과 페이지로 바로 이동해요"
        value={videoId}
        onChange={(e) => setVideoId(e.target.value)}
      />
      <button type="submit">바로가기</button>
      {error && <p className="quick-jump-error">{error}</p>}
    </form>
  );
}

export default function RecentHistory() {
  const [items, setItems] = useState(() => getHistory());
  const [checked, setChecked] = useState(false); // 서버 재확인이 끝났는지 (깜빡임 방지)

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
            removeFromHistory(item.videoId);
            return null;
          }
        })
      );
      if (!cancelled) {
        setItems(results.filter(Boolean));
        setChecked(true);
      }
    }

    if (getHistory().length > 0) {
      checkAll();
    } else {
      setChecked(true);
    }

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="recent-history">
      <h2>최근 내 분석 내역</h2>
      <p className="section-sub">이 브라우저에서 최근 4시간 안에 요청한 것만 보여요.</p>

      {items.length > 0 ? (
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
      ) : (
        checked && (
          <div className="recent-history-empty">
            <span className="recent-history-empty-icon">📭</span>
            <p>아직 이 브라우저에서 분석한 내역이 없어요.</p>
          </div>
        )
      )}

      <QuickJump />
    </section>
  );
}