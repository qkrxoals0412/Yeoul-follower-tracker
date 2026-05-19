from flask import Flask, render_template_string
from playwright.sync_api import sync_playwright
import re
import os

app = Flask(__name__)

TARGET = 8062

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

        .followers {
            font-size: 140px;
            font-weight: bold;
            color: #111;
            line-height: 1;
        }

        .followers span {
            font-size: 50px;
            margin-left: 10px;
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

    <div class="followers">
        {{ followers }}<span>명</span>
    </div>

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

</body>

</html>
"""


def get_followers():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox"]
            )

            page = browser.new_page()

            url = "https://www.instagram.com/kuyeoul/"
            page.goto(url, timeout=60000)

            # 안정적으로 meta 태그 로딩 대기
            page.wait_for_selector("meta[property='og:description']", timeout=10000)

            desc = page.locator("meta[property='og:description']").get_attribute("content")

            browser.close()

            if not desc:
                return 7421

            match = re.search(r"([\d,]+)\sFollowers", desc)

            if match:
                return int(match.group(1).replace(",", ""))

            return 7421

    except Exception as e:
        print("ERROR:", e)
        return 7421


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
