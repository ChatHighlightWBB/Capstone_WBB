import os
import subprocess
from typing import Dict, List


class WBBFFmpegClipper:
  """[설명] 와바바(WBB) 제안서 4.2.1 규격: FFmpeg 기반 무인코딩 고속 클리핑 및 병합 모듈

  화질 손실 없이 스트림 복사(-c copy) 방식으로 후보 구간을 자르고 최종 영상을
  합칩니다.
  """

  def __init__(self, temp_dir: str = "./temp_clips"):
    self.temp_dir = temp_dir
    # 클립 임시 저장 폴더 자동 생성
    os.makedirs(self.temp_dir, exist_ok=True)

  def clip_candidate_segment(
      self,
      video_path: str,
      start_sec: float,
      end_sec: float,
      output_filename: str,
      buffer_sec: float = 3.0,
  ) -> str:
    """[설명] 특정 시작/종료 시간 구간을 앞뒤 버퍼 타임을 포함하여 잘라냅니다.

    :param video_path: 원본 영상 파일 경로
    :param start_sec: 시작 시간 (초)
    :param end_sec: 종료 시간 (초)
    :param output_filename: 저장할 클립 파일명 (예: candidate_1.mp4)
    :param buffer_sec: 앞뒤 여유 시간 (초, 기본 3초)
    :return: 생성된 클립의 절대 경로
    """
    # 시작 시간이 0초보다 작아지지 않도록 방어
    buffered_start = max(0.0, start_sec - buffer_sec)
    duration = (end_sec - start_sec) + (buffer_sec * 2)

    output_path = os.path.join(self.temp_dir, output_filename)

    # FFmpeg 무인코딩 고속 자르기 명령어 (-ss, -t, -c copy)
    cmd = [
        "ffmpeg",
        "-y",  # 기존 파일 덮어쓰기
        "-ss",
        str(buffered_start),  # 시작 지점으로 고속 이동
        "-i",
        video_path,  # 원본 영상 입력
        "-t",
        str(duration),  # 자를 길이(지속 시간)
        "-c",
        "copy",  # 재인코딩 없는 무손실 고속 복사
        output_path,
    ]

    try:
      # 터미널 명령어 비동기 실행 (stdout/stderr 숨김 처리로 깔끔한 출력 유지)
      subprocess.run(
          cmd,
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
      )
      return output_path
    except subprocess.CalledProcessError as e:
      print(f"❌ FFmpeg 클리핑 실패 ({output_filename}): {str(e)}")
      return ""

  def merge_final_clips(
      self, clip_paths: List[str], output_final_path: str
  ) -> str:
    """[설명] 2차 검증을 통과한 최종 하이라이트 클립들을 하나의 영상으로 병합합니다."""
    if not clip_paths:
      print("⚠️ 병합할 클립 파일이 없습니다.")
      return ""

    # FFmpeg concat용 텍스트 리스트 파일 생성
    list_file_path = os.path.join(self.temp_dir, "merge_list.txt")
    with open(list_file_path, "w", encoding="utf-8") as f:
      for path in clip_paths:
        abs_path = os.path.abspath(path).replace("\\", "/")
        f.write(f"file '{abs_path}'\n")

    # FFmpeg 무인코딩 병합 명령어
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_file_path,
        "-c",
        "copy",
        output_final_path,
    ]

    try:
      subprocess.run(
          cmd,
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
      )
      print(f"🎉 최종 하이라이트 영상 병합 완료: {output_final_path}")
      return output_final_path
    except subprocess.CalledProcessError as e:
      print(f"❌ 최종 영상 병합 실패: {str(e)}")
      return ""


# 단독 실행 테스트 루틴
if __name__ == "__main__":
  clipper = WBBFFmpegClipper()

  TEST_VIDEO = "./test_sample.mp4"

  if not os.path.exists(TEST_VIDEO):
    print(f"⚠️ 테스트할 '{TEST_VIDEO}' 파일이 현재 폴더에 없습니다.")
    print("임의의 .mp4 영상을 프로젝트 폴더에 넣고 테스트해 보세요.")
  else:
    print("✂️ [FFmpeg 무인코딩 클리핑 테스트 시작]...")
    # 0초~20초 구간 자르기 테스트
    clip1 = clipper.clip_candidate_segment(
        TEST_VIDEO, start_sec=5.0, end_sec=20.0, output_filename="clip_test_1.mp4"
    )
    print(f"✅ 클립 1 생성 완료: {clip1}")