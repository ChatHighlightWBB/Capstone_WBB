# ⚙️ 와바바(WBB) 백엔드 / 프론트엔드 통신 데이터 규격서 (Dummy JSON)

이 JSON 구조는 AI 멀티모달 분석이 완료되었을 때 DB에 저장되고, 프론트엔드로 전달될 최종 데이터 포맷입니다. 엔진 완성 전까지 이 데이터를 바탕으로 API와 UI를 개발합니다.

```json
{
  "video_id": "chzzk_stream_20260522",
  "platform": "CHZZK",
  "video_url": "[https://chzzk.naver.com/video/12345](https://chzzk.naver.com/video/12345)",
  "analyzed_at": "2026-05-22T15:00:00",
  "mood_report": {
    "dominant_emotion": "기쁨(웃음)",
    "emotion_ratio": { 
      "joy": 0.65, 
      "surprised": 0.15, 
      "angry": 0.05, 
      "sad": 0.15 
    }
  },
  "highlights": [
    {
      "highlight_id": 1,
      "start_time": "01:23:10",
      "end_time": "01:23:40",
      "duration_sec": 30,
      "main_emotion": "joy",
      "score": 88.5
    },
    {
      "highlight_id": 2,
      "start_time": "02:05:00",
      "end_time": "02:05:40",
      "duration_sec": 40,
      "main_emotion": "surprised",
      "score": 82.1
    }
  ]
}