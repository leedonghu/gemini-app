import os
from fastapi import FastAPI
from pydantic import BaseModel
from vertexai.generative_models import GenerativeModel
import vertexai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

app = FastAPI()

# 1. Project ID 확인 (없으면 여기서부터 문제임)
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
print(f"현재 인식된 프로젝트 ID: {PROJECT_ID}") # 터미널에 출력

# 2. Vertex AI 초기화 (실패하면 에러가 남)
try:
    if not PROJECT_ID:
        raise ValueError("Project ID가 환경변수에 없습니다! .env 파일을 확인하세요.")
    vertexai.init(project=PROJECT_ID, location="us-central1")
    model = GenerativeModel("gemini-2.5-flash")
    print("Vertex AI 초기화 성공!")
except Exception as e:
    print(f"초기화 중 에러 발생: {e}")
    model = None # 모델 로딩 실패 처리

class UserQuery(BaseModel):
    query: str

@app.get("/")
def home():
    return {"status": "test!"}

@app.post("/analyze")
def analyze_stock(request_data: UserQuery):
    # 모델이 제대로 로딩 안 됐으면 멈춤
    if not model:
        return {"error": "모델이 초기화되지 않았습니다. 터미널 로그를 확인하세요."}

    try:
        user_query = request_data.query 
        print(f"질문 받음: {user_query}")
        
        # 3. 여기서 에러가 나면 잡아서 보여줌
        response = model.generate_content(user_query)
        return {"reply": response.text}
        
    except Exception as e:
        # 에러 내용을 그대로 브라우저로 보냄 (디버깅용)
        return {"error_message": str(e), "type": "Gemini 실행 중 에러"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)