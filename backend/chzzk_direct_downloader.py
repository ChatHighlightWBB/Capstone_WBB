"""
=============================================================================
[와바바(WBB)] 치지직(CHZZK) 자체 API 직접 다운로더
=============================================================================

[왜 이게 필요한가]
yt-dlp의 CHZZK 익스트랙터는 DASH 매니페스트를 파싱할 때 <SegmentTemplate>에
sourceURL 속성이 없으면 KeyError('sourceURL')로 죽습니다. 이건 yt-dlp
Python 코드 자체의 버그라 --extractor-args로 우회가 안 됩니다.

[우회 방법]
yt-dlp를 아예 안 거치고, 치지직 자체 API에서 재생 매니페스트 URL만
직접 받아온 뒤, 그 URL을 ffmpeg에 바로 넘깁니다. ffmpeg는 C로 작성된
자체 DASH demuxer가 있어서 yt-dlp의 이 버그와 무관하게 동작합니다.

[참고 문서 — 커뮤니티에서 리버스 엔지니어링한 API]
    https://github.com/JTech-CO/chzzk-downloader
    https://greasyfork.org (치지직 다시보기 실제 시각 토글 유저스크립트)

  영상 상세 : GET api.chzzk.naver.com/service/v2/videos/{videoNo}
  재생 정보 : GET apis.naver.com/neonplayer/vodplay/v2/playback/{videoId}
              ?key={inKey}&sid=2099&env=real&lc=ko&cpl=ko

[중요 — 반드시 실제 테스트 필요]
이 코드는 공개된 적 없는 비공식 API라, 응답 필드명(특히 inKey가 정확히
어느 키에 들어있는지)이 문서마다 조금씩 다르게 언급됩니다. 아래
_extract_in_key()가 여러 후보 키를 시도하도록 만들어뒀지만, 실제로
돌려보시고 안 되면 debug_dump=True로 실제 응답을 출력해서 정확한
필드명을 확인한 뒤 고쳐야 합니다.
"""

import os
import re
import json
import subprocess
import urllib.request
import urllib.error

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _http_get_json(url: str, headers: dict = None) -> dict:
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_video_no(chzzk_url: str) -> str:
    """https://chzzk.naver.com/video/123456 -> '123456'"""
    m = re.search(r"/video/(\d+)", chzzk_url)
    if not m:
        raise ValueError(f"치지직 URL에서 video 번호를 못 찾았습니다: {chzzk_url}")
    return m.group(1)


def _extract_in_key(video_detail: dict) -> str:
    """
    영상 상세 응답 안 어딘가에 재생용 inKey가 들어있습니다.
    문서마다 표기가 달라서 여러 후보 경로를 순서대로 시도합니다.
    """
    content = video_detail.get("content", video_detail)
    candidates = [
        content.get("inKey"),
        content.get("inkey"),
        content.get("videoInKey"),
        video_detail.get("inKey"),
    ]
    for c in candidates:
        if c:
            return c
    raise KeyError(
        "inKey를 찾지 못했습니다. debug_dump=True로 실제 응답을 확인하고 "
        "_extract_in_key()의 후보 키 목록을 실제 필드명으로 고쳐주세요."
    )


def get_playback_manifest_url(chzzk_url: str, debug_dump: bool = False) -> str:
    """
    치지직 VOD 링크 하나로 실제 재생 가능한 DASH 매니페스트(.mpd) URL을
    반환합니다. ffmpeg가 이 URL을 직접 읽을 수 있습니다.
    """
    video_no = extract_video_no(chzzk_url)

    detail_url = f"https://api.chzzk.naver.com/service/v2/videos/{video_no}"
    detail = _http_get_json(detail_url)
    if debug_dump:
        print("=== [DEBUG] 영상 상세 응답 ===")
        print(json.dumps(detail, ensure_ascii=False, indent=2)[:2000])

    in_key = _extract_in_key(detail)
    content = detail.get("content", detail)
    video_id = content.get("videoId") or video_no

    playback_url = (
        f"https://apis.naver.com/neonplayer/vodplay/v2/playback/{video_id}"
        f"?key={in_key}&sid=2099&env=real&lc=ko&cpl=ko"
    )
    playback_info = _http_get_json(playback_url)
    if debug_dump:
        print("=== [DEBUG] 재생 정보 응답 ===")
        print(json.dumps(playback_info, ensure_ascii=False, indent=2)[:2000])

    # 응답이 매니페스트 자체를 JSON으로 감싸서 줄 수도, 매니페스트 URL만
    # 필드로 줄 수도 있습니다. 두 경우 다 대응합니다.
    manifest_url = (
        playback_info.get("url")
        or playback_info.get("manifestUrl")
        or playback_info.get("mpdUrl")
    )
    if not manifest_url:
        raise KeyError(
            "재생 매니페스트 URL을 응답에서 못 찾았습니다. debug_dump=True로 "
            "실제 응답을 확인하고 필드명을 맞춰주세요."
        )
    return manifest_url


def download_chzzk_vod_direct(chzzk_url: str, output_path: str, max_height: int = 480,
                               debug_dump: bool = False) -> bool:
    """
    yt-dlp를 거치지 않고, 치지직 API에서 받은 매니페스트 URL을 ffmpeg에
    직접 물려서 다운로드합니다. 성공하면 True, 실패하면 False를 반환합니다.
    """
    try:
        manifest_url = get_playback_manifest_url(chzzk_url, debug_dump=debug_dump)
    except Exception as e:
        print(f"❌ [CHZZK 직접 다운로드] 매니페스트 URL 획득 실패: {e}")
        return False

    print(f"🎯 [CHZZK 직접 다운로드] 매니페스트 확보, ffmpeg로 다운로드 시작...")

    # ffmpeg 자체 DASH demuxer 사용. -c copy로 재인코딩 없이 그대로 저장합니다.
    # 화질 선택(max_height)은 DASH 매니페스트에 여러 화질이 있을 때
    # ffmpeg -map 0:v:0 같은 스트림 지정이 필요할 수 있는데, 이건 실제
    # 매니페스트 구조를 보고 조정해야 합니다 (일단 기본 스트림으로 시도).
    cmd = [
        "ffmpeg", "-y",
        "-user_agent", USER_AGENT,
        "-i", manifest_url,
        "-c", "copy",
        output_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0 or not os.path.exists(output_path):
        print(f"❌ [CHZZK 직접 다운로드] ffmpeg 실패: {result.stderr[-800:]}")
        return False

    print(f"✅ [CHZZK 직접 다운로드] 성공: {output_path}")
    return True


if __name__ == "__main__":
    # 단독 테스트용. 실제 치지직 VOD 링크로 바꿔서 debug_dump=True로 먼저
    # 돌려보고, 응답 구조를 확인한 뒤 위 필드명들을 실제에 맞게 고치세요.
    TEST_URL = "https://chzzk.naver.com/video/0000000"
    download_chzzk_vod_direct(TEST_URL, "./chzzk_test_output.mp4", debug_dump=True)