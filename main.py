import time
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import engine, Base, get_db
from app.models import QueryLog
from app.core.cache import find_in_cache, save_to_cache
from app.services.llm_client import ask_gemini

# Tables automatically initialize hongi
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Token Optimization Gateway")

class QueryRequest(BaseModel):
    prompt: str

class QueryResponse(BaseModel):
    cached: bool
    source: str
    similarity_score: float
    latency_ms: float
    response: str

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Token Optimization Gateway</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --card-bg: rgba(16, 24, 40, 0.75);
            --card-border: rgba(255, 255, 255, 0.08);
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.25);
            --hit: #22c55e;
            --hit-bg: rgba(34, 197, 94, 0.15);
            --miss: #f59e0b;
            --miss-bg: rgba(245, 158, 11, 0.15);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body {
            background-color: var(--bg);
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.12) 0px, transparent 50%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 30px 20px;
        }
        .container { width: 100%; max-width: 900px; }
        header { text-align: center; margin-bottom: 25px; }
        header h1 {
            font-size: 1.9rem;
            font-weight: 700;
            background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }
        header p { color: var(--text-secondary); font-size: 0.95rem; }
        .glass-panel {
            background: var(--card-bg);
            backdrop-filter: blur(14px);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 22px;
            margin-bottom: 20px;
        }
        .input-group { display: flex; gap: 12px; }
        input[type="text"] {
            flex: 1;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 14px 18px;
            color: var(--text-primary);
            outline: none;
        }
        input[type="text"]:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }
        button {
            background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
            color: #fff;
            border: none;
            padding: 14px 24px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
        }
        button:hover { opacity: 0.92; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
        .stat-card {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 14px;
            text-align: center;
        }
        .stat-label { font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 4px; }
        .stat-value { font-family: 'JetBrains Mono', monospace; font-size: 1.15rem; font-weight: 700; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
        .badge-hit { background: var(--hit-bg); color: var(--hit); border: 1px solid rgba(34, 197, 94, 0.3); }
        .badge-miss { background: var(--miss-bg); color: var(--miss); border: 1px solid rgba(245, 158, 11, 0.3); }
        .output-box {
            font-family: 'JetBrains Mono', monospace;
            background: rgba(11, 15, 25, 0.9);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 16px;
            min-height: 120px;
            max-height: 380px;
            overflow-y: auto;
            white-space: pre-wrap;
            color: #cbd5e1;
        }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>Smart Token Optimization Gateway</h1>
        <p>Real-Time Semantic Caching & Persistent Query Analytics</p>
    </header>

    <div class="glass-panel">
        <form id="queryForm">
            <div class="input-group">
                <input type="text" id="promptInput" placeholder="Enter prompt..." required autocomplete="off">
                <button type="submit" id="submitBtn">Send Request</button>
            </div>
        </form>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Cache Status</div>
            <div class="stat-value" id="cacheStatus">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Response Time</div>
            <div class="stat-value" id="latency">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Semantic Match</div>
            <div class="stat-value" id="similarity">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Provider</div>
            <div class="stat-value" id="source" style="font-size: 0.95rem;">-</div>
        </div>
    </div>

    <div class="glass-panel">
        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 10px;">OUTPUT RESPONSE</div>
        <div class="output-box" id="outputBox">Response will render here...</div>
    </div>
</div>

<script>
    const form = document.getElementById('queryForm');
    const promptInput = document.getElementById('promptInput');
    const submitBtn = document.getElementById('submitBtn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const prompt = promptInput.value.trim();
        if (!prompt) return;

        submitBtn.disabled = true;
        submitBtn.innerText = 'Processing...';

        try {
            const res = await fetch('/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt })
            });
            const data = await res.json();
            if (res.ok) {
                document.getElementById('cacheStatus').innerHTML = data.cached 
                    ? '<span class="badge badge-hit">HIT</span>' 
                    : '<span class="badge badge-miss">MISS</span>';
                document.getElementById('latency').innerText = `${data.latency_ms} ms`;
                document.getElementById('similarity').innerText = `${(data.similarity_score * 100).toFixed(1)}%`;
                document.getElementById('source').innerText = data.source;
                document.getElementById('outputBox').innerText = data.response;
            }
        } catch (err) {
            document.getElementById('outputBox').innerText = `Error: ${err.message}`;
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = 'Send Request';
        }
    });
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)

@app.post("/query", response_model=QueryResponse)
def process_query(request: QueryRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    
    # 1. Check Cache
    cached_response, similarity_score = find_in_cache(request.prompt)
    
    if cached_response:
        latency = round((time.time() - start_time) * 1000, 2)
        source = "Redis (Local Cache)"
        
        # Save Log in DB
        log = QueryLog(
            prompt=request.prompt,
            response=cached_response,
            is_cached=True,
            similarity_score=similarity_score,
            latency_ms=latency,
            source=source
        )
        db.add(log)
        db.commit()

        return QueryResponse(
            cached=True,
            source=source,
            similarity_score=similarity_score,
            latency_ms=latency,
            response=cached_response
        )
    
    # 2. Cache Miss -> Gemini Call
    try:
        llm_response = ask_gemini(request.prompt)
        save_to_cache(request.prompt, llm_response)
        latency = round((time.time() - start_time) * 1000, 2)
        source = "Google Gemini API"

        # Save Log in DB
        log = QueryLog(
            prompt=request.prompt,
            response=llm_response,
            is_cached=False,
            similarity_score=similarity_score,
            latency_ms=latency,
            source=source
        )
        db.add(log)
        db.commit()

        return QueryResponse(
            cached=False,
            source=source,
            similarity_score=similarity_score,
            latency_ms=latency,
            response=llm_response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    """Summary of saved tokens and hit rates from persistent DB."""
    total_queries = db.query(QueryLog).count()
    cache_hits = db.query(QueryLog).filter(QueryLog.is_cached == True).count()
    cache_misses = total_queries - cache_hits
    hit_ratio = round((cache_hits / total_queries * 100), 2) if total_queries > 0 else 0.0
    
    avg_latency = db.query(func.avg(QueryLog.latency_ms)).scalar() or 0.0

    return {
        "total_queries_logged": total_queries,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "hit_ratio_percent": hit_ratio,
        "average_latency_ms": round(avg_latency, 2),
        "estimated_tokens_saved": cache_hits * 150  # Average 150 tokens per cached hit
    }