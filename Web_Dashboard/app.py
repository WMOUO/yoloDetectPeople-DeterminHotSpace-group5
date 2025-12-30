# app.py — AWS IoT MQTT -> CSV + Web Dashboard
# Requirement: "10 秒一到就記錄一次"（不需等下一筆 MQTT）
# Hot event rule (per zone):
# - When zone turns ON, start timer
# - As soon as continuous ON reaches HOT_SECONDS, record hot_count += 1 immediately
# - Same ON period counts only once; must go OFF then ON again to count again
#
# Features:
# - Subscribe AWS IoT MQTT topics
# - Log all incoming messages to peopleflow.csv
# - 9-grid LED status (last_state) + cumulative ON/OFF counts
# - Bar chart: cumulative ON/OFF counts per zone
# - Bar chart: hot event counts per zone (10s reached => +1)
#
# Requirements:
#   pip install fastapi uvicorn awsiotsdk
#
# Run:
#   uvicorn app:app --host 0.0.0.0 --port 8000
#
# Put these files next to app.py:
#   AmazonRootCA1.pem
#   device-certificate.pem.crt
#   private.pem.key

import csv
import json
import threading
import time
from collections import deque, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

# ========= AWS IoT =========
ENDPOINT = "a10eer929bk2gd-ats.iot.us-east-1.amazonaws.com"
TOPICS = [
    "project/led_control",
    "project/esp8266_led",
]
CLIENT_ID = "local_peopleflow_logger"

ROOT_CA = "AmazonRootCA1.pem"
CERT = "device-certificate.pem.crt"
PRIVATE_KEY = "private.pem.key"

# ========= Hot-zone rule =========
HOT_SECONDS = 10

# ========= CSV =========
CSV_PATH = Path("peopleflow.csv")
CSV_HEADER = ["ts_utc", "topic", "raw", "zone", "state"]

# ========= In-memory =========
events = deque(maxlen=5000)
lock = threading.Lock()

# Per-zone runtime state
# last_state: 0/1/None
# on_since: epoch seconds when ON started
# hot_counted: whether this ON period already counted a hot event
# hot_count: total hot events recorded
zone_state: Dict[int, Dict[str, Any]] = {
    z: {"last_state": None, "on_since": None, "hot_counted": False, "hot_count": 0}
    for z in range(1, 10)
}

# ========= CSV helpers =========
def ensure_csv() -> None:
    if not CSV_PATH.exists():
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)

def append_csv(row: dict) -> None:
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([row.get(h, "") for h in CSV_HEADER])

# ========= Payload parsing =========
def parse_payload(raw: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Supports:
      - Plain digits: "11","10","21","20"... (tens=zone, ones=state)
      - JSON: {"message":"11"} or {"zone":1,"present":1} / {"zone":1,"state":1}
    Returns (zone, state) where state is 1=ON, 0=OFF
    """
    raw = raw.strip()

    # JSON
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if "zone" in obj and ("present" in obj or "state" in obj):
                z = int(obj["zone"])
                s = int(obj.get("present", obj.get("state")))
                if 1 <= z <= 9 and s in (0, 1):
                    return z, s
            if "message" in obj:
                raw = str(obj["message"]).strip()
        except Exception:
            pass

    # Plain digits
    if raw.isdigit():
        v = int(raw)
        z, s = v // 10, v % 10
        if 1 <= z <= 9 and s in (0, 1):
            return z, s

    return None, None

# ========= MQTT callback =========
def on_message(topic, payload, **kwargs):
    raw = payload.decode("utf-8", errors="ignore").strip()
    ts = datetime.now(timezone.utc).isoformat()
    now = time.time()

    zone, state = parse_payload(raw)

    row = {
        "ts_utc": ts,
        "topic": str(topic),
        "raw": raw,
        "zone": zone,
        "state": state,
    }

    with lock:
        events.appendleft(row)
        append_csv(row)

        # Update per-zone state (timer start/reset)
        if zone is not None and state in (0, 1):
            zs = zone_state[zone]
            prev = zs["last_state"]

            if state == 1:
                # OFF/None -> ON: start new ON period
                if prev != 1:
                    zs["on_since"] = now
                    zs["hot_counted"] = False
                zs["last_state"] = 1
            else:
                # ON -> OFF: reset ON period
                zs["last_state"] = 0
                zs["on_since"] = None
                zs["hot_counted"] = False

    print(f"[MQTT] {topic} {raw} -> zone={zone} state={state}")

# ========= Background checker =========
def hot_checker():
    """
    Every 0.2s check if any zone has been continuously ON for >= HOT_SECONDS.
    When threshold is reached, record hot_count += 1 immediately (only once per ON period).
    """
    while True:
        time.sleep(0.2)
        now = time.time()
        with lock:
            for z in range(1, 10):
                zs = zone_state[z]
                if (
                    zs["last_state"] == 1
                    and not zs["hot_counted"]
                    and zs["on_since"] is not None
                    and (now - zs["on_since"]) >= HOT_SECONDS
                ):
                    zs["hot_count"] += 1
                    zs["hot_counted"] = True
                    print(f"[HOT] Zone {z} hot event recorded (>= {HOT_SECONDS}s)")

def start_mqtt():
    # Check cert files exist
    for p in [ROOT_CA, CERT, PRIVATE_KEY]:
        if not Path(p).exists():
            raise FileNotFoundError(f"Missing file: {p} (put it next to app.py)")

    elg = io.EventLoopGroup(1)
    resolver = io.DefaultHostResolver(elg)
    bootstrap = io.ClientBootstrap(elg, resolver)

    conn = mqtt_connection_builder.mtls_from_path(
        endpoint=ENDPOINT,
        cert_filepath=CERT,
        pri_key_filepath=PRIVATE_KEY,
        ca_filepath=ROOT_CA,
        client_bootstrap=bootstrap,
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30,
    )

    print("Connecting to AWS IoT Core...")
    conn.connect().result()
    print("Connected. Subscribing...")

    for t in TOPICS:
        conn.subscribe(t, mqtt.QoS.AT_LEAST_ONCE, on_message)[0].result()
        print("Subscribed:", t)

    while True:
        time.sleep(1)

# ========= Stats =========
def compute_counts():
    """
    Cumulative ON/OFF counts and last_state derived from events.
    """
    by_zone = defaultdict(lambda: {"on": 0, "off": 0, "last_state": None})
    for z in range(1, 10):
        _ = by_zone[z]

    # events newest-first; iterate reversed so last_state ends up as newest
    for e in reversed(list(events)):
        z, s = e.get("zone"), e.get("state")
        if z is None or s is None:
            continue
        if s == 1:
            by_zone[z]["on"] += 1
        elif s == 0:
            by_zone[z]["off"] += 1
        by_zone[z]["last_state"] = s

    return by_zone

def compute_hot_counts():
    """
    Returns hot_count per zone and current ON duration.
    """
    now = time.time()
    out = {}
    for z in range(1, 10):
        zs = zone_state[z]
        dur = 0.0
        if zs["last_state"] == 1 and zs["on_since"] is not None:
            dur = max(0.0, now - zs["on_since"])
        out[z] = {
            "hot_count": int(zs["hot_count"]),
            "on_duration_sec": dur,
            "is_hot_now": dur >= HOT_SECONDS,
        }
    return out

# ========= Web UI =========
HTML_PAGE = f"""
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>人流紀錄 Dashboard</title>
  <style>
    body{{font-family:system-ui,-apple-system,"Noto Sans TC",sans-serif;margin:20px}}
    .row{{display:flex;gap:16px;flex-wrap:wrap}}
    .card{{border:1px solid #ddd;border-radius:12px;padding:14px;min-width:260px}}
    table{{border-collapse:collapse;width:100%}}
    th,td{{border-bottom:1px solid #eee;padding:6px 8px;text-align:left;font-size:14px}}
    th{{background:#fafafa}}
    .muted{{color:#666}}
    .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace}}

    .led-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:8px}}
    .led{{border:1px solid #ddd;border-radius:12px;padding:12px;text-align:center;user-select:none}}
    .led-circle{{width:28px;height:28px;border-radius:50%;margin:6px auto 8px;border:2px solid #bbb;background:#f5f5f5}}
    .led.on .led-circle{{background:#22c55e;border-color:#16a34a;box-shadow:0 0 10px rgba(34,197,94,.7)}}
    .led.off .led-circle{{background:#e5e7eb}}
    .led.unknown .led-circle{{background:#fff;border-style:dashed}}
  </style>
</head>
<body>
  <h2>人流紀錄 Dashboard</h2>
  <div class="muted">
    熱區事件規則：同一區連續 ON ≥ {HOT_SECONDS} 秒，滿秒當下立即記錄一次；同一段 ON 只算一次（需 OFF 後再 ON 才能再算）
  </div>

  <div class="row" style="margin-top:14px">
    <div class="card" style="flex:1;min-width:320px">
      <h3 style="margin:0 0 8px 0">9 宮格 LED（最後狀態）</h3>
      <div id="leds" class="led-grid"></div>

      <h3 style="margin:14px 0 8px 0">累積統計（ON / OFF 次數）</h3>
      <canvas id="countChart" height="120"></canvas>

      <h3 style="margin:14px 0 8px 0">熱區事件次數（≥ {HOT_SECONDS} 秒算一次）</h3>
      <canvas id="hotChart" height="120"></canvas>
    </div>

    <div class="card" style="flex:2;min-width:720px">
      <h3 style="margin:0 0 8px 0">最新事件（最近 50 筆）</h3>
      <table>
        <thead>
          <tr><th>時間(UTC)</th><th>topic</th><th>raw</th><th>zone</th><th>state</th></tr>
        </thead>
        <tbody id="events"></tbody>
      </table>
    </div>
  </div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
const fmtState = (s)=> s===1 ? "ON(有人)" : s===0 ? "OFF(無人)" : "-";
const esc = (s)=> String(s ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");

let countChart=null;
let hotChart=null;

async function refresh(){{
  const st = await fetch("/api/stats").then(r=>r.json());
  const ht = await fetch("/api/heat").then(r=>r.json());

  // ===== LED grid =====
  const leds = document.getElementById("leds");
  leds.innerHTML = "";
  for(let z=1; z<=9; z++) {{
    const v = st.by_zone[String(z)] || {{}};
    const cls = v.last_state===1 ? "on" : v.last_state===0 ? "off" : "unknown";
    leds.innerHTML += `
      <div class="led ${{cls}}">
        <div><b>Zone ${{z}}</b></div>
        <div class="led-circle"></div>
        <div class="muted">ON:${{v.on||0}} / OFF:${{v.off||0}}</div>
      </div>`;
  }}

  const labels = Array.from({{length:9}}, (_,i)=>`Zone ${{i+1}}`);

  // ===== Count chart (ON/OFF) =====
  const onData=[], offData=[];
  for(let z=1; z<=9; z++) {{
    const v = st.by_zone[String(z)] || {{}};
    onData.push(v.on || 0);
    offData.push(v.off || 0);
  }}
  {{
    const ctx = document.getElementById("countChart").getContext("2d");
    if(!countChart){{
      countChart = new Chart(ctx, {{
        type:"bar",
        data:{{labels,datasets:[
          {{label:"ON 次數", data:onData}},
          {{label:"OFF 次數", data:offData}}
        ]}},
        options:{{responsive:true, animation:false, scales:{{y:{{beginAtZero:true, ticks:{{precision:0}}}}}}}}
      }});
    }} else {{
      countChart.data.datasets[0].data = onData;
      countChart.data.datasets[1].data = offData;
      countChart.update();
    }}
  }}

  // ===== Hot chart (hot events) =====
  const hotCounts=[];
  for(let z=1; z<=9; z++) {{
    const v = ht.by_zone[String(z)] || {{}};
    hotCounts.push(v.hot_count || 0);
  }}
  {{
    const ctx = document.getElementById("hotChart").getContext("2d");
    if(!hotChart){{
      hotChart = new Chart(ctx, {{
        type:"bar",
        data:{{labels,datasets:[
          {{label:"熱區事件次數", data:hotCounts}}
        ]}},
        options:{{responsive:true, animation:false, scales:{{y:{{beginAtZero:true, ticks:{{precision:0}}}}}}}}
      }});
    }} else {{
      hotChart.data.datasets[0].data = hotCounts;
      hotChart.update();
    }}
  }}

  // ===== Events table =====
  const ev = await fetch("/api/events?limit=50").then(r=>r.json());
  const tbody = document.getElementById("events");
  tbody.innerHTML = ev.events.map(e => `
    <tr>
      <td>${{esc(e.ts_utc)}}</td>
      <td class="mono">${{esc(e.topic)}}</td>
      <td class="mono">${{esc(e.raw)}}</td>
      <td>${{e.zone ?? "-"}}</td>
      <td>${{fmtState(e.state)}}</td>
    </tr>
  `).join("");
}}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_csv()
    threading.Thread(target=start_mqtt, daemon=True).start()
    threading.Thread(target=hot_checker, daemon=True).start()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

@app.get("/api/events")
def api_events(limit: int = 50):
    limit = max(1, min(200, limit))
    with lock:
        return {"events": list(events)[:limit]}

@app.get("/api/stats")
def api_stats():
    with lock:
        by_zone = compute_counts()
    return JSONResponse({"by_zone": {str(k): v for k, v in by_zone.items()}})

@app.get("/api/heat")
def api_heat():
    with lock:
        hz = compute_hot_counts()
    return JSONResponse({
        "hot_seconds": HOT_SECONDS,
        "by_zone": {str(z): {"hot_count": hz[z]["hot_count"]} for z in range(1, 10)}
    })
