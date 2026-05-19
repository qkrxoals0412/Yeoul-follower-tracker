from flask import Flask, render_template_string
import requests
from bs4 import BeautifulSoup
import os
import time

app = Flask(__name__)

TARGET = 8062

# 🔥 캐시 (서버 안정화 및 Picuki 요청 제한 방지)
cache = {
    "followers": 7421,
    "timestamp": 0
}

CACHE_TTL = 300  # 5분마다 한 번씩만 Picuki에 접속하도록 설정

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>여울 팔로워 트래커</title>
    <meta http-equiv="refresh" content="300">
    <style>
        body { background-color: white; font-family: Arial, sans-serif; text-align: center; margin: 0; padding-top: 60px; }
        .logo { width: 320px; margin-bottom: 40px; }
        .followers-label { font-size: 28px; color: #555; margin-bottom: 10px; }
        .odometer { display: flex; justify-content: center; gap: 6px; font-size: 140px; font-weight: bold; color: #111; }
        .digit { width: 70px; height: 140px; overflow: hidden; position: relative; }
        .digit-inner { position: absolute; top: 0; left: 0; transition: transform 0.6s ease; }
        .num { height: 140px; display: flex; align-items: center; justify-content: center; }
        .target-number { font-size: 55px; font-weight: bold; color: #a00020; margin-top: 10px; }
        .progress-container { width: 80%; height: 45px; background-color: #e5e5e5; margin: 50px auto; border-radius: 30px; overflow: hidden; }
        .progress-bar { height: 100%; background-color: #c8102e; }
        .percent { font-size: 36px; font-weight: bold; color: #c8102e; margin-top: -20px; }
        .remaining { margin-top: 60px; font-size: 60px; font-weight: bold; color: #111; }
        .remaining span { color: #c8102e; font-size: 90px; }
        .subtext { margin-top: 30px; font-size: 28px; color: #777; }
    </style>
</head>
<body>
    <img src="/static/logo.png" class="logo">
    <div class="followers-label">여울 현재 팔로워 수</div>
    <div class="odometer" id="odometer"></div>
    <div class="target-number">목표: 연세대학교 인연 (8,062명)</div>
    <div class="progress-container">
        <div class="progress-bar" style="width: {{ percent }}%;"></div>
    </div>
    <div class="percent">{{ percent }}%</div>
    <div class="remaining">연세대학교 인연까지 <span>{{ remaining }}</span>!</div>
    <div class="subtext">목표 달성을 향해 달려가는 중</div>

<script>
function renderOdometer(number) {
    const el = document.getElementById("odometer");
    el.innerHTML = "";
    String(number).split("").forEach(d => {
        const wrap = document.createElement("div"); wrap.className = "digit";
        const inner = document.createElement("div"); inner.className = "digit-inner";
        for (let i = 0; i <= 9; i++) {
            const num = document.createElement("div"); num.className = "num"; num.innerText = i; inner.appendChild(num);
        }
        inner.style.transform = `translateY(-${d * 140}px)`;
        wrap.appendChild(inner); el.appendChild(wrap);
    });
}
window.onload = function () {
    const current = {{ followers }};
    renderOdometer(current);
};
</script>
</body>
</html>
"""

def get_followers():
    global cache
    now = time.time()

    if now - cache["timestamp"] < CACHE_TTL:
        return cache["followers"]

    try:
        # Picuki를 통해 인스타 정보 가져오기
        url = "https://www.picuki.com/profile/kuyeoul"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Picuki의 팔로워 정보가 담긴 태그 찾기 (상황에 따라 클래스명 확인 필요)
        # 보통 통계 숫자는 .profile-stat-count 클래스 등에 위치함
        stats = soup.select('.profile-stat-count')
        if stats:
            # 첫 번째 통계가 게시물, 두 번째가 팔로워인 경우가 많음 (확인 후 인덱스 조정)
            followers_str = stats[1].text.replace(',', '').strip()
            followers = int(followers_str)
            
            cache["followers"] = followers
            cache["timestamp"] = now
            return followers
    except Exception as e:
        print("ERROR:", e)

    return cache["followers"]

@app.route("/")
def home():
    followers = get_followers()
    percent = round((followers / TARGET) * 100, 1)
    remaining = TARGET - followers
    return render_template_string(HTML, followers=followers, percent=percent, remaining=remaining)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
