import os
from fastapi import FastAPI, Request
from vertexai.generative_models import GenerativeModel
import vertexai

app = FastAPI()

# Cloud Run에서는 프로젝트 ID를 자동으로 가져오지만, 
# 혹시 모르니 안전하게 초기화
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
vertexai.init(project=PROJECT_ID, location="asia-northeast3")

model = GenerativeModel("gemini-1.5-flash")

# 안전장치: ID가 없으면 에러를 띄워서 개발자가 알게 함
if not PROJECT_ID:
    raise ValueError("Project ID가 없습니다! 환경변수를 설정해주세요.")

@app.get("/")
def home():
    return {"status": "test"}