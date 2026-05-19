from flask import Flask, render_template_string
from playwright.sync_api import sync_playwright
import re
import os
import time

app = Flask(__name__)

TARGET = 8062

# 🔥 캐시 (핵심)
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

        .odometer {
            display: flex;
            justify-content: center;
            gap: 6px;
            font-size: 140px;
            font-weight: bold;
        }

        .digit {
            width: 70px;
            height: 140px;
            overflow: hidden;
            position: relative;
        }

        .digit-inner {
            position: absolute;
            transition: transform 0.6s ease;
        }

        .num {
            height: 140px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .progress-container {
            width: 80%;
            height: 45px;
            background: #e5e5e5;
            margin: 50px auto;
            border-radius: 30px;
        }

        .progress-bar {
            height: 100%;
            background: #c8102e;
        }
    </style>
</head>

<body>

<h1>여울 팔로워</h1>

<div class="odometer" id="odometer"></div>

<div class="progress-container">
    <div class="progress-bar" style="width: {{ percent }}%;"></div>
</div>

<div>{{ percent }}%</div>

<div>목표까지 {{ remaining }}명</div>

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
    let prev = localStorage.getItem("followers") || current;

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

    # 🔥 캐시 사용
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
