import os
import json
import subprocess

class WBBFFmpegClipper:
    """
    [설명]
    1. final_highlight_candidates.json의 확정 구간을 읽어옵니다.
    2. FFmpeg Stream Copy(-c copy) 무인코딩 방식으로 구간별 고속 클리핑을 수행합니다.
    3. 클립들을 단일 최종 하이라이트 영상(final_highlight.mp4)으로 병합합니다.
    """
    def __init__(self, video_path: str = "./test_sample.mp4", temp_clip_dir: str = "./temp_clips"):
        self.video_path = video_path
        self.temp_clip_dir = temp_clip_dir
        os.makedirs(self.temp_clip_dir, exist_ok=True)

    def cut_and_merge_highlights(self, json_path: str = "final_highlight_candidates.json", output_video: str = "final_highlight.mp4"):
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"'{json_path}' 파일이 없습니다. 2차 검증을 먼저 실행하세요.")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        highlights = data.get("highlights", [])
        if not highlights:
            print("❌ 병합할 하이라이트 구간이 없습니다.")
            return

        print("=" * 70)
        print(f"🎬 [FFmpeg 무인코딩 클리핑 시작] 총 {len(highlights)}개 구간 추출")
        print("=" * 70)

        clip_files = []
        concat_list_path = os.path.join(self.temp_clip_dir, "concat_list.txt")

        # 1. 구간별 무인코딩 부분 추출
        for idx, h in enumerate(highlights):
            start = h["start_time"]
            duration = h["duration"]
            clip_path = os.path.join(self.temp_clip_dir, f"highlight_part_{idx}.mp4")

            # 무인코딩 Stream Copy 적용 (-c copy)
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-t", str(duration),
                "-i", self.video_path,
                "-c", "copy",
                "-avoid_negative_ts", "1",
                clip_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            clip_files.append(clip_path)
            print(f" ➔ 클립 생성 완료: Part {idx+1} ({start}초 ~ {h['end_time']}초, {duration}초 분량)")

        # 2. 병합 목록 파일(concat list) 작성
        with open(concat_list_path, "w", encoding="utf-8") as cf:
            for c_path in clip_files:
                abs_path = os.path.abspath(c_path).replace("\\", "/")
                cf.write(f"file '{abs_path}'\n")

        # 3. 무인코딩 단일 영상 병합
        print(f"\n🎞️ [최종 병합 중...] ➔ '{output_video}'")
        merge_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_video
        ]
        subprocess.run(merge_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        if os.path.exists(output_video):
            file_size_mb = round(os.path.getsize(output_video) / (1024 * 1024), 2)
            print("=" * 70)
            print(f"🎉 [성공] 최종 하이라이트 영상 생성 완료: {output_video} ({file_size_mb} MB)")
            print("=" * 70)
        else:
            print("❌ 영상 병합에 실패했습니다.")

if __name__ == "__main__":
    clipper = WBBFFmpegClipper(video_path="./test_sample.mp4")
    clipper.cut_and_merge_highlights(
        json_path="final_highlight_candidates.json",
        output_video="final_highlight.mp4"
    )