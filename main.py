import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. 환경 변수 로드 (보안 정보를 .env에서 가져옴)
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
MODEL_ID = os.getenv("GEMINI_MODEL_ID")

# 2. FastAPI 앱 인스턴스 생성 (이게 있어야 uvicorn이 실행됨)
app = FastAPI()

# 요청 데이터 구조 정의
class StockRequest(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"status": "Server is running", "model": MODEL_ID}

@app.post("/analyze")
def analyze_stock(request: StockRequest):
    """
    주식 분석 요청을 받아 Gemini 2.5 + Google Search로 분석 결과 반환
    """
    if not PROJECT_ID:
        raise HTTPException(status_code=500, detail="Project ID 설정이 안 되었습니다.")

    print(f"🚀 분석 요청 수신: {request.query}")

    # 3. Gemini 클라이언트 초기화
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION
    )

    google_search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    try:
        # 4. 모델 호출
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=request.query,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
                temperature=0.1,
            )
        )
        
        # 결과 반환
        return {
            "query": request.query,
            "response": response.text,
            "source": "Google Search Grounding"
        }

    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        # 사용자에게는 상세 에러 대신 일반 메시지 전달 (보안)
        raise HTTPException(status_code=500, detail=str(e))