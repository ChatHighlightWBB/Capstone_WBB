import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

def run_interactive_emotion_analyzer():
    print("\n==================================================")
    print("[WBB] VS Code 실시간 감정 분류기 가동 (종료하려면 'exit' 입력)")
    print("==================================================")
    
    # 허깅페이스에 등록된 한국어 감정 분류 KLUE-BERT v2 모델 사용
    model_name = "dlckdfuf141/korean-emotion-kluebert-v2"
    
    try:
        # 가상환경 venv 내부에 다운로드된 토크나이저와 모델 가중치 로드
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        model.eval() # 연산 속도 향상 및 추론 일관성을 위해 평가 모드로 설정
        
        # 모델 고유의 7개 감정 맵 데이터 구조 정의
        labels_map = {
            0: "공포", 1: "놀람", 2: "분노", 3: "슬픔", 
            4: "중립", 5: "행복", 6: "혐오"
        }
        
        # 사용자가 'exit'를 치기 전까지 무한 반복 구동하는 대화형 루프
        while True:
            print("\n" + "-"*50)
            # 💡 [여기에 입력] 터미널 창에서 직접 텍스트를 입력받는 파이썬 내장 함수
            user_input = input("👉 분석할 채팅을 입력하세요: ").strip()
            
            # 종료 조건 처리
            if user_input.lower() == 'exit':
                print("[WBB] 실시간 분석기를 종료합니다. 고생하셨습니다.")
                print("==================================================")
                break
                
            if not user_input:
                print("[경고] 빈 문장입니다. 단어를 입력해 주세요.")
                continue
                
            # 텍스트 데이터의 텐서(Tensor) 정형화 및 전처리
            inputs = tokenizer(user_input, return_tensors="pt", padding=True, truncation=True, max_length=64)
            
            # AI 딥러닝 역전파 연산을 비활성화하여 CPU/GPU 메모리 및 추론 성능 최적화
            with torch.no_grad():
                outputs = model(**inputs)
                
            # 예측된 로짓(Logits) 결과값을 합계 100% 규격의 퍼센트 확률로 변환
            probs = F.softmax(outputs.logits, dim=-1)[0]
            
            print(f"\n[WBB] '{user_input}' 분석 결과:")
            print("-"*50)
            
            # 확률이 높은 감정 순서대로 정렬하여 데이터 가공
            sorted_probs = sorted(
                [(labels_map[i], prob.item() * 100) for i, prob in enumerate(probs)],
                key=lambda x: x[1], reverse=True
            )
            
            # 터미널 시각화용 막대그래프 텍스트 출력
            for label, percent in sorted_probs:
                bar = "■" * int(percent // 5)
                print(f"[{label}] {percent:6.2f}% : {bar}")
                
            print("-"*50)
            print(f"💡 추천 라벨: {sorted_probs[0][0]} (매핑 번호 기입용)")
            
    except Exception as e:
        print(f"\n[오류] 구동 중 예외 발생: {e}")

if __name__ == "__main__":
    run_interactive_emotion_analyzer()