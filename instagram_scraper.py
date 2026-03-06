import time
import random
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

insta_ids = [
    "lyndeedebetaz",
]


chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_argument("--start-maximized")

print("=== 브라우저를 실행합니다 ===")
driver = webdriver.Chrome(options=chrome_options)

driver.get("https://www.instagram.com/")
print("\n" + "="*50)
print("🚨 [매우 중요] 브라우저에서 인스타그램에 직접 로그인해주세요!")
print("🚨 로그인이 완료되어 피드 화면이 나오면,")
print("🚨 여기 터미널로 돌아와서 [Enter] 키를 누르세요.")
print("="*50 + "\n")

input("로그인 완료 후 엔터를 누르세요...") # 여기서 대기함

results = []

print(f"=== 총 {len(insta_ids)}명 크롤링 시작 ===")

for i, user_id in enumerate(insta_ids):
    url = f"https://www.instagram.com/{user_id}/"
    
    print(f"[{i+1}/{len(insta_ids)}] {user_id} 확인 중...", end=" ")
    
    try:
        driver.get(url)
        
        time.sleep(random.uniform(4, 7))
        
        bio_text = ""
        email = ""
        
        try:
            header_element = driver.find_element(By.TAG_NAME, "header")
            bio_text = header_element.text
            
            # 정규표현식으로 이메일 찾기
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', bio_text)
            if email_match:
                email = email_match.group(0)
                print(f"-> 이메일: {email}")
            else:
                print("-> 이메일 없음")
                
        except Exception:
            print("-> 프로필을 찾을 수 없음 (비공개 또는 계정 없음)")
        
        results.append({
            "ID": user_id,
            "URL": url,
            "Email": email,
            "Bio": bio_text.replace("\n", " ")[:100]
        })
        
    except Exception as e:
        print(f"-> 에러: {e}")

    time.sleep(random.uniform(2, 5))

df = pd.DataFrame(results)
df.to_excel("instagram_emails.xlsx", index=False)
print("\n=== 작업 완료! 'instagram_emails.xlsx' 저장됨 ===")

driver.quit()