"""
=============================================================================
[와바바(WBB)] OCR 전용 독립 실행 워커
=============================================================================

[왜 별도 프로세스로 분리했는가]
paddlepaddle-gpu와 torch(CUDA든 CPU든 무관하게)를 같은 파이썬 프로세스에
같이 import하면 Windows에서 아래 증상 중 하나로 깨지는 게 확인됐습니다:

  - OSError: [WinError 127] cudnn_cnn64_9.dll 관련 프로시저를 찾을 수 없음
  - "partially initialized module 'paddle' has no attribute 'tensor'
     (most likely due to a circular import)"

device를 CPU로 강제해도 재현되는 걸 확인했고, 다른 프로젝트에서도 동일하게
보고된 걸 확인했습니다 — 즉 CUDA 설정 문제가 아니라 두 라이브러리가 같은
프로세스 안에 공존하는 것 자체가 Windows에서 불안정한 상태입니다.

그래서 OCR(paddle) 부분만 완전히 별도의 파이썬 프로세스로 떼어냈습니다.
이 스크립트는 torch를 전혀 import하지 않고, 메인 서버 프로세스(torch를
쓰는 Whisper/Demucs가 있는 곳)와도 완전히 분리된 프로세스로 실행됩니다.
서로 메모리를 공유하지 않으니 DLL/모듈 충돌이 구조적으로 발생할 수 없습니다.

[대가]
매 분석마다 이 프로세스가 새로 뜨면서 PaddleOCR 모델을 매번 새로
로딩합니다 (서버 시작 시 1회만 로딩하던 것보다 분석 1건당 몇 초 더 걸림).
프로세스 충돌보다는 이 정도 오버헤드가 훨씬 낫습니다.

[사용법]
    python ocr_worker_cli.py --video path/to/video.mp4 --output out.csv
                              [--crop-box 0.15,0.65,0.6,0.98]
                              [--sample-rate 5.0]

crop-box를 안 주면 Auto-ROI가 자동으로 채팅창 위치를 찾습니다.
성공하면 exit code 0, 실패하면 0이 아닌 코드와 함께 stderr에 에러를 남깁니다.
"""

import sys
import argparse

# [Windows 인코딩 방어] 이 스크립트가 highlight_pipeline.py의 env 설정 없이
# 직접 실행되는 경우에도, 이모지 출력이 콘솔 기본 인코딩(cp949 등) 때문에
# 죽지 않도록 표준출력/에러 인코딩을 UTF-8로 강제합니다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass  # 아주 오래된 파이썬이면 reconfigure가 없을 수 있음 — 무시하고 진행


def main():
    parser = argparse.ArgumentParser(description="와바바 OCR 전용 워커 (paddle 전용 프로세스)")
    parser.add_argument("--video", required=True, help="입력 영상 경로")
    parser.add_argument("--output", required=True, help="결과 CSV 저장 경로")
    parser.add_argument("--crop-box", default=None,
                         help="ymin,xmin,ymax,xmax (0~1 비율). 안 주면 Auto-ROI 사용")
    parser.add_argument("--sample-rate", type=float, default=5.0, help="프레임 샘플링 주기(초)")
    args = parser.parse_args()

    crop_box = None
    if args.crop_box:
        try:
            crop_box = tuple(float(x) for x in args.crop_box.split(","))
        except ValueError:
            print(f"[ocr_worker] crop-box 형식이 잘못됐습니다: {args.crop_box}", file=sys.stderr)
            sys.exit(2)

    # 이 지점 이전에는 paddle/paddleocr을 아직 아무것도 import하지 않습니다.
    # (모듈 최상단에서 import하면 argparse 에러 하나 내는 데도 무거운 모델
    #  로딩 코드까지 다 실행되니, 여기서 지연 import합니다.)
    from ppocr_chat_extractor import WBBPPOCRExtractor

    extractor = WBBPPOCRExtractor()
    extractor.extract_chat_from_video(
        video_path=args.video,
        crop_box=crop_box,
        sample_rate_sec=args.sample_rate,
        output_csv_path=args.output,
    )
    print(f"[ocr_worker] 완료: {args.output}")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ocr_worker] 실패: {e}", file=sys.stderr)
        sys.exit(1)