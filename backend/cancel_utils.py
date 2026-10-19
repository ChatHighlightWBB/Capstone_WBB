"""
[와바바(WBB)] 분석 취소 도구
- 사용자가 분석 화면에서 "분석 멈추기"를 누르면 server.py 가 작업별 threading.Event 를 켭니다.
- 파이프라인(highlight_pipeline.py, stage2_refinement.py, ffmpeg_clipper.py)은 단계 사이·반복문 앞에서
  check_cancel()로 그 표시를 확인하고, 켜져 있으면 AnalysisCancelled 를 던져 멈춥니다.
- server.py 와 파이프라인 모듈이 서로 import 하지 않도록(순환 import 방지) 따로 둔 파일입니다.
"""


class AnalysisCancelled(Exception):
    """사용자가 분석을 멈춤"""


def check_cancel(cancel_event):
    """
    cancel_event(threading.Event)가 켜져 있으면 AnalysisCancelled 를 던집니다.
    None 이면(취소 기능을 쓰지 않는 호출) 아무것도 하지 않아 기존 동작과 같습니다.
    """
    if cancel_event is not None and cancel_event.is_set():
        raise AnalysisCancelled("사용자가 분석을 멈췄어요.")