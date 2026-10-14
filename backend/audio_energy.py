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

# ==============================================================================
# [피치·템포] 제안서 3.2.3 Librosa 피치(Pitch)·에너지(RMS)·속도(Tempo) 분석.
# 템포는 정규화 없는 onset strength 1초 평균(소리 변화량에 가까운 지표).
# 2026-10-14 토크 방송에서 음량과 순위 상관 피치 0.69, 템포 0.57.
# 목소리 대역 필터는 300Hz 아래를 잘라 기본 주파수가 사라지므로, 피치는 lowpass 만 건 소리를 따로 읽어 잽니다.
# ==============================================================================
PITCH_FILTER = "lowpass=f=1000"   # 피치용 소리 필터(기본 주파수를 남김)
PITCH_FMIN = 70.0                 # 피치 탐색 하한(Hz)
PITCH_FMAX = 500.0                # 피치 탐색 상한(Hz)
PITCH_FRAME_LENGTH = 2048         # 피치·프레임 RMS 프레임 길이(샘플, 128ms)
PITCH_HOP_LENGTH = 512            # 프레임 간격(샘플, 32ms). onset strength 도 같은 간격
PITCH_LOUD_FRAME_RATIO = 0.5      # 프레임 RMS 가 그 1초 RMS 의 이 비율 이상인 프레임(소리 있는 프레임)만 피치에 씀


def compute_loudness_per_sec(video_path, voice_band=False):
    """1초마다 음량(dBFS)을 계산해 리스트로 돌려준다. 전체를 메모리에 올리지 않고 1초씩 흘려 읽는다.
    voice_band=True 면 목소리 대역(300~3400Hz)만 남기고 계산한다."""
    # 계획서의 Librosa RMS 에너지 산출. 소리 읽기는 긴 방송 메모리 문제로 FFmpeg 로 1초씩 흘려 읽음
    # (librosa 는 무거워서 서버 시작이 느려지지 않게 함수 안에서 import)
    import librosa

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
            # 1초 배열 전체를 프레임 하나로 보고 librosa.feature.rms 로 RMS 1개를 구한다
            n = len(samples)
            rms = float(librosa.feature.rms(y=samples, frame_length=n, hop_length=n, center=False)[0, 0])
            db = 20.0 * np.log10(rms) if rms > 0 else SILENCE_DB
            result.append(max(float(db), SILENCE_DB))
            if len(buf) < chunk_bytes:  # 마지막 조각(1초 미만)
                break
    finally:
        proc.stdout.close()
        proc.wait()
    return result


def _read_one_sec(proc, chunk_bytes):
    """pipe 에서 1초 분량이 찰 때까지 모아 float 배열로 돌려준다(compute_loudness_per_sec 와 같은 읽기). 끝이면 None."""
    buf = b""
    while len(buf) < chunk_bytes:
        part = proc.stdout.read(chunk_bytes - len(buf))
        if not part:
            break
        buf += part
    if len(buf) < 2:
        return None
    buf = buf[: len(buf) - (len(buf) % 2)]
    return np.frombuffer(buf, dtype=np.int16).astype(np.float64) / 32768.0


def compute_voice_features_per_sec(video_path):
    """1초마다 목소리 음량(dB)·피치(f0, Hz)·템포(onset strength 평균)를 계산해 dict 로 돌려준다.
    {"rms_db": [...], "f0_hz": [... 또는 None], "onset_strength": [...]}
    - 음량·템포: 목소리 대역 소리(compute_loudness_per_sec(voice_band=True) 와 같은 필터·16000Hz 모노).
      음량은 그 함수와 같은 계산, 템포는 librosa.onset.onset_strength 의 1초 평균(1초마다 정규화하지 않음).
    - 피치: lowpass 만 건 소리에서 librosa.yin 프레임별 f0 중, 소리 있는 프레임만의 중간값(없으면 None).
    두 소리를 ffmpeg 두 개로 동시에 열어 같은 1초끼리 짝지어 흘려 읽는다(전체를 메모리에 올리지 않음)."""
    import librosa  # 서버 시작이 느려지지 않게 함수 안에서 import (compute_loudness_per_sec 와 같음)

    def open_stream(af):
        cmd = ["ffmpeg", "-v", "error", "-i", video_path, "-vn", "-af", af,
               "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def chunk_rms(y):
        # 1초 배열 전체를 프레임 하나로 본 RMS (compute_loudness_per_sec 와 같음)
        n = len(y)
        return float(librosa.feature.rms(y=y, frame_length=n, hop_length=n, center=False)[0, 0])

    chunk_bytes = int(SAMPLE_RATE * CHUNK_SEC) * 2  # s16le = 샘플당 2바이트
    result = {"rms_db": [], "f0_hz": [], "onset_strength": []}
    p_voice = open_stream(VOICE_FILTER)  # 음량·템포용
    p_pitch = open_stream(PITCH_FILTER)  # 피치용
    try:
        while True:
            yv = _read_one_sec(p_voice, chunk_bytes)
            yp = _read_one_sec(p_pitch, chunk_bytes)
            if yv is None or yp is None:
                break

            # 음량(dB)과 템포(onset strength 1초 평균). 무음이거나 너무 짧은 조각은 템포 0
            rms = chunk_rms(yv)
            db = 20.0 * np.log10(rms) if rms > 0 else SILENCE_DB
            result["rms_db"].append(max(float(db), SILENCE_DB))
            if rms <= 0 or len(yv) < PITCH_FRAME_LENGTH // 2:
                strength = 0.0
            else:
                strength = float(librosa.onset.onset_strength(y=yv, sr=SAMPLE_RATE, hop_length=PITCH_HOP_LENGTH).mean())
            result["onset_strength"].append(strength)

            # 피치: 소리 있는 프레임(프레임 RMS >= 1초 RMS × 비율)의 f0 중간값
            f0_med = None
            p_rms = chunk_rms(yp)
            if p_rms > 0 and len(yp) >= PITCH_FRAME_LENGTH // 2:
                f0 = librosa.yin(yp, fmin=PITCH_FMIN, fmax=PITCH_FMAX, sr=SAMPLE_RATE,
                                 frame_length=PITCH_FRAME_LENGTH, hop_length=PITCH_HOP_LENGTH)
                frame_rms = librosa.feature.rms(y=yp, frame_length=PITCH_FRAME_LENGTH, hop_length=PITCH_HOP_LENGTH)[0]
                m = min(len(f0), len(frame_rms))
                loud = frame_rms[:m] >= PITCH_LOUD_FRAME_RATIO * p_rms
                if loud.any():
                    f0_med = float(np.median(f0[:m][loud]))
            result["f0_hz"].append(f0_med)

            if len(yv) < SAMPLE_RATE * CHUNK_SEC:  # 마지막 조각(1초 미만)
                break
    finally:
        for proc in (p_voice, p_pitch):
            proc.stdout.close()
            proc.kill()  # 한쪽이 먼저 끝나 남은 ffmpeg 가 pipe 에서 기다리지 않게 정리
            proc.wait()
    return result