import time
import random
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ==========================================
# 1. 틱톡 영상 주소 리스트
# ==========================================
tiktok_urls = [
    "https://www.tiktok.com/@parfum_cerise/video/7603075031702375703", # 예시
    "https://www.tiktok.com/@lilouakeup/video/7602769263224458518", # 예시
    # ... 여기에 틱톡 영상 주소를 계속 추가하세요
]

# ==========================================
# 2. 브라우저 설정
# ==========================================
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("--start-maximized")

# 이미지 로딩 꺼서 속도 높이기 (데이터만 필요하니까)
chrome_options.add_argument("--blink-settings=imagesEnabled=false") 

print("=== 브라우저를 실행합니다 ===")
driver = webdriver.Chrome(options=chrome_options)

results = []

print(f"=== 총 {len(tiktok_urls)}개 영상 데이터 분석 시작 ===")

for i, url in enumerate(tiktok_urls):
    print(f"[{i+1}/{len(tiktok_urls)}] 접속 및 분석 중...", end=" ")
    
    try:
        driver.get(url)
        # 틱톡 데이터가 로딩될 때까지 충분히 대기 (중요)
        time.sleep(random.uniform(5, 7))
        
        view_count = "추출 실패"
        
        try:
            # [핵심 기술] 화면에 보이는 글자가 아니라, 페이지 소스(HTML) 전체를 가져옴
            page_source = driver.page_source
            
            # 틱톡 내부 데이터(JSON)에서 "playCount":12345 패턴을 찾음
            # 이 데이터는 화면에 안 보여도 무조건 존재함
            match = re.search(r'"playCount":(\d+)', page_source)
            
            if match:
                # 숫자만 추출
                raw_count = int(match.group(1))
                # 보기 좋게 포맷팅 (예: 12345 -> 12,345)
                view_count = f"{raw_count:,}"
            else:
                # 혹시 다른 이름으로 저장되어 있을 경우 대비
                match_sub = re.search(r'"itemInfos":\{.*?"playCount":(\d+)', page_source)
                if match_sub:
                    raw_count = int(match_sub.group(1))
                    view_count = f"{raw_count:,}"

        except Exception as e:
            view_count = "에러"
            
        print(f"-> 조회수: {view_count}")
        
        results.append({
            "URL": url,
            "Views": view_count
        })
        
    except Exception as e:
        print(f"-> 접속 실패: {e}")

    # 차단 방지 휴식
    time.sleep(random.uniform(2, 4))

# ==========================================
# 3. 결과 저장
# ==========================================
df = pd.DataFrame(results)
df.to_excel("tiktok_views_final.xlsx", index=False)
print("\n=== 작업 완료! 'tiktok_views_final.xlsx' 저장됨 ===")

driver.quit()