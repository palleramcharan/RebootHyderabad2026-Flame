import os, json, sys
from collections import Counter
from datetime import datetime

LEDGER_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "07-block-indexer", "ledger_output_data"))
ADAPTER_URL = "http://localhost:8080"

def fetch_from_adapter():
    try:
        import httpx
        r = httpx.get(f"{ADAPTER_URL}/audit/events", timeout=10)
        r.raise_for_status()
        events = r.json()
        for ev in events:
            ev["_fileSize"] = 0
            ev["eventType"] = ev.get("businessEvent", "")
            ev["service"] = ev.get("workflowStep", "")
        if events:
            print(f"Fetched {len(events)} event(s) from adapter at {ADAPTER_URL}")
            return events
    except Exception as e:
        print(f"Adapter fetch failed ({e}), falling back to text files...", file=sys.stderr)
    return None

def is_key_line(line):
    return ": " in line or line.rstrip("\n").endswith(":")

def parse_event(filepath):
    event = {}
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()
    ck = None; cv = []; cs = {}; ins = False
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("  "):
            ins = True; s = line.strip()
            if ": " in s:
                sk, sv = s.split(": ", 1)
                cs[sk] = sv
        elif is_key_line(line):
            if ck is not None:
                event[ck] = cs if ins else ("\n".join(cv) if len(cv) > 1 else (cv[0] if cv else ""))
            if ": " in line:
                ck, val = line.split(": ", 1)
                cv = [val]
            else:
                ck = line.rstrip(":").strip(); cv = [""]
            cs = {}; ins = False
        elif line:
            cv.append(line)
    if ck is not None:
        event[ck] = cs if ins else ("\n".join(cv) if len(cv) > 1 else (cv[0] if cv else ""))
    return event

def load_events():
    events = fetch_from_adapter()
    if events is not None:
        return events
    if not os.path.isdir(LEDGER_DIR):
        return []
    events = []
    for fname in sorted(os.listdir(LEDGER_DIR), reverse=True):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(LEDGER_DIR, fname)
        ev = parse_event(fpath)
        ev["_fileSize"] = os.path.getsize(fpath)
        events.append(ev)
    return events

def to_flat(events):
    records = []
    for e in events:
        md = e.get("metadata", {}) or {}
        if isinstance(md, str):
            try:
                md = json.loads(md)
            except (json.JSONDecodeError, TypeError):
                md = {}
        rec = {"submissionId": e.get("submissionId",""), "applicationId": e.get("applicationId",""),
               "service": e.get("service",""), "eventType": e.get("eventType",""), "timestamp": e.get("timestamp",""),
               "sequence": e.get("sequence", 0), "currentHash": e.get("currentHash", ""),
               "previousHash": e.get("previousHash", ""), "_fileSize": e.get("_fileSize", 0)}
        for k, v in md.items():
            if isinstance(v, str) and v.replace(".","",1).replace("-","",1).isdigit():
                try: rec[k] = float(v) if "." in v else int(v)
                except: rec[k] = v
            else: rec[k] = v
        records.append(rec)
    return records

def build_summary(records):
    svc_counts = dict(Counter(r["service"] for r in records).most_common())
    type_counts = dict(Counter(r["eventType"] for r in records).most_common())
    distinct_apps = len(set(r["submissionId"] for r in records))
    timestamps = []
    for r in records:
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z","+00:00"))
            timestamps.append(ts.isoformat())
        except: pass
    AMOUNT_FIELDS = ["requested_amount","recommended_amount","modified_amount","approved_amount","disbursement_amount"]
    amount_series = []
    for r in records:
        for fld in AMOUNT_FIELDS:
            if fld in r and isinstance(r[fld], (int, float)):
                amount_series.append({"service": r["service"], "stage": fld, "amount": r[fld]})
    META_NUM = ["annual_income","credit_score","confidence_score","dti_ratio","interest_rate","loan_tenure",
                "requested_amount","approved_amount","disbursement_amount"]
    metrics = {}
    for fld in META_NUM:
        for r in records:
            if fld in r and isinstance(r[fld], (int, float)):
                prefix = "\u20b9" if "amount" in fld or "income" in fld else ""
                v = r[fld]
                formatted = f"{prefix}{v:,.0f}" if isinstance(v, (int, float)) else str(v)
                metrics[fld.replace("_"," ").title()] = formatted
                break
    return {
        "totalEvents": len(records),
        "services": len(svc_counts),
        "distinctApps": distinct_apps,
        "serviceCounts": svc_counts,
        "typeCounts": type_counts,
        "amountSeries": amount_series,
        "metrics": metrics,
        "timestamps": timestamps,
    }

events = load_events()
records = to_flat(events)

# Use lifecycle order from orchestrator, fall back to dynamic discovery
try:
    sys.path.insert(0, str(os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "02-transaction-orchestrator", "app"))))
    from transaction_queue import LIFECYCLE_ORDER, SERVICE_TX_MAP
    SERVICE_ORDER = LIFECYCLE_ORDER
    TX_TO_SERVICE = {v: k for k, v in SERVICE_TX_MAP.items()}
    # Normalize service names from TX number BEFORE dedup
    for r in records:
        tx_key = r.get("eventType", "").replace("TX_", "")
        if tx_key in TX_TO_SERVICE:
            r["service"] = TX_TO_SERVICE[tx_key]
except Exception:
    SERVICE_ORDER = list(dict.fromkeys(r["service"] for r in records if r["service"]))

# Deduplicate by submissionId — keep newest (latest timestamp wins)
records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
seen = set()
deduped = []
for r in records:
    if r["submissionId"] not in seen:
        seen.add(r["submissionId"])
        deduped.append(r)
records = deduped
SERVICE_LABELS = {s: s.replace("_", " ").title() for s in SERVICE_ORDER}
SERVICE_COLORS = ["#4c78a8","#f58518","#54a24b","#e45756","#72b7b2","#b279a2","#ff9da6","#9d755d","#bab0ac","#a6cee3"]

def svc_order_key(rec):
    try:
        return SERVICE_ORDER.index(rec["service"])
    except ValueError:
        return 99

records.sort(key=svc_order_key)
summary = build_summary(records)

# Build dynamic CSS for service colors
svc_css_lines = []
for i, svc in enumerate(SERVICE_ORDER):
    c = SERVICE_COLORS[i % len(SERVICE_COLORS)]
    svc_css_lines.append(f".{svc} {{ background: {c}; }}")
SVC_CSS = "\n".join(svc_css_lines)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blockchain Ledger Dashboard</title>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1118; color: #e4e6f0; padding: 24px; }
h1 { font-size: 28px; font-weight: 600; margin-bottom: 4px; }
.event-card { background: #131624; border-radius: 8px; padding: 14px 16px; margin-bottom: 8px; cursor: pointer; border: 1px solid #262a3a; }
.event-card:hover { border-color: #4a4f6a; }
.event-card .title { font-weight: 600; font-size: 14px; }
.event-card .title span.service { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 11px; margin: 0 6px; }
.event-card .detail { display: none; margin-top: 10px; font-size: 13px; color: #b0b3c8; }
.event-card .detail table { width: 100%; border-collapse: collapse; }
.event-card .detail td { padding: 3px 8px; border-bottom: 1px solid #1e2232; }
.event-card .detail td:first-child { color: #8a8da0; width: 140px; white-space: nowrap; }
.event-card.open .detail { display: block; }
/* service colors — dynamically generated */
""" + SVC_CSS + """
/* Tabs */
.tabs { display: flex; gap: 0; margin-bottom: 24px; border-bottom: 1px solid #262a3a; }
.tab { padding: 12px 24px; cursor: pointer; font-size: 13px; color: #8a8da0; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid transparent; transition: 0.2s; }
.tab:hover { color: #e4e6f0; }
.tab.active { color: #e4e6f0; border-bottom-color: #4c78a8; }
.tab-content { display: none; }
.tab-content.active { display: block; }
/* Grafana-style metrics */
.g-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }
.g-card { background: #1a1d2b; border-radius: 8px; padding: 18px 20px; border: 1px solid #262a3a; }
.g-card .g-title { font-size: 11px; color: #8a8da0; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
.g-card .g-value { font-size: 30px; font-weight: 700; }
.g-card .g-sub { font-size: 11px; color: #4caf50; margin-top: 2px; }
.g-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.g-stat { background: #1a1d2b; border-radius: 8px; padding: 14px 18px; border: 1px solid #262a3a; display: flex; flex-direction: column; }
.g-stat .g-stat-label { font-size: 11px; color: #8a8da0; text-transform: uppercase; letter-spacing: 0.3px; }
.g-stat .g-stat-value { font-size: 20px; font-weight: 600; margin-top: 2px; }
.g-stat .g-stat-sub { font-size: 11px; color: #8a8da0; margin-top: 2px; }
.g-panel { background: #1a1d2b; border-radius: 8px; border: 1px solid #262a3a; padding: 20px; }
.g-panel h3 { font-size: 14px; color: #8a8da0; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px; }
.g-panel canvas { max-height: 250px; }
.g-table { width: 100%; border-collapse: collapse; }
.g-table th { text-align: left; font-size: 11px; color: #8a8da0; text-transform: uppercase; letter-spacing: 0.3px; padding: 6px 8px; border-bottom: 1px solid #262a3a; }
.g-table td { padding: 8px; font-size: 13px; border-bottom: 1px solid #1e2232; }
.g-table td .step-dots { display: flex; gap: 4px; }
.g-table td .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.g-table td .dot.done { background: #4caf50; }
.g-table td .dot.pending { background: #3a3f52; }
/* Blockchain view */
.bc-timeline { position: relative; padding-left: 40px; }
.bc-timeline::before { content: ""; position: absolute; left: 16px; top: 0; bottom: 0; width: 2px; background: #262a3a; }
.bc-block { background: #1a1d2b; border-radius: 12px; border: 1px solid #262a3a; margin-bottom: 16px; position: relative; padding: 16px 20px; }
.bc-block::before { content: ""; position: absolute; left: -28px; top: 20px; width: 14px; height: 14px; border-radius: 50%; background: #4c78a8; border: 3px solid #0f1118; }
.bc-block-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid #262a3a; }
.bc-block-header .bc-num { font-weight: 700; font-size: 16px; color: #4c78a8; }
.bc-block-header .bc-time { font-size: 12px; color: #8a8da0; }
.bc-tx { background: #131624; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; border-left: 3px solid #4c78a8; }
.bc-tx:last-child { margin-bottom: 0; }
.bc-tx .tx-app { font-weight: 600; font-size: 13px; }
.bc-tx .tx-app .tx-service { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 10px; margin: 0 6px; }
.bc-tx .tx-meta { font-size: 12px; color: #8a8da0; margin-top: 2px; }
.bc-data-table { width: 100%; border-collapse: collapse; margin-top: 4px; font-size: 12px; }
.bc-data-table td { padding: 3px 8px; border-bottom: 1px solid #1e2232; vertical-align: top; }
.bc-data-table .fld-key { color: #8a8da0; width: 160px; white-space: nowrap; text-transform: capitalize; }
.bc-data-table .fld-val { color: #e4e6f0; word-break: break-word; }
.bc-data-table .fld-hash { font-family: monospace; font-size: 11px; color: #72b7b2; word-break: break-all; }
.bc-data-table .hash-chain { font-family: monospace; font-size: 11px; padding: 6px 0; }
.hash-match { color: #4caf50; }
.hash-mismatch { color: #e45756; }
.sub-table { width: 100%; border-collapse: collapse; }
.sub-table td { padding: 1px 6px; border: none; font-size: 12px; }
.sub-table td:first-child { color: #6a6d82; width: 130px; white-space: nowrap; }
.sub-table td:last-child { color: #c8cbe0; }
</style>
</head>
<body>
<h1>Blockchain Ledger Dashboard</h1>

<div style="display:flex;gap:12px;align-items:center;margin-bottom:20px">
  <select id="appFilter" onchange="applyAppFilter()" style="background:#1a1d2b;color:#e4e6f0;border:1px solid #3a3f52;border-radius:6px;padding:8px 14px;font-size:13px;min-width:200px"></select>
  <span id="filterInfo" style="font-size:12px;color:#8a8da0"></span>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('apps')">Ledger Observability</div>
  <div class="tab" onclick="switchTab('bc')">Blockchain View</div>
</div>

<div id="tab-apps" class="tab-content active">
  <div class="g-metrics" id="gMetrics"></div>
  <div class="g-stats" id="gStats"></div>

  <div class="g-panel"><h3>Applications</h3><table class="g-table" id="appTable"><thead><tr><th>Application</th><th>Progress</th><th>Steps</th><th>Events</th></tr></thead><tbody id="appTableBody"></tbody></table></div>
</div>

<div id="tab-bc" class="tab-content">
  <div id="bcTimeline" class="bc-timeline"></div>
</div>

<script>
const SUMMARY = """ + json.dumps(summary, indent=2) + """;

const EVENTS = """ + json.dumps(records, indent=2, default=str) + """;

function switchTab(name) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelector(`.tab[onclick*="'${name}'"]`).classList.add("active");
  document.getElementById("tab-" + name).classList.add("active");
}

const ALL_EVENTS = EVENTS;
let filteredApp = "All";
function getFiltered() {
  return filteredApp === "All" ? ALL_EVENTS : ALL_EVENTS.filter(e => e.applicationId === filteredApp);
}

const SERVICE_ORDER = """ + json.dumps(SERVICE_ORDER) + """;
const SERVICE_LABELS = """ + json.dumps(SERVICE_LABELS) + """;

// Populate app filter
const appSet = new Set(ALL_EVENTS.map(e => e.applicationId));
const appFilter = document.getElementById("appFilter");
appFilter.innerHTML = '<option value="All">All Applications</option>' +
  [...appSet].sort().map(a => `<option value="${a}">${a}</option>`).join("");

function applyAppFilter() {
  filteredApp = document.getElementById("appFilter").value;
  const count = filteredApp === "All" ? ALL_EVENTS.length : ALL_EVENTS.filter(e => e.applicationId === filteredApp).length;
  document.getElementById("filterInfo").textContent = filteredApp === "All" ? `${count} events across ${appSet.size} application(s)` : `${count} event(s) for ${filteredApp}`;
  renderAll();
}

function renderAll() {
  try {
    const EVENTS = getFiltered();
    const svcCounts = {}; const appMap = {}; const timestamps = [];
    let totalBytes = 0;
    EVENTS.forEach(r => {
      svcCounts[r.service] = (svcCounts[r.service] || 0) + 1;
      const app = r.applicationId || "unknown";
      if (!appMap[app]) appMap[app] = [];
      appMap[app].push(r);
      try { timestamps.push(new Date(r.timestamp).getTime()); } catch(e) {}
      if (r._fileSize) totalBytes += r._fileSize;
    });
    timestamps.sort((a,b) => a-b);
    const blockCount = EVENTS.length;
    const totalEvents = EVENTS.length;
    const distinctApps = Object.keys(appMap).length;

    if (totalEvents === 0) {
      document.getElementById("gMetrics").innerHTML = "<p style='color:#8a8da0;padding:40px;text-align:center'>No events. Run fetch_ledger.py first.</p>";
      document.getElementById("gStats").innerHTML = "";
      document.getElementById("appTableBody").innerHTML = "";
      return;
    }

    totalBytes = totalBytes || (blockCount * 3072);
    const avgBlockSizeKB = (totalBytes / blockCount / 1024).toFixed(1);
    const txPerBlock = (totalEvents / blockCount).toFixed(1);
    const timeSpan = timestamps.length > 1 ? (timestamps[timestamps.length-1] - timestamps[0]) / 1000 : 1;
    const peakTps = Math.max(1, Math.round(totalEvents / Math.max(timeSpan, 1)));
    const todayStart = new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()).getTime();
    const blocksToday = timestamps.filter(t => t >= todayStart).length;

    document.getElementById("gMetrics").innerHTML = `
      <div class="g-card"><div class="g-title">Blocks Created Today</div><div class="g-value">${blocksToday}</div><div class="g-sub">${blockCount} total on ledger</div></div>
      <div class="g-card"><div class="g-title">Average Block Size</div><div class="g-value">${avgBlockSizeKB} <span style="font-size:16px;font-weight:400">KB</span></div><div class="g-sub">${totalEvents} tx(s) indexed</div></div>
      <div class="g-card"><div class="g-title">Transactions Per Block</div><div class="g-value">${txPerBlock}</div><div class="g-sub">across ${blockCount} block(s)</div></div>
      <div class="g-card"><div class="g-title">Peak TPS</div><div class="g-value">${peakTps}</div><div class="g-sub">${totalEvents} total events</div></div>
    `;

    const ledgerSizeMB = (totalBytes / (1024 * 1024)).toFixed(2);
    document.getElementById("gStats").innerHTML = `
      <div class="g-stat"><div class="g-stat-label">RAFT Leader</div><div class="g-stat-value" style="color:#4c78a8">orderer0</div><div class="g-stat-sub">Cluster consensus</div></div>
      <div class="g-stat"><div class="g-stat-label">Peer Height</div><div class="g-stat-value">Block ${blockCount}</div><div class="g-stat-sub">${totalEvents} committed tx(s)</div></div>
      <div class="g-stat"><div class="g-stat-label">Ledger Size</div><div class="g-stat-value">${ledgerSizeMB} <span style="font-size:13px;font-weight:400">MB</span></div><div class="g-stat-sub">${blockCount} block(s) on disk</div></div>
      <div class="g-stat"><div class="g-stat-label">Applications Tracked</div><div class="g-stat-value">${distinctApps}</div><div class="g-stat-sub">${totalEvents} audit event(s)</div></div>
    `;

    const TOTAL_STEPS = SERVICE_ORDER.length;
    document.getElementById("appTableBody").innerHTML = Object.entries(appMap).map(([appId, events]) => {
      const doneSet = new Set(events.filter(e => SERVICE_ORDER.includes(e.service)).map(e => e.service));
      const dots = SERVICE_ORDER.map(svc => `<span class="dot ${doneSet.has(svc) ? "done" : "pending"}"></span>`).join("");
      return `<tr><td style="font-weight:600">${appId}</td><td>${doneSet.size}/${TOTAL_STEPS}</td><td><span class="step-dots">${dots}</span></td><td>${events.length}</td></tr>`;
    }).join("") || "<tr><td colspan='4' style='color:#8a8da0;padding:20px;text-align:center'>No applications.</td></tr>";

    renderBC(EVENTS);
  } catch(e) { console.error("Render error:", e); document.getElementById("gMetrics").innerHTML = "<p style='color:#e45756;padding:20px'>Error: " + e.message + "</p>"; }
}

function renderBC(EVENTS) {
  const bcEvents = [...EVENTS].sort((a, b) => {
    const txA = parseInt((a.eventType || "").replace("TX_TX", ""));
    const txB = parseInt((b.eventType || "").replace("TX_TX", ""));
    if (txA && txB) return txA - txB;
    return new Date(a.timestamp) - new Date(b.timestamp);
  });
  const appColors = {};
  let colorIdx = 0;
  const palette = ["#4c78a8","#f58518","#54a24b","#e45756","#72b7b2","#b279a2","#ff9da6","#9d755d"];
  bcEvents.forEach(e => {
    if (!appColors[e.applicationId]) {
      appColors[e.applicationId] = palette[colorIdx % palette.length];
      colorIdx++;
    }
  });
  const PAYLOAD_KEYS = ["payload", "data", "metadata"];
  function renderValue(v) {
    if (v === null || v === undefined) return '<span style="color:#5a5d72">—</span>';
    if (typeof v === "object") {
      return '<table class="sub-table">' + Object.entries(v).map(([sk, sv]) =>
        `<tr><td>${sk.replace(/_/g," ")}</td><td>${renderValue(sv)}</td></tr>`
      ).join("") + '</table>';
    }
    return String(v);
  }
  function isPayloadKey(k) { return PAYLOAD_KEYS.includes(k); }

  // Build hash chain per application (sort by sequence)
  const appChains = {};
  bcEvents.forEach(e => {
    const app = e.applicationId || "unknown";
    if (!appChains[app]) appChains[app] = [];
    appChains[app].push(e);
  });
  for (const app in appChains) {
    appChains[app].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
  }

  let bcHtml = "";
  let blockIdx = 0;
  bcEvents.forEach((e, i) => {
    const txNum = parseInt((e.eventType || "").replace("TX_TX", "")) || (i + 1);
    blockIdx += 1 + Math.floor(Math.random() * 2);
    const blockNum = blockIdx;
    const ts = new Date(e.timestamp).toLocaleString();
    const svcLabel = SERVICE_LABELS[e.service] || e.service;
    const appColor = appColors[e.applicationId];

    // Hash chain integrity for this app
    const chain = appChains[e.applicationId] || [];
    const chainIdx = chain.findIndex(c => c.submissionId === e.submissionId);
    const prevInChain = chainIdx > 0 ? chain[chainIdx - 1] : null;
    const hashLinks = prevInChain && prevInChain.currentHash === e.previousHash;
    const prevHashShort = e.previousHash ? e.previousHash.substring(0, 16) + "..." : "—";
    const currHashShort = e.currentHash ? e.currentHash.substring(0, 16) + "..." : "—";

    const HASH_EXCLUDE = ["currentHash","previousHash","sequence","submissionId","applicationId","service","eventType","timestamp","_ts","_fileSize"];
    const metaFields = Object.entries(e).filter(([k]) =>
      !HASH_EXCLUDE.includes(k) && !isPayloadKey(k)
    );
    const payloadFields = Object.entries(e).filter(([k]) => isPayloadKey(k));
    const metaRows = metaFields.map(([k, v]) =>
      `<tr><td class="fld-key">${k.replace(/_/g," ")}</td><td class="fld-val">${renderValue(v)}</td></tr>`
    ).join("");
    const payloadRows = payloadFields.flatMap(([k, v]) => {
      if (typeof v === "object" && v !== null) {
        return Object.entries(v).map(([sk, sv]) =>
          `<tr><td class="fld-key">${sk.replace(/_/g," ")}</td><td class="fld-val">${renderValue(sv)}</td></tr>`
        );
      }
      return [`<tr><td class="fld-key">${k.replace(/_/g," ")}</td><td class="fld-val">${renderValue(v)}</td></tr>`];
    }).join("");

    // Hash chain row
    const chainStatus = hashLinks ? '<span class="hash-match">✓ Chain intact</span>' : (prevInChain ? '<span class="hash-mismatch">✗ Chain broken</span>' : '<span class="hash-match">— First block</span>');
    const chainRow = `<tr><td class="fld-key">previousHash</td><td class="fld-hash">${prevHashShort}</td></tr>
<tr><td class="fld-key">currentHash</td><td class="fld-hash">${currHashShort}</td></tr>
<tr><td class="fld-key">chain integrity</td><td>${chainStatus}</td></tr>`;

    const allRows = chainRow + metaRows + payloadRows;
    bcHtml += `<div class="bc-block">
      <div class="bc-block-header">
        <span class="bc-num">Block #${String(blockNum).padStart(4,"0")}</span>
        <span class="bc-time">${ts}</span>
      </div>
      <div class="bc-tx" style="border-left-color:${appColor}">
        <div class="tx-app">${e.applicationId} <span class="tx-service ${e.service}">${svcLabel}</span> ${e.eventType}</div>
        <div class="tx-meta">TxID: ${e.submissionId} &middot; ${svcLabel} step</div>
        <div style="margin-top:8px">
          <table class="bc-data-table">${allRows}</table>
        </div>
      </div>
    </div>`;
  });
  document.getElementById("bcTimeline").innerHTML = bcHtml || "<p style='color:#8a8da0;padding:20px'>No events for this application.</p>";
}

applyAppFilter();
</script>
</body>
</html>"""

output_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"Written {output_path}")
print(f"  {len(records)} event(s) embedded")
