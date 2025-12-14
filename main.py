import os
import json
import io
import re # [추가] 정규표현식 모듈 (숫자만 추출하기 위해)
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# 1. 설정 및 클라이언트 초기화
load_dotenv()
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
# 폰트 경로 설정 (프로젝트 루트의 fonts 폴더 안에 폰트 파일이 있어야 함)
# 굵고 힘있는 폰트가 잘 어울립니다. (예: NanumSquareRoundEB.ttf, GmarketSansBold.ttf)
FONT_PATH = "./fonts/NanumSquareRoundEB.ttf" 
# FONT_PATH = "./fonts/GmarketSansTTFBold.ttf" 
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)

app = FastAPI()

# 폰트 로드 도우미 함수
def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        print(f"⚠️ 경고: '{FONT_PATH}' 폰트 파일을 찾을 수 없습니다. 기본 폰트를 사용합니다. (한글 깨짐 발생 가능)")
        return ImageFont.load_default()
    
def parse_color_string(color_str, default_color):
    """
    "(255, 0, 0, 255)" 같은 문자열을 (255, 0, 0, 255) 튜플로 변환합니다.
    실패하면 default_color를 반환합니다.
    """
    if not color_str:
        return default_color
    
    try:
        # 1. 숫자만 모두 추출 (정규표현식)
        # 예: "(26, 43, 85, 255)" -> ['26', '43', '85', '255']
        numbers = re.findall(r'\d+', str(color_str))
        
        # 2. 3개(RGB) 혹은 4개(RGBA)인 경우 튜플로 변환
        if len(numbers) in [3, 4]:
            return tuple(map(int, numbers))
        else:
            return default_color # 숫자가 이상하면 기본색 사용
    except Exception:
        return default_color

# ==========================================
# [추가] 색상 밝기 계산 함수
# ==========================================
# [핵심] 색상 밝기에 따라 최적의 그림자 색상 반환
def get_optimal_shadow_color(text_color):
    r, g, b = text_color[:3]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    # 밝은 색(128 이상)이면 검은 그림자, 어두운 색이면 흰색 그림자
    if luminance < 128:
        return (255, 255, 255, 220) # 흰색 (진하게)
    else:
        return (0, 0, 0, 220)       # 검은색 (진하게)

# ==========================================
# [최종] 상용 앱 수준의 '트레이딩 카드' 디자인
# ==========================================
def create_premium_card_image(image_bytes, data):
    try:
        base_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    except Exception:
        base_image = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
        
    width, height = base_image.size
    
    text_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    # 1. 폰트 크기 설정 (작고 오밀조밀하게)
    font_s = load_font(int(width * 0.04))  # 1줄: 제품명
    font_xl = load_font(int(width * 0.075)) # 2줄: 주식 수
    font_m = load_font(int(width * 0.05))  # 3줄: 티커

    # 2. 색상 정의
    default_mint = (0, 255, 180, 255) 
    color_highlight_down = (255, 200, 0, 255) # 주황색 (강조)
    color_white = (255, 255, 255, 255)   # 흰색 (기본)
    shadow_color = (0, 0, 0, 220)        # 그림자 (진하게)
    
    

    # [수정] 두 가지 색상 파싱
    raw_prod_color = data.get('product_representation_color')
    raw_comp_color = data.get('company_representation_color')
    
    product_color = parse_color_string(raw_prod_color, default_mint) # 제품 색상
    company_color = parse_color_string(raw_comp_color, default_mint) # 기업 색상
    
    name = data.get('company_name', 'Company')
    ticker = data.get('ticker', 'TICKER')
    count = data.get('share_count', '0')
    
    if str(ticker).isdigit(): 
        display_name = name  # 한국 주식: 이름 표시 (예: 삼성전자)
    else:
        display_name = ticker # 해외 주식: 티커 표시 (예: TSLA)

    # Line 1: [제품명(노랑)] + [ 참으면(흰색)]
    line1_parts = [
        (data.get('product_name', '제품'), font_m, product_color),
        (" 대신", font_s, color_white)
    ]
    
    # Line 2: [N주(노랑)] - 전체 강조
    line2_parts = [
        (f"{display_name} {count}주", font_xl, company_color)
    ]
    
    # Line 3: [티커(노랑)] + [ 주주(노랑)] + [ 가능!(흰색)]
    line3_parts = [
        (" 주주", font_m, color_highlight_down),
        (" 되자!", font_s, color_white)
    ]

    # 4. 조각난 텍스트 이어 그리기 함수 (핵심 로직)
    def draw_multi_colored_line(parts, y_pos):
        # (1) 전체 너비 미리 계산 (중앙 정렬 위해)
        total_width = 0
        max_height = 0
        for text, font, _ in parts:
            bbox = draw.textbbox((0, 0), text, font=font)
            total_width += bbox[2] - bbox[0]
            max_height = max(max_height, bbox[3] - bbox[1])
        
        # (2) 시작 X 좌표 (중앙)
        padding_right = int(width * 0.1) # 오른쪽 여백 10%
        start_x = width - total_width - padding_right
        # start_x = (width - total_width) // 2
        
        # (3) 순서대로 그리기
        current_x = start_x
        for text, font, color in parts:
            # [핵심] 현재 글자색에 딱 맞는 그림자 색상 계산
            if color == color_white:
                current_shadow = (0, 0, 0, 220) # 흰 글씨는 무조건 검은 그림자
            else:
                current_shadow = get_optimal_shadow_color(color)
                
            # 그림자 (외곽선 효과)
            stroke_width = max(2, int(font.size / 12))
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx!=0 or dy!=0:
                        draw.text((current_x+dx, y_pos+dy), text, font=font, fill=current_shadow)
            
            # 실제 글씨
            draw.text((current_x, y_pos), text, font=font, fill=color)
            
            # 다음 글자 위치로 이동
            bbox = draw.textbbox((0, 0), text, font=font)
            current_x += bbox[2] - bbox[0]
            
        return max_height # 이 줄의 높이 반환

    # 5. 전체 높이 계산 및 Y좌표 설정 (오밀조밀 간격)
    gap = int(width * 0.01) # 줄 간격 최소화
    
    # 임시 높이 계산
    h1 = draw_multi_colored_line(line1_parts, -1000) # 그리기X, 계산만
    h2 = draw_multi_colored_line(line2_parts, -1000)
    h3 = draw_multi_colored_line(line3_parts, -1000)
    
    total_text_height = h1 + h2 + h3 + (gap * 2)
    start_y = int(height * 0.6) - (total_text_height // 2) # 화면 60% 지점 중심

    # 6. 실제 그리기 실행
    current_y = start_y
    draw_multi_colored_line(line1_parts, current_y)
    current_y += h1 + gap
    
    draw_multi_colored_line(line2_parts, current_y)
    current_y += h2 + gap
    
    draw_multi_colored_line(line3_parts, current_y)

    # 7. 합성 및 저장
    final_image = Image.alpha_composite(base_image, text_layer).convert("RGB")
    img_byte_arr = io.BytesIO()
    final_image.save(img_byte_arr, format='JPEG', quality=95)
    img_byte_arr.seek(0)
    return img_byte_arr

@app.post("/vision-invest-image")
async def vision_invest_image(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        
        # ==========================================
        # 1단계: Gemini 분석 (안전한 도형 강제)
        # ==========================================
        print("🔍 1단계: 이미지 분석 중...")
        analyze_prompt = """
        Analyze this image and identify the main product.
        Provide the details in JSON format.
        
        [Detailed Identification Rules]
        1. **Read Visible Text (OCR):** Look closely for any text on labels, packaging, screens, or cup sleeves. Use this to determine the exact name (e.g., "Iced Americano" instead of just "Coffee").
        2. **Identify Brand & Logo:** Look for logos (Apple logo, Starbucks siren, Samsung logo) to confirm the brand.
        3. **Visual Distinctions:** - If it's a phone, look at the camera layout to guess the model (e.g., Galaxy S24 Ultra vs Base model).
           - If it's a car, look at the emblem and grille.
        4. **Naming Format:** Combine "[Brand] [Specific Model/Item]".
           - Good: "스타벅스 아이스 아메리카노", "삼성 갤럭시 S24 울트라", "나이키 덩크 로우"
           - Bad: "커피", "스마트폰", "운동화"
        
        Rules for 'symbol':
        - Do NOT use emojis.
        - ONLY use one of these safe geometric shapes: ●, ■, ◆, ★, ♥, ♠
        
        [Logic for 'share_count']
        Calculate: (Product Price / Stock Price)
        - If result >= 1: Round to 1 decimal place (e.g., 15.23 -> "15.2").
        - If result < 1: Show up to the first non-zero digit (e.g., 0.0041 -> "0.004", 0.052 -> "0.05").
        
        Rules for 'company_name':
        - Provide a name well known to people. (e.g., "Apple" instead of "Apple Inc.").
        - provide the name in Korean (e.g., "애플", "삼성전자", "스타벅스").
        - Must be a listed company on a stock exchange.
        - If it is not a publicly traded company or you cannot identify which company it is, it is likely the largest publicly traded company that makes a similar product.
        
        Rules for 'product_price':
        - Estimate the retail price of the product in KRW.
        - If the product is a consumable (e.g., coffee, food), provide the price for a standard size or serving.
        - If the product is a durable good (e.g., phone, car, shoes), provide the base model price without extra features.
        - If the product is intangible, provide its subscription fee or usage fee(e.g., Netflix monthly fee).
        

        JSON Output Requirements:
        1. "product_name": Product name in Korean.
        2. "ticker": product manufacturer (Stock ticker).
        3. "share_count": Calculated string based on the logic above.
        4. "product_price" : Estimated product price in KRW (Integer string, e.g. "4500").
        5. "stock_price" : Estimated stock price in KRW (Integer string, e.g. "120000").
        6. "symbol": One safe shape.
        7. "company_name": follow the rules above.
        8. "company_representation_color": A representative color of the company in RGBA, last value must be 255 (e.g., "(255, 0, 0, 255)").
        9. "product_representation_color": A representative color of the product in RGBA, last value must be 255 (e.g., "(0, 255, 0, 255)").

        Example:
        {"symbol": "♥", 
        "product_name": "스타벅스 커피", 
        "ticker": "SBUX", 
        "product_price": "4500", 
        "stock_price": "135000", 
        "share_count": "0.03", 
        "company_name": "스타벅스",
        "company_representation_color": "(0, 128, 0, 255)",
        "product_representation_color": "(139, 69, 19, 255)"}
        """
        
        # ... (Gemini 호출 및 에러 처리 코드는 이전과 동일하게 유지) ...
        # (지면 관계상 생략, 기존 코드의 Gemini 호출 부분을 그대로 사용하세요)
        analysis_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                analyze_prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", # JSON 강제 출력
                # tools=[types.Tool(google_search=types.GoogleSearch())] # 검색 허용
                # [중요] 금융 관련 답변이 차단되지 않도록 안전 필터 해제
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE"
                    ),
                ]
            )
        )

        # [테스트용 가짜 데이터 - Gemini 호출 성공 시 주석 처리하세요]
        data = json.loads(analysis_response.text)
        print(f"✅ 분석 완료: {data}")

        # ==========================================
        # 2단계 & 3단계: 문구 완성 및 Pillow 합성 (v2 호출)
        # ==========================================
        print("🎨 2&3단계: 고퀄리티 이미지 합성 중 (Pillow v2)...")
        
        # 이제 텍스트를 합치지 않고 데이터 자체를 넘깁니다.
        final_image_stream = create_premium_card_image(image_bytes, data)
        
        file_name = "C:\\Users\\Lenovo\\Desktop\\111\\local_test_result.jpg"
        with open(file_name, "wb") as f:
            f.write(final_image_stream.getvalue())
        
        return StreamingResponse(final_image_stream, media_type="image/jpeg")

    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))