const SAMPLE_CHATS = [
  { nick: "사사임", nickColor: "#8c6fff", text: "?" },
  { nick: "따마커", nickColor: "#ff8a3d", text: "ㅋㅋㅋㅋㅋㅋㅋㅋㅋ" },
  { nick: "아리사왜봄", nickColor: "#00c875", text: "딜이 안들어가" },
  { nick: "천하태평 겜돌이", nickColor: "#0182ff", text: "그걸 거기다쓰면.." },
  { nick: "soltis", nickColor: "#ff3b30", text: "실드있죠" },
  { nick: "이야쌤", nickColor: "#8c6fff", text: "8" },
  { nick: "헤으에응", nickColor: "#ff8a3d", text: "실망스럽다 리사야" },
  { nick: "커정", nickColor: "#00c875", text: "평~생" },
  { nick: "삼겹살2줄반", nickColor: "#0182ff", text: "펴ㅕㅕ평생" },
  { nick: "페아르", nickColor: "#ff3b30", text: "아직스 어게인" },
  { nick: "쥐눈이콩", nickColor: "#8c6fff", text: "쉴드가 있잖아 리사야" },
  { nick: "아보카도맛있다", nickColor: "#ff8a3d", text: "..." },
];

// 실제 채팅 로그를 그대로 재현하지 않고, 흔히 나오는 스트리밍 채팅 패턴으로
// 재구성한 예시 문구입니다. 위에서 아래로 끊임없이 흐르는 느낌만 재현합니다.
export default function LiveChatDecor() {
  const loopChats = [...SAMPLE_CHATS, ...SAMPLE_CHATS];

  return (
    <div className="chat-decor" aria-hidden="true">
      <div className="chat-decor-track">
        {loopChats.map((c, i) => (
          <div key={i} className="chat-decor-line">
            <span className="chat-decor-nick" style={{ color: c.nickColor }}>{c.nick}</span>
            <span className="chat-decor-text">{c.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}