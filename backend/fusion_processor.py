import numpy as np
from typing import List, Dict

def format_seconds_to_time(sec: int) -> str:
    mins, secs = divmod(sec, 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}"

def calculate_sliding_window_fusion(time_series_logs: List[Dict], window_size_sec: int = 30, step_sec: int = 5, buffer_sec: int = 3) -> List[Dict]:
    """
    [왜 이렇게 작성했는가? (Why)]
    1. 예외 방어: time_series_logs가 비어있거나, 채팅/오디오 값이 전부 0인 경우 발생할 수 있는
       ZeroDivisionError(0으로 나누기 오류)를 방지하기 위한 가드 코드를 추가했습니다.
    2. 세부 기능 4.1.2: 하이라이트 시작/종료 시점에 ±3초 버퍼를 자동 추가합니다.
    """
    print(f"📊 [Late Fusion 엔진] 30초 Sliding Window Multi-modal 스코어링 개시 (입력: {len(time_series_logs)}개)")
    
    # 💡 [예외 처리 1] 입력 데이터가 아예 없는 경우 안전하게 빈 리스트 반환
    if not time_series_logs:
        print("⚠️ [Late Fusion 경고] 분석할 시계열 데이터가 비어있습니다.")
        return []
        
    samples_per_window = window_size_sec // step_sec
    
    all_chat_counts = [doc.get("chat_count", 0) for doc in time_series_logs]
    all_audio_rms = [doc.get("librosa_rms_energy", 0.0) for doc in time_series_logs]
    all_visual_scores = [doc.get("visual_score", 0.0) for doc in time_series_logs]
    
    # 💡 [예외 처리 2] 평균값이 0이 되어 0으로 나누는 오류를 방지하기 위해 최소 기준값 설정
    avg_chat_count = float(np.mean(all_chat_counts)) if all_chat_counts else 1.0
    if avg_chat_count == 0:
        avg_chat_count = 1.0
        
    avg_audio_rms = float(np.mean(all_audio_rms)) if all_audio_rms else 0.01
    if avg_audio_rms == 0:
        avg_audio_rms = 0.01
        
    avg_visual_score = float(np.mean(all_visual_scores)) if all_visual_scores else 0.01
    if avg_visual_score == 0:
        avg_visual_score = 0.01
    
    window_scores = []
    
    for i in range(len(time_series_logs)):
        window_docs = time_series_logs[i : i + samples_per_window]
        if not window_docs:
            break
            
        start_sec = window_docs[0].get("timestamp_sec", 0)
        end_sec = window_docs[-1].get("timestamp_sec", 0) + step_sec
        
        buffered_start_sec = max(0, start_sec - buffer_sec)
        buffered_end_sec = end_sec + buffer_sec
        
        start_time_str = format_seconds_to_time(buffered_start_sec)
        end_time_str = format_seconds_to_time(buffered_end_sec)
        
        win_chat_sum = int(sum([d.get("chat_count", 0) for d in window_docs]))
        win_audio_max = float(max([d.get("librosa_rms_energy", 0.0) for d in window_docs])) if window_docs else 0.0
        win_visual_avg = float(np.mean([d.get("visual_score", 0.0) for d in window_docs])) if window_docs else 0.0
        
        w_chat = 0.5
        w_audio = 0.3
        w_visual = 0.2
        
        if win_audio_max < avg_audio_rms and win_chat_sum > (avg_chat_count * 1.5 * len(window_docs)):
            w_chat = 0.70
            w_audio = 0.10
            w_visual = 0.20
            
        chat_score = min(win_chat_sum / (avg_chat_count * len(window_docs) + 1e-5), 2.0)
        audio_score = min(win_audio_max / (avg_audio_rms + 1e-5), 2.0)
        visual_score = min(win_visual_avg / (avg_visual_score + 1e-5), 2.0)
        
        final_fusion_score = float(round((chat_score * w_chat) + (audio_score * w_audio) + (visual_score * w_visual), 4))
        
        window_scores.append({
            "window_index": int(i),
            "start_time": start_time_str,
            "end_time": end_time_str,
            "win_chat_sum": win_chat_sum,
            "win_audio_max": round(win_audio_max, 4),
            "win_visual_avg": round(win_visual_avg, 4),
            "fusion_score": final_fusion_score
        })

    scores_list = [w["fusion_score"] for w in window_scores]
    mean_score = float(np.mean(scores_list)) if scores_list else 0.0
    std_score = float(np.std(scores_list)) if scores_list else 0.0
    
    adaptive_threshold = float(round(mean_score + (0.8 * std_score), 4))
    print(f"🎯 [Adaptive Threshold] 평균 스코어: {mean_score:.4f}, 동적 임계점: {adaptive_threshold}")
    
    candidate_count = 0
    for w in window_scores:
        is_candidate = bool(w["fusion_score"] >= adaptive_threshold)
        w["is_1st_highlight_candidate"] = is_candidate
        if is_candidate:
            candidate_count += 1
            
    print(f"✅ [Late Fusion 완료] 총 {len(window_scores)}개 윈도우 중 {candidate_count}개 후보 추출 성공.")
    return window_scores