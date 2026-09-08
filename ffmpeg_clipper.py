"""
=============================================================================
[와바바(WBB)] 5단계: FFmpeg 초고속 무인코딩 하이라이트 클리핑 및 병합기
- 담당자: 송태섭 (책임개발자)
- 핵심 패치: 
  1. highlight_pipeline.py 호출 규격에 맞춰 파라미터명을 'output_video'로 동기화
  2. 파이프라인에서 video_path 누락 시 JSON 메타데이터에서 원본 경로를 자동 추출하는 방어 로직 추가
  3. 알 수 없는 파라미터 충돌을 막기 위한 **kwargs 흡수 처리
=============================================================================
"""

import os
import json
import subprocess

class WBBFFmpegClipper:
    def __init__(self):
        pass

    def cut_and_merge_highlights(
        self, 
        video_path: str = None,  # [수정] 필수 인자에서 선택 인자로 변경하여 파이프라인 누락 에러 방어
        json_path: str = "final_highlight_candidates.json", 
        output_video: str = "final_highlight.mp4",
        buffer_sec: float = 1.5,
        **kwargs  # [수정] 오케스트레이션에서 던지는 알 수 없는 인자(예: target_video)를 에러 없이 흡수
    ):
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"❌ '{json_path}' 파일이 없습니다.")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # [핵심 방어 로직] 파이프라인이 비디오 경로를 명시적으로 주지 않으면, 
        # kwargs를 뒤져보거나 4단계 JSON 메타데이터에 기록된 원본 경로를 직접 꺼내옵니다.
        if not video_path:
            video_path = kwargs.get("target_video", data.get("metadata", {}).get("source_video"))

        # 그래도 경로가 없거나 파일이 존재하지 않으면 안전하게 종료
        if not video_path or not os.path.exists(video_path):
            print(f"❌ [오류] 자를 원본 영상 경로를 찾을 수 없습니다: {video_path}")
            return None

        clips = data.get("highlight_clips", [])
        if not clips:
            print("⚠️ 클리핑할 최종 하이라이트 구간이 없습니다.")
            return None

        os.makedirs("./temp_cut_clips", exist_ok=True)
        clip_files = []

        print(f"\n🎬 [Step 5] 총 {len(clips)}개 하이라이트 구간 무인코딩 클리핑 시작 (안전 버퍼: ±{buffer_sec}초)")

        for idx, item in enumerate(clips, 1):
            raw_start = float(item["start_time"])
            raw_end = float(item["end_time"])

            # FFmpeg stream copy 특유의 키프레임 밀림 현상을 방어하기 위한 안전 버퍼 마진 계산
            safe_start = max(0.0, raw_start - buffer_sec)
            safe_end = raw_end + buffer_sec
            clip_duration = safe_end - safe_start

            part_filename = f"./temp_cut_clips/part_{idx}.mp4"
            
            # FFmpeg 무인코딩 자르기 명령어 (-c copy 활용으로 초고속 무손실 추출)
            cmd_cut = [
                "ffmpeg", "-y",
                "-ss", str(safe_start),
                "-t", str(clip_duration),
                "-i", video_path,
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                part_filename
            ]
            subprocess.run(cmd_cut, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            clip_files.append(part_filename)
            print(f" ➔ [{idx}/{len(clips)}] 구간 절삭 완료: {safe_start:.1f}초 ~ {safe_end:.1f}초 -> {part_filename}")

        # 병합(concat)을 위한 리스트 텍스트 파일 동적 생성
        concat_list_path = "./temp_cut_clips/merge_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as lf:
            for c_path in clip_files:
                abs_p = os.path.abspath(c_path).replace("\\", "/")
                lf.write(f"file '{abs_p}'\n")

        print(f"\n🎞️ [Step 5] 개별 클립들을 단일 하이라이트 영상으로 병합 중...")
        cmd_merge = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_video
        ]
        subprocess.run(cmd_merge, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if os.path.exists(output_video):
            size_mb = os.path.getsize(output_video) / (1024 * 1024)
            print(f"🎉 [성공] 최종 하이라이트 영상 제작 완료: '{output_video}' ({size_mb:.2f} MB)")
            return output_video
        else:
            print("❌ 병합 영상 생성 실패")
            return None


if __name__ == "__main__":
    clipper = WBBFFmpegClipper()
    clipper.cut_and_merge_highlights(video_path="test_sample_game.mp4")