"""
=============================================================================
[와바바(WBB)] SOOP(구 아프리카TV) 브라우저 자동화 다운로더
=============================================================================

[왜 이게 필요한가]
streamlink의 SOOP 플러그인은 공식적으로 "Type: live"만 지원하고 VOD는
지원 범위 밖입니다 (streamlink 공식 플러그인 문서 기준). 즉 설정을
바꿔서 될 문제가 아니라, VOD 재생 URL 자체를 다른 방법으로 구해야 합니다.

[우회 방법]
실제 브라우저(Playwright)로 VOD 페이지를 열어서, 페이지가 로딩되며
발생하는 네트워크 요청 중 실제 영상 스트림(.m3u8)을 가로챕니다.
이렇게 구한 서명된 m3u8 URL을 ffmpeg에 바로 넘겨서 다운로드합니다.

[커뮤니티 확인 사항]
"Soop VOD Downloader" 같은 크롬 확장 프로그램들이 정확히 이 방식
(브라우저에서 m3u8을 가로채서 다운로드)으로 동작합니다. 즉 이게
현재 SOOP VOD를 받을 수 있는 사실상 유일한 방법입니다.

[설치 필요]
    pip install playwright
    playwright install chromium

[중요 — 반드시 실제 테스트 필요]
- SOOP은 페이지 진입 시 성인 인증/비밀번호 등이 걸린 영상이 있을 수 있고,
  이 경우 이 스크립트가 그대로는 못 뚫습니다.
- m3u8 URL 패턴(.m3u8 포함 여부)이 실제와 다를 수 있어, capture 조건을
  실제 네트워크 탭을 보고 조정해야 할 수 있습니다.
- 이 방식은 매번 브라우저를 띄우는 만큼 다운로드 1건당 몇 초~수십 초
  더 걸립니다.
"""

import os
import re
import subprocess

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 실제로 캡처하고 싶은 스트림 URL 패턴. 화질별로 여러 개가 잡힐 수 있어서,
# 그중 "가장 마지막에 잡힌 것"이나 "특정 해상도가 포함된 것"을 고르는 식으로
# 실제 캡처 결과를 보고 조정하는 걸 권장합니다.
M3U8_PATTERN = re.compile(r"\.m3u8(\?|$)")


def capture_m3u8_url(soop_vod_url: str, timeout_ms: int = 20000, debug_dump: bool = False) -> str:
    """
    Playwright로 SOOP VOD 페이지를 열어서, 실제 재생에 쓰이는 m3u8 URL을
    네트워크 요청 가로채기로 찾아냅니다. 못 찾으면 예외를 던집니다.
    """
    from playwright.sync_api import sync_playwright  # 지연 임포트 (미설치 시 이 함수만 실패)

    captured_urls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        def on_request(request):
            if M3U8_PATTERN.search(request.url):
                captured_urls.append(request.url)
                if debug_dump:
                    print(f"🔍 [SOOP 캡처] m3u8 요청 발견: {request.url}")

        page.on("request", on_request)

        page.goto(soop_vod_url, wait_until="domcontentloaded", timeout=timeout_ms)

        # 재생 버튼을 눌러야 스트림 요청이 발생하는 페이지 구조일 수 있어서,
        # 흔한 재생 버튼 선택자 몇 개를 시도해봅니다. 안 눌려도 에러는 아닙니다.
        for selector in ["button.btn_play", ".player_control_play", "video"]:
            try:
                page.click(selector, timeout=2000)
                break
            except Exception:
                continue

        page.wait_for_timeout(timeout_ms)
        browser.close()

    if not captured_urls:
        raise RuntimeError(
            "m3u8 요청을 하나도 못 잡았습니다. 로그인/성인인증이 필요한 "
            "영상이거나, 페이지 구조가 바뀌어서 재생 버튼 선택자를 "
            "못 찾았을 수 있습니다. debug_dump=True로 다시 확인해보세요."
        )

    # 보통 가장 마지막(재생이 실제로 시작된 뒤)에 잡힌 URL이 실제 스트림입니다.
    return captured_urls[-1]


def download_soop_vod_direct(soop_vod_url: str, output_path: str, debug_dump: bool = False) -> bool:
    """
    브라우저로 m3u8 URL을 캡처한 뒤, ffmpeg로 다운로드합니다.
    성공하면 True, 실패하면 False를 반환합니다.
    """
    try:
        m3u8_url = capture_m3u8_url(soop_vod_url, debug_dump=debug_dump)
    except ImportError:
        print("❌ [SOOP 직접 다운로드] playwright가 설치되지 않았습니다. "
              "pip install playwright && playwright install chromium")
        return False
    except Exception as e:
        print(f"❌ [SOOP 직접 다운로드] m3u8 캡처 실패: {e}")
        return False

    print(f"🎯 [SOOP 직접 다운로드] m3u8 확보, ffmpeg로 다운로드 시작...")

    cmd = [
        "ffmpeg", "-y",
        "-user_agent", USER_AGENT,
        "-i", m3u8_url,
        "-c", "copy",
        output_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0 or not os.path.exists(output_path):
        print(f"❌ [SOOP 직접 다운로드] ffmpeg 실패: {result.stderr[-800:]}")
        return False

    print(f"✅ [SOOP 직접 다운로드] 성공: {output_path}")
    return True


if __name__ == "__main__":
    TEST_URL = "https://vod.sooplive.co.kr/player/00000000"
    download_soop_vod_direct(TEST_URL, "./soop_test_output.mp4", debug_dump=True)