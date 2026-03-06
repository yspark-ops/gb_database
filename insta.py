import time
import random
import re
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ==========================================
# 1. 릴스 주소 리스트
# ==========================================
reel_urls = [
    "https://www.instagram.com/p/DUV-612COkn/",
    "https://www.instagram.com/p/DUUAY8PDPiD/",
    # 여기에 원하시는 주소를 계속 추가하세요
]

# ==========================================
# 2. 브라우저 설정
# ==========================================
chrome_options = Options()
# 봇 탐지 회피
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("--start-maximized")

print("=== 브라우저를 실행합니다 ===")
driver = webdriver.Chrome(options=chrome_options)

# ==========================================
# 3. 로그인 단계
# ==========================================
driver.get("https://www.instagram.com/")
print("\n" + "="*50)
print("🚨 [로그인 필수] 인스타그램에 로그인해주세요.")
print("🚨 로그인이 끝나고 피드 화면이 보이면,")
print("🚨 이 터미널에서 [Enter] 키를 누르세요.")
print("="*50 + "\n")

input("로그인 완료 후 엔터를 누르세요...") 

results = []

print(f"=== 총 {len(reel_urls)}개 릴스 정밀 분석 시작 ===")

for i, url in enumerate(reel_urls):
    print(f"[{i+1}/{len(reel_urls)}] 분석 중...", end=" ")
    
    try:
        driver.get(url)
        # 데이터를 불러올 시간을 충분히 줍니다
        time.sleep(random.uniform(4, 6))
        
        view_count = "N/A"
        
        try:
            # [핵심 기술] 화면에 보이는 글자가 아니라, 페이지 소스(HTML) 자체를 가져옵니다.
            page_source = driver.page_source
            
            # 1. 'play_count' 또는 'video_view_count' 라는 숨겨진 데이터 패턴을 찾습니다.
            # 인스타 내부에 "video_view_count":12345 형태로 숨어 있습니다.
            match = re.search(r'"video_view_count":(\d+)', page_source)
            
            if match:
                # 찾았다면 숫자만 추출
                view_count = match.group(1)
            else:
                # 다른 이름으로 저장되어 있을 경우 ('play_count')
                match_sub = re.search(r'"play_count":(\d+)', page_source)
                if match_sub:
                    view_count = match_sub.group(1)
                else:
                    # 정밀 분석 실패 시 최후의 수단: 메타데이터에서 숫자만 뽑기
                    # "86 likes" -> 86 (이건 조회수가 아니라 좋아요일 가능성이 큼)
                    meta_match = re.search(r'"og:description" content="([^"]+)"', page_source)
                    if meta_match:
                        content = meta_match.group(1)
                        view_count = f"(대체값) {content}"

        except Exception as e:
            view_count = "에러"
            
        print(f"-> 조회수: {view_count}")
        
        results.append({
            "URL": url,
            "Views": view_count
        })
        
    except Exception as e:
        print(f"-> 접속 실패: {e}")

    time.sleep(random.uniform(2, 4))

# ==========================================
# 4. 결과 저장
# ==========================================
df = pd.DataFrame(results)
df.to_excel("insta_real_views.xlsx", index=False)
print("\n=== 작업 완료! 'insta_real_views.xlsx' 저장됨 ===")

driver.quit()