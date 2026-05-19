from flask import Flask, render_template_string
from playwright.sync_api import sync_playwright
import re
import os
import time

app = Flask(__name__)

TARGET = 8062

# 🔥 캐시 (서버 안정화 핵심)
cache = {
    "followers": 7421,
    "timestamp": 0
}

CACHE_TTL = 60  # 60초마다만 인스타 접근

HTML = """
<!DOCTYPE html>
<html>

<head>

    <title>여울 팔로워 트래커</title>

    <meta http-equiv="refresh" content="15">

    <style>

        body {
            background-color: white;
            font-family: Arial, sans-serif;
            text-align: center;
            margin: 0;
            padding-top: 60px;
        }

        .logo {
            width: 320px;
            margin-bottom: 40px;
        }

        .followers-label {
            font-size: 28px;
            color: #555;
            margin-bottom: 10px;
        }

        /* 🔥 ODOMETER */
        .odometer {
            display: flex;
            justify-content: center;
            gap: 6px;
            font-size: 140px;
            font-weight: bold;
            color: #111;
        }

        .digit {
            width: 70px;
            height: 140px;
            overflow: hidden;
            position: relative;
        }

        .digit-inner {
            position: absolute;
            top: 0;
            left: 0;
            transition: transform 0.6s ease;
        }

        .num {
            height: 140px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .target-number {
            font-size: 55px;
            font-weight: bold;
            color: #a00020;
            margin-top: 10px;
        }

        .progress-container {
            width: 80%;
            height: 45px;
            background-color: #e5e5e5;
            margin: 50px auto;
            border-radius: 30px;
            overflow: hidden;
        }

        .progress-bar {
            height: 100%;
            background-color: #c8102e;
        }

        .percent {
            font-size: 36px;
            font-weight: bold;
            color: #c8102e;
            margin-top: -20px;
        }

        .remaining {
            margin-top: 60px;
            font-size: 60px;
            font-weight: bold;
            color: #111;
        }

        .remaining span {
            color: #c8102e;
            font-size: 90px;
        }

        .subtext {
            margin-top: 30px;
            font-size: 28px;
            color: #777;
        }

    </style>

</head>

<body>

    <img src="/static/logo.png" class="logo">

    <div class="followers-label">
        여울 현재 팔로워 수
    </div>

    <!-- 🔥 ODOMETER -->
    <div class="odometer" id="odometer"></div>

    <div class="target-number">
        목표: 연세대학교 인연 (8,062명)
    </div>

    <div class="progress-container">
        <div class="progress-bar" style="width: {{ percent }}%;"></div>
    </div>

    <div class="percent">
        {{ percent }}%
    </div>

    <div class="remaining">
        연세대학교 인연까지 <span>{{ remaining }}</span>!
    </div>

    <div class="subtext">
        목표 달성을 향해 달려가는 중
    </div>


<script>

function renderOdometer(number) {
    const el = document.getElementById("odometer");
    el.innerHTML = "";

    String(number).split("").forEach(d => {
        const wrap = document.createElement("div");
        wrap.className = "digit";

        const inner = document.createElement("div");
        inner.className = "digit-inner";

        for (let i = 0; i <= 9; i++) {
            const num = document.createElement("div");
            num.className = "num";
            num.innerText = i;
            inner.appendChild(num);
        }

        inner.style.transform = `translateY(-${d * 140}px)`;

        wrap.appendChild(inner);
        el.appendChild(wrap);
    });
}

window.onload = function () {

    const current = {{ followers }};

    let prev = localStorage.getItem("followers");

    if (!prev) prev = current;

    prev = parseInt(prev);

    let start = prev;
    let end = current;

    let startTime = performance.now();

    function animate(now) {
        let progress = Math.min((now - startTime) / 1000, 1);
        let value = Math.floor(start + (end - start) * progress);

        renderOdometer(value);

        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }

    requestAnimationFrame(animate);

    localStorage.setItem("followers", current);
};

</script>

</body>
</html>
"""


def get_followers():
    global cache

    now = time.time()

    # 🔥 캐시 사용 (서버 안정화)
    if now - cache["timestamp"] < CACHE_TTL:
        return cache["followers"]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox"]
            )

            page = browser.new_page()

            page.goto("https://www.instagram.com/kuyeoul/", timeout=60000)

            page.wait_for_selector("meta[property='og:description']", timeout=10000)

            desc = page.locator("meta[property='og:description']").get_attribute("content")

            browser.close()

            if desc:
                match = re.search(r"([\d,]+)\sFollowers", desc)
                if match:
                    followers = int(match.group(1).replace(",", ""))

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

    return render_template_string(
        HTML,
        followers=followers,
        percent=percent,
        remaining=remaining
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
