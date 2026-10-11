import subprocess

import numpy as np

# ==============================================================================
# [채팅+음성 융합용] 1초 단위 목소리 크기(dB) 계산
# 스트리머가 크게 웃거나 소리치는 순간은 하이라이트일 가능성이 높아서,
# 1차 후보 점수(sliding_window_nlp.py)에 채팅 감정과 함께 섞어 씁니다.
# 긴 영상도 메모리를 적게 쓰도록 ffmpeg 출력(pipe)을 1초씩 흘려 읽습니다.
# ==============================================================================
SAMPLE_RATE = 16000          # ffmpeg 로 다시 뽑을 샘플레이트(Hz)
CHUNK_SEC = 1.0              # 몇 초씩 끊어 읽을지
SILENCE_DB = -90.0           # 완전 무음일 때 넣을 dB 값
VOICE_FILTER = "highpass=f=300,lowpass=f=3400"  # 목소리 대역 필터(배경음악·저음 효과음 영향 줄이기)


def compute_loudness_per_sec(video_path, voice_band=False):
    """1초마다 음량(dBFS)을 계산해 리스트로 돌려준다. 전체를 메모리에 올리지 않고 1초씩 흘려 읽는다.
    voice_band=True 면 목소리 대역(300~3400Hz)만 남기고 계산한다."""
    # ffmpeg 는 stage2_refinement.py 와 같이 PATH 의 "ffmpeg" 를 부릅니다.
    cmd = ["ffmpeg", "-v", "error", "-i", video_path, "-vn"]
    if voice_band:
        cmd += ["-af", VOICE_FILTER]
    cmd += ["-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]
    chunk_bytes = int(SAMPLE_RATE * CHUNK_SEC) * 2  # s16le = 샘플당 2바이트
    result = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            # pipe 는 요청한 만큼 한 번에 안 올 수 있어서 1초 분량이 찰 때까지 모은다
            buf = b""
            while len(buf) < chunk_bytes:
                part = proc.stdout.read(chunk_bytes - len(buf))
                if not part:
                    break
                buf += part
            if len(buf) < 2:
                break
            buf = buf[: len(buf) - (len(buf) % 2)]
            samples = np.frombuffer(buf, dtype=np.int16).astype(np.float64) / 32768.0
            rms = float(np.sqrt(np.mean(samples * samples)))
            db = 20.0 * np.log10(rms) if rms > 0 else SILENCE_DB
            result.append(max(float(db), SILENCE_DB))
            if len(buf) < chunk_bytes:  # 마지막 조각(1초 미만)
                break
    finally:
        proc.stdout.close()
        proc.wait()
    return result