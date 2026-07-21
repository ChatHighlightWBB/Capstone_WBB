import os
import numpy as np
import librosa

def extract_audio_rms_features(video_path: str, sample_rate: int = 22050, hop_length: int = 512) -> dict:
    """
    [설계 이유 (Why)]
    1. 제안서 세부 기능 3.2.1 명세에 따라 비디오에서 오디오 파형을 로드하고 RMS 에너지를 추출합니다.
    2. OpenCV 채팅창 프레임 가공 주기(5초)와 시간축을 정확히 일치시켜 
       차후 Late Fusion 스코어링 시 자석처럼 1:1 결합이 가능하도록 설계했습니다.
    """
    print(f"🎵 [Librosa 오디오 엔진] 음성 분석 및 RMS 시계열 특징 추출 개시: {video_path}")
    
    if not os.path.exists(video_path):
        print(f"❌ [Librosa] 분석 대상 원본 영상이 존재하지 않습니다: {video_path}")
        return {}
        
    try:
        # Step 1: 비디오 파일에서 오디오 파형(Waveform, y)과 샘플링 레이트(sr) 오토 로드
        # AI 표준 분석 규격인 22.05kHz 단일 채널(Mono)로 변환 로드
        y, sr = librosa.load(video_path, sr=sample_rate, mono=True)
        
        # 전체 비디오의 총 물리 시간(초) 계산
        total_duration_sec = librosa.get_duration(y=y, sr=sr)
        
        # Step 2: 오디오 신호의 단기 에너지인 RMS(Root Mean Square) 프레임 배열 계산
        # $RMS = \sqrt{\frac{1}{N} \sum |x(n)|^2}$ 식에 따라 소리의 물리적 크기를 정량화
        rms_array = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
        
        # Step 3: 5초 interval 단위로 시간축 동기화 다운샘플링 보정
        frames_per_sec = sr / hop_length
        interval_frames = int(frames_per_sec * 5)  # 5초 간격 오디오 프레임 수
        
        audio_time_series = {}
        total_intervals = int(np.ceil(total_duration_sec / 5))
        
        for i in range(total_intervals):
            start_frame = i * interval_frames
            end_frame = min(start_frame + interval_frames, len(rms_array))
            
            if start_frame >= len(rms_array):
                break
                
            # 5초 구간 내에서 가장 강하게 터진 음성 에너지(Peak RMS)를 추출 (스트리머 고함/환호 포착용)
            chunk_rms = rms_array[start_frame:end_frame]
            peak_rms_value = float(np.max(chunk_rms)) if len(chunk_rms) > 0 else 0.0
            
            # 타임코드 인덱스 생성 (ex: 5초 -> 00:00:05)
            timestamp_sec = i * 5
            mins, secs = divmod(timestamp_sec, 60)
            hours, mins = divmod(mins, 60)
            time_index_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            
            audio_time_series[time_index_str] = round(peak_rms_value, 4)
            
        print(f"✅ [Librosa 완료] 총 {len(audio_time_series)}개 오디오 시계열 구간의 RMS 특징 맵 추출 성공.")
        return audio_time_series
        
    except Exception as audio_e:
        print(f"❌ [Librosa 오디오 가공 에러]: {str(audio_e)}")
        return {}

# 모듈 단독 동작 테스트용
if __name__ == "__main__":
    test_video = "temp_storage/wbb_20260720_192300_360p.mp4"
    if os.path.exists(test_video):
        result = extract_audio_rms_features(test_video)
        print("테스트 결과 샘플:", result)