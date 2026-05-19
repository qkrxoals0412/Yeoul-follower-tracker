from flask import Flask, render_template_string, jsonify, request
import os
import time
import threading

app = Flask(__name__)

CURRENT_LABEL = "여울"
TARGET_LABEL = "연세대학교 인연"

UPDATE_SECRET = os.environ.get("UPDATE_SECRET", "123kjh123k0b87sdfalj3n24rbbv087b0a8d7u")

cache = {
    "followers": 7421,
    "target": 8062,
    "timestamp": 0,
    "status": "waiting_for_local_update",
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
}

async function syncFollowers() {
    try {
        const res = await fetch("/api/followers?ts=" + Date.now(), {
            cache: "no-store"
        });

        const data = await res.json();
        updateUI(data);
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


def calculate_percent(followers, target):
    if target <= 0:
        return 0
    return round((followers / target) * 100, 1)


def update_cache(followers, target, status="updated"):
    with lock:
        cache["followers"] = followers
        cache["target"] = target
        cache["timestamp"] = time.time()
        cache["status"] = status


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
        target_label=TARGET_LABEL,
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
        "target_label": TARGET_LABEL,
    })


@app.route("/update", methods=["POST"])
def update_from_local():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "invalid json"}), 400

    if data.get("secret") != UPDATE_SECRET:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    followers = data.get("followers")
    target = data.get("target")

    if not isinstance(followers, int) or not isinstance(target, int):
        return jsonify({"ok": False, "error": "followers and target must be int"}), 400

    update_cache(
        followers=followers,
        target=target,
        status="updated_from_local",
    )

    print(
        f"[UPDATE] followers={followers}, target={target}",
        flush=True,
    )

    return jsonify({
        "ok": True,
        "followers": followers,
        "target": target,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )
