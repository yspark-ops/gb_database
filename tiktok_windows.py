import time
import random
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ==========================================
#  틱톡 아이디 리스트
# ==========================================
tiktok_ids = [

"aec.pau", "rickhutchugc", "alyssiaaa.r", "debluxe0", "alyssiaaa.r", "aec.pau", "natvnk", "reffysenae", "isarahbutler", "aec.pau", "jeselleleigh", "kimesiaaaa", "natalietucc", "leilanii_02", "jalazzy", "orixnaomi", "sarahcramos", "itsdque_", "soyandreabaca", "aec.pau", "malikahroyallah", "ashleykaylamakeup", "layla_.mckenzie", "sarahcramos", "glambervcruz", "whatwouldlizzydo", "kelliesmom", "davidandhana", "liceisyummy", "omgitsrileyr", "miriamezagui", "alexandrasfinds1", "icedcaramelriss", "tkochristo", "nilsaprowant", "cicihaskill", "omgitsrileyr", "tkochristo", "linus1002", "stephanieowens1992", "livraebrew", "liceisyummy", "alexandrasfinds1", "smittyyyyyyy1", "cicihaskill", "toya_no_la", "rust_ridge_ranch26", "nilsaprowant", "zoraidajazmine", "nopasanadabuyit", "its_ashleyyyb", "mikaylanogueira", "lis_beautytips", "michelledemoda", "sammycakes2020", "taybeckerbeauty", "mydlvz1", "samanthamullino", "lis_beautytips", "smittyyyyyyy1", "jeffreestar", "lexirosenstein", "lis_beautytips", "lushoctober", "ericataylor2347", "lorenrosko", "adityamadiraju", "lis_beautytips", "hallie_grace8", "nphiynhi", "itsnotnotus", "mydlvz1", "sarahcramos", "bri.lynn.riley1", "lexirosenstein", "dusteerosexo", "angelamachadobeauty", "kayleecollective", "ginangeles07", "the_jakks", "dailydealswithme", "sydneyshops", "smellgoodeveryday1", "taybeckerbeauty", "thelighttorch", "brittney_lucas", "kelliecrowther", "callmetarajay", "michellesfaves", "lexirosenstein", "michellesays", "little_miss_c_", "lexirosenstein", "sydneyshops", "brizlittle", "lyndeedebetaz", "riannapepe", "sarahkchey", "nphiynhi", "romand_us", "riannapepe"
]

chrome_options = Options()

# 봇 탐지 회피 설정
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("--start-maximized") 

print("=== 브라우저를 찾고 있습니다 (처음엔 몇 초 걸릴 수 있습니다) ===")
driver = webdriver.Chrome(options=chrome_options)

results = []

print(f"=== 총 {len(tiktok_ids)}명 크롤링 시작 (윈도우 환경) ===")

for i, user_id in enumerate(tiktok_ids):
    url = f"https://www.tiktok.com/@{user_id}"
    
    print(f"[{i+1}/{len(tiktok_ids)}] {user_id} 접속 중...", end=" ")
    
    try:
        driver.get(url)
        
        time.sleep(random.uniform(3, 5))
        
        bio_text = ""
        email = ""
        
        try:
            bio_element = driver.find_element(By.CSS_SELECTOR, '[data-e2e="user-bio"]')
            bio_text = bio_element.text
            
            # 이메일 추출
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', bio_text)
            if email_match:
                email = email_match.group(0)
                print(f"-> 이메일: {email}")
            else:
                print("-> 이메일 없음")
                
        except Exception:
            print("-> 정보 없음 (로딩 실패/캡챠)")
            
        results.append({
            "ID": user_id,
            "URL": url,
            "Email": email,
            "Bio": bio_text
        })
        
    except Exception as e:
        print(f"-> 에러: {e}")

    time.sleep(random.uniform(1, 3))

# ==========================================
#  결과 저장 -> tiktok_project 폴더 내 저장
# ==========================================
df = pd.DataFrame(results)
df.to_excel("tiktok_result_final.xlsx", index=False)
print("\n=== 작업 완료! 'tiktok_result_final.xlsx' 파일이 생성되었습니다. ===")

driver.quit()