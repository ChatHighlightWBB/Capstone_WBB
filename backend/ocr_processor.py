import os
import re
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# 💡 [초보자 안내]: 현재 PC에 paddlepaddle 및 paddleocr 패키지가 설치되어 있어야 작동합니다.
# 터미널에서 'pip install paddlepaddle paddleocr'를 선행 실행해 두어야 합니다.
from paddleocr import PaddleOCR

def run_ppocr_inference_and_save(chat_image_dir: str, video_id: str, mongodb_url: str, db_name: str):
    """
    [설계 이유 (Why)]
    1. 제안서 세부 기능 3.1.1 명세에 따라, 크롭된 흑백 프레임 이미지 내부의 채팅 텍스트를 추출합니다.
    2. 추출된 문자열은 휘발되지 않도록 Cloud NoSQL인 MongoDB Atlas에 시계열 데이터 규격으로 적재합니다.
    3. 메인 백엔드 Uvicorn 루프의 병목을 막기 위해 차후 메인 파이프라인 체인 결합 시 run_in_executor로 위임됩니다.
    """
    print(f"👁️ [PP-OCRv3 엔진] 텍스트 추론 및 파싱 공정 개시 (Target: {chat_image_dir})")
    
    # 한국어(lang='ko') 인식을 지원하는 초경량 PP-OCRv3 객체 초기화 (추론 속도 개선 최적화 인자 포함)
    ocr = PaddleOCR(use_angle_cls=False, lang='ko', show_log=False)
    
    # 가공 완료 폴더 내부에 존재하는 frame_XXXXs.jpg 파일 목록 수집 후 정렬
    if not os.path.exists(chat_image_dir):
        print(f"❌ [PP-OCRv3] 크롭 이미지 디렉토리가 존재하지 않습니다: {chat_image_dir}")
        return False
        
    image_files = sorted([f for f in os.listdir(chat_image_dir) if f.endswith('.jpg')])
    
    # 데이터베이스에 집적할 정형 시계열 로그 배열
    time_series_logs = []
    
    for filename in image_files:
        # 파일명에서 정규식을 이용해 타임코드(초) 추출 (예: frame_0005s.jpg -> 5)
        match = re.search(r'frame_(\d+)s', filename)
        if not match:
            continue
        timestamp_sec = int(match.group(1))
        
        image_path = os.path.join(chat_image_dir, filename)
        
        # PP-OCRv3 이미지 추론 연산 수행
        result = ocr.ocr(image_path, cls=False)
        
        parsed_text_list = []
        if result and result[0]:
            for line in result[0]:
                # line[1][0] 구조 내부에 OCR이 인식한 실제 텍스트 문자열이 바인딩되어 있음
                text_content = line[1][0].strip()
                if text_content:
                    parsed_text_list.append(text_content)
                    
        # D3.js/Chart.js 시각화용 및 KoBERT 자연어 입력 규격에 맞춘 타임 스탬프 문자열 변환 (ex: 00:00:05)
        mins, secs = divmod(timestamp_sec, 60)
        hours, mins = divmod(mins, 60)
        time_index_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
        
        # MongoDB Atlas에 도큐먼트로 삽입될 객체 구조 정의
        log_entry = {
            "time_index": time_index_str,
            "timestamp_sec": timestamp_sec,
            "raw_chats": parsed_text_list,
            "chat_count": len(parsed_text_list)
        }
        time_series_logs.append(log_entry)
        print(f"📝 [PP-OCRv3 파싱] 타임라인 [{time_index_str}] -> {len(parsed_text_list)}건 추출 완료.")

    # 💡 [MongoDB Atlas 물리 저장 계층 작동]
    # 동기식 스레드 컨텍스트 내부에서 데이터 무결성을 보장하며 원격 MongoDB에 Bulk Insert를 수행하기 위해
    # 표준 동기식 매커니즘인 pymongo 표준 라이브러리를 경유하여 트랜잭션을 체결합니다.
    try:
        from pymongo import MongoClient
        client = MongoClient(mongodb_url)
        db = client[db_name]
        
        # 비디오 ID별 독립 컬렉션을 생성하거나 동적 생성하여 격리 적재
        collection = db[f"analysis_{video_id}"]
        
        if time_series_logs:
            # 컬렉션 내부 초기화 후 대량 적재 안전 수행
            collection.delete_many({})
            collection.insert_many(time_series_logs)
            print(f"✅ [MongoDB Atlas] 시계열 채팅 로그 {len(time_series_logs)}개 도큐먼트 영구 저장 완착 완료!")
            client.close()
            return True
        else:
            print("ℹ️ 추출된 텍스트 로그가 없어 DB 적재를 보류합니다.")
            client.close()
            return False
            
    except Exception as db_e:
        print(f"❌ [MongoDB Atlas 연동 에러]: {str(db_e)}")
        return False

# 모듈 단독 테스트용 진입점
if __name__ == "__main__":
    # 지난 공정의 wbb_20260720_184250 타임 코드를 대입하여 단독 모듈 동작 테스트 수행 가능
    target_dir = "temp_storage/wbb_20260720_184250_chats"
    test_id = "wbb_20260720_184250"
    
    # 개발 인프라 내 로컬/Atlas 접속 정보 바인딩 (.env 설정 연동 규격)
    mock_url = "mongodb://localhost:27017"
    mock_db = "wbb_db"
    
    if os.path.exists(target_dir):
        run_ppocr_inference_and_save(target_dir, test_id, mock_url, mock_db)