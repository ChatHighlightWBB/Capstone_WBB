import os
import cv2
import numpy as np

def extract_and_crop_chat_frames(video_path: str, output_dir: str, interval_sec: int = 5) -> dict:
    """
    [설계 이유 (Why)]
    1. 세부 기능 1.2.2: 5초 간격 이미지 크롭 전처리
    2. 세부 기능 3.1.2: 연속 프레임 간 픽셀 오차(cv2.absdiff)를 계산하여 
       화면 변화량(Visual Change, 0.0 ~ 1.0) 수치를 시계열로 정량 산출합니다.
    """
    print(f"🎬 [OpenCV 엔진] 채팅창 크롭 및 화면 변화량 분석 시작 (Target: {video_path})")
    
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"❌ [OpenCV] 비디오 파일을 열 수 없습니다: {video_path}")
        return {}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = int(fps * interval_sec)
    
    frame_count = 0
    saved_count = 0
    prev_gray_frame = None
    visual_changes = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            timestamp_sec = int(frame_count / fps)
            mins, secs = divmod(timestamp_sec, 60)
            hours, mins = divmod(mins, 60)
            time_index_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

            # Step 1: 화면 변화량 수치 산출 (세부 기능 3.1.2)
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray_frame is not None:
                # 두 프레임 간 Absolute Difference(절대 차이) 계산
                diff = cv2.absdiff(prev_gray_frame, gray_frame)
                mean_diff = float(np.mean(diff))
                # 0~50 오차 범위를 0.0~1.0 사이로 정규화
                normalized_v_score = min(mean_diff / 50.0, 1.0)
            else:
                normalized_v_score = 0.0
            
            prev_gray_frame = gray_frame
            visual_changes[time_index_str] = round(normalized_v_score, 4)

            # Step 2: 우측 채팅 영역 자르기 (오른쪽 30% 영역)
            h, w, _ = frame.shape
            crop_x = int(w * 0.7)
            chat_crop = frame[0:h, crop_x:w]

            crop_filename = f"frame_{timestamp_sec}s.jpg"
            cv2.imwrite(os.path.join(output_dir, crop_filename), chat_crop)
            saved_count += 1

        frame_count += 1

    cap.release()
    print(f"✅ [OpenCV 완료] 총 {saved_count}개 크롭 프레임 생성 및 화면 변화량 맵 산출 완료.")
    return visual_changes

if __name__ == "__main__":
    test_video = "temp_storage/wbb_20260721_150850_360p.mp4"
    if os.path.exists(test_video):
        res = extract_and_crop_chat_frames(test_video, "temp_storage/test_chats")
        print("화면 변화량 샘플:", res)