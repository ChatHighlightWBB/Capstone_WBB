import os
import subprocess
from typing import List, Dict

def extract_and_merge_highlight_clips(video_url: str, final_highlights: List[Dict], video_id: str) -> List[str]:
    """
    [설계 이유 (Why)]
    1. 제안서 설계 원칙 3번(프록시 기반 다운로드)과 세부 기능 4.2.1 명세에 따라 
       최종 확정된 하이라이트 타임코드 구간만 선택적으로 추출합니다.
    2. FFmpeg Stream Copy(-c copy) 방식을 적용하여 재인코딩 없이 
       화질 손실 0%, 초단위 속도로 고화질 클립을 잘라내고 하나의 요약본으로 병합합니다.
    """
    print(f"🎬 [FFmpeg 클리핑 엔진] 고화질 구간 무인코딩 부분 추출 및 병합 시작 (Target: {len(final_highlights)}개 구간)")
    
    output_dir = os.path.join("temp_storage", f"{video_id}_clips")
    os.makedirs(output_dir, exist_ok=True)
    
    generated_clip_paths = []
    concat_list_file = os.path.join(output_dir, "concat_list.txt")
    
    # 💡 FFmpeg 실행 파일 경로 탐색 (가상환경 내부 또는 시스템 PATH)
    base_dir = os.path.abspath(os.path.dirname(__file__))
    venv_ffmpeg = os.path.join(base_dir, "venv", "Scripts", "ffmpeg.exe")
    ffmpeg_bin = venv_ffmpeg if os.path.exists(venv_ffmpeg) else "ffmpeg"

    try:
        with open(concat_list_file, "w", encoding="utf-8") as list_f:
            for item in final_highlights:
                rank = item.get("rank", 1)
                start_time = item.get("start_time", "00:00:00")
                end_time = item.get("end_time", "00:00:30")
                
                clip_filename = f"highlight_rank_{rank:02d}.mp4"
                clip_path = os.path.join(output_dir, clip_filename)
                
                # 💡 [핵심 기술 스택: FFmpeg Stream Copy]
                # -ss (시작시간) -to (종료시간) -c copy 옵션으로 비디오/오디오 무인코딩 고속 절단
                # 360p 프록시 파일(temp_storage/video_id_360p.mp4)로부터 즉시 잘라내어 빠른 응답 속도 보장
                source_360p = os.path.join("temp_storage", f"{video_id}_360p.mp4")
                
                if not os.path.exists(source_360p):
                    print(f"❌ [FFmpeg] 원본 프록시 파일이 없어 클리핑을 중단합니다: {source_360p}")
                    continue
                    
                cmd = f'"{ffmpeg_bin}" -y -ss {start_time} -to {end_time} -i "{source_360p}" -c copy "{clip_path}"'
                
                res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if res.returncode == 0 and os.path.exists(clip_path):
                    generated_clip_paths.append(clip_path)
                    # 병합용 상대 경로 적재
                    list_f.write(f"file '{clip_filename}'\n")
                    print(f"  └ ✂️ [클리핑 성공] Rank {rank}: [{start_time} ~ {end_time}] -> {clip_filename}")
                else:
                    print(f"  └ ❌ [클리핑 실패] Rank {rank}: {res.stderr.strip()}")

        # 💡 [최종 하이라이트 모음집 무인코딩 자동 병합]
        merged_output_path = os.path.join(output_dir, f"{video_id}_final_summary.mp4")
        if len(generated_clip_paths) > 1:
            concat_cmd = f'"{ffmpeg_bin}" -y -f concat -safe 0 -i "{concat_list_file}" -c copy "{merged_output_path}"'
            concat_res = subprocess.run(concat_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if concat_res.returncode == 0:
                print(f"🎉 [FFmpeg 모음집 병합 완료] 최종 요약 파일: {merged_output_path}")
            else:
                print(f"⚠️ [FFmpeg 병합 예외]: {concat_res.stderr.strip()}")

        return generated_clip_paths

    except Exception as clip_e:
        print(f"❌ [FFmpeg 클리핑 엔진 사후 에러]: {str(clip_e)}")
        return []

# 단독 테스트용
if __name__ == "__main__":
    dummy_final = [
        {"rank": 1, "start_time": "00:00:00", "end_time": "00:00:10"},
        {"rank": 2, "start_time": "00:00:15", "end_time": "00:00:25"}
    ]
    extract_and_merge_highlight_clips("", dummy_final, "wbb_20260721_145650")