from flask import Flask, render_template_string, jsonify
from playwright.sync_api import sync_playwright
import re
import os
import time
import threading

app = Flask(__name__)

CURRENT_PROFILE_URL = "https://www.instagram.com/kuyeoul/"
TARGET_PROFILE_URL = "https://www.instagram.com/inyon_yonsei/"

CURRENT_LABEL = "여울"
TARGET_LABEL = "연세대학교 인연"

FETCH_INTERVAL = 15

cache = {
    "followers": 7421,
    "target": 8062,
    "timestamp": 0,
    "status": "starting"
}

lock = threading.Lock()


HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>여울 팔로워 트래커</title>

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
            width: {{ percent }}%;
            transition: width 0.5s ease;
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

        .debug {
            margin-top: 25px;
            font-size: 16px;
            color: #aaa;
        }
    </style>
</head>

<body>

    <img src="/static/logo.png" class="logo">

    <div class="followers-label">
        {{ current_label }} 현재 팔로워 수
    </div>

    <div class="odometer" id="odometer"></div>

    <div class="target-number" id="target-number">
        목표: {{ target_label }} ({{ target_formatted }}명)
    </div>

    <div class="progress-container">
        <div class="progress-bar"></div>
    </div>

    <div class="percent" id="percent">
        {{ percent }}%
    </div>

    <div class="remaining">
        {{ target_label }}까지 <span id="remaining">{{ remaining }}</span>!
    </div>

    <div class="subtext">
        목표 달성을 향해 달려가는 중
    </div>

    <div class="debug" id="debug"></div>

<script>
let lastFollowers = null;

function formatNumber(n) {
    return Number(n).toLocaleString();
}

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

function animateOdometer(start, end) {
    const startTime = performance.now();

    function animate(now) {
        const progress = Math.min((now - startTime) / 1000, 1);
        const value = Math.floor(start + (end - start) * progress);

        renderOdometer(value);

        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }

    requestAnimationFrame(animate);
}

function updateUI(data) {
    const current = data.followers;

    if (lastFollowers === null) {
        renderOdometer(current);
    } else if (current !== lastFollowers) {
        animateOdometer(lastFollowers, current);
    }

    lastFollowers = current;

    document.querySelector(".progress-bar").style.width = data.percent + "%";
    document.getElementById("percent").innerText = data.percent + "%";
    document.getElementById("remaining").innerText = data.remaining;

    document.getElementById("target-number").innerText =
        `목표: ${data.target_label} (${formatNumber(data.target)}명)`;

    const updated = data.timestamp
        ? new Date(data.timestamp * 1000).toLocaleTimeString()
        : "아직 수집 전";

    document.getElementById("debug").innerText =
        `status: ${data.status} / current: ${formatNumber(data.followers)} / target: ${formatNumber(data.target)} / updated: ${updated}`;
}

async function syncFollowers() {
    try {
        const res = await fetch("/api/followers?ts=" + Date.now(), {
            cache: "no-store"
        });

        const data = await res.json();

        updateUI(data);
        console.log("[SYNC]", data);
    } catch (e) {
        console.error("[SYNC ERROR]", e);
    }
}

window.onload = function () {
    syncFollowers();
    setInterval(syncFollowers, 3000);
};
</script>

</body>
</html>
"""


def parse_count(raw):
    """
    예:
    7,701 -> 7701
    7.7K -> 7700
    1.2M -> 1200000
    """
    s = raw.strip().replace(",", "").upper()

    if s.endswith("K"):
        return int(float(s[:-1]) * 1000)

    if s.endswith("M"):
        return int(float(s[:-1]) * 1000000)

    if s.endswith("B"):
        return int(float(s[:-1]) * 1000000000)

    return int(float(s))


def extract_followers_from_text(text):
    """
    실제 렌더링된 body 텍스트에서 followers 숫자 추출.
    """
    patterns = [
        r"([\d,.]+[KMB]?)\s+followers",
        r"([\d,.]+[KMB]?)\s+Followers",
        r"팔로워\s*([\d,.]+[KMB]?)",
        r"([\d,.]+[KMB]?)\s*팔로워",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return parse_count(match.group(1))

    return None


def extract_followers_from_meta(page):
    """
    og:description은 캐시된 값일 수 있으므로 fallback으로만 사용.
    """
    try:
        desc = page.locator("meta[property='og:description']").get_attribute("content")

        if not desc:
            return None

        print("[OG DESC]", desc)

        match = re.search(r"([\d,.]+[KMB]?)\s+Followers", desc, re.IGNORECASE)

        if match:
            return parse_count(match.group(1))

    except Exception as e:
        print("[META ERROR]", e)

    return None


def fetch_followers_from_page(page, url, name):
    """
    같은 Playwright page를 재사용해서 특정 Instagram 계정 팔로워 수를 가져옴.
    body 텍스트 우선, og:description은 fallback.
    """
    print(f"[FETCH] {name}: {url}")

    page.goto(
        url,
        timeout=30000,
        wait_until="domcontentloaded"
    )

    time.sleep(5)

    followers = None

    try:
        body_text = page.inner_text("body")
        followers = extract_followers_from_text(body_text)

        if followers is not None:
            print(f"[BODY UPDATED] {name}: {followers}")
            return followers

        print(f"[BODY PARSE FAILED] {name}, trying og:description")

    except Exception as e:
        print(f"[BODY READ ERROR] {name}: {e}")

    followers = extract_followers_from_meta(page)

    if followers is not None:
        print(f"[OG UPDATED] {name}: {followers}")
        return followers

    print(f"[PARSE FAILED] {name}")
    return None


def calculate_percent(followers, target):
    if target <= 0:
        return 0

    return round((followers / target) * 100, 1)


def update_cache(followers=None, target=None, status="ok"):
    with lock:
        if followers is not None:
            cache["followers"] = followers

        if target is not None:
            cache["target"] = target

        cache["timestamp"] = time.time()
        cache["status"] = status


def update_status(status):
    with lock:
        cache["status"] = status


def follower_worker():
    """
    Playwright 브라우저를 1번만 켜고 계속 재사용.
    한 루프에서 여울 팔로워와 인연 팔로워를 둘 다 갱신.
    """
    print("[WORKER] starting")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ]
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1280, "height": 900},
            )

            page = context.new_page()

            while True:
                try:
                    update_status("fetching_current")

                    current_followers = fetch_followers_from_page(
                        page,
                        CURRENT_PROFILE_URL,
                        CURRENT_LABEL
                    )

                    update_status("fetching_target")

                    target_followers = fetch_followers_from_page(
                        page,
                        TARGET_PROFILE_URL,
                        TARGET_LABEL
                    )

                    if current_followers is not None and target_followers is not None:
                        update_cache(
                            followers=current_followers,
                            target=target_followers,
                            status="ok"
                        )
                        print(f"[UPDATED] current={current_followers}, target={target_followers}")

                    elif current_followers is not None:
                        update_cache(
                            followers=current_followers,
                            status="target_parse_failed"
                        )
                        print(f"[PARTIAL UPDATED] current={current_followers}, target failed")

                    elif target_followers is not None:
                        update_cache(
                            target=target_followers,
                            status="current_parse_failed"
                        )
                        print(f"[PARTIAL UPDATED] current failed, target={target_followers}")

                    else:
                        update_status("parse_failed")
                        print("[PARSE FAILED] both profiles failed")

                except Exception as e:
                    update_status(f"error: {str(e)[:80]}")
                    print("[FETCH ERROR]", e)

                    try:
                        page.close()
                    except Exception:
                        pass

                    page = context.new_page()

                time.sleep(FETCH_INTERVAL)

    except Exception as e:
        update_status(f"worker_dead: {str(e)[:80]}")
        print("[WORKER DEAD]", e)


@app.route("/")
def home():
    with lock:
        followers = cache["followers"]
        target = cache["target"]

    percent = calculate_percent(followers, target)
    remaining = max(target - followers, 0)

    return render_template_string(
        HTML,
        followers=followers,
        target=target,
        target_formatted=f"{target:,}",
        percent=percent,
        remaining=remaining,
        current_label=CURRENT_LABEL,
        target_label=TARGET_LABEL
    )


@app.route("/api/followers")
def api_followers():
    with lock:
        followers = cache["followers"]
        target = cache["target"]
        timestamp = cache["timestamp"]
        status = cache["status"]

    percent = calculate_percent(followers, target)
    remaining = max(target - followers, 0)

    return jsonify({
        "followers": followers,
        "target": target,
        "percent": percent,
        "remaining": remaining,
        "timestamp": timestamp,
        "status": status,
        "current_label": CURRENT_LABEL,
        "target_label": TARGET_LABEL
    })


if __name__ == "__main__":
    t = threading.Thread(target=follower_worker, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
