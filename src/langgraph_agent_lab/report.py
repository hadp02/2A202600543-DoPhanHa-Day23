# ruff: noqa: E501
"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data."""
    scenario_rows = []
    for s in metrics.scenario_metrics:
        success_str = "✅ Yes" if s.success else "❌ No"
        scenario_rows.append(
            f"| {s.scenario_id} | {s.expected_route} | {s.actual_route or 'N/A'} | {success_str} | {s.retry_count} | {s.interrupt_count} |"
        )
    table_content = "\n".join(scenario_rows)

    report_md = f"""# Day 08 Lab Report — LangGraph Agentic Orchestration

## 1. Team / student

- **Name**: Student & Antigravity AI Pair Programming Team
- **Repo/commit**: Day 08 LangGraph Agent Lab (Production-style Orchestration)
- **Date**: 2026-06-29
- **Overall Success Rate**: {metrics.success_rate:.2%} ({metrics.total_scenarios} scenarios tested)

## 2. Architecture

The workflow is structured as a robust **LangGraph StateGraph** designed for handling support-ticket operations. Key architectural components include:
- **Intake & Classification**: Raw user queries enter via `intake` and are routed by `classify` using structured LLM output (`with_structured_output`) into 5 distinct priority routes (`risky` > `tool` > `missing_info` > `error` > `simple`).
- **Conditional Routing**: 4 dedicated routing gates (`route_after_classify`, `route_after_evaluate`, `route_after_retry`, `route_after_approval`) dynamically direct the agent flow based on state evaluation.
- **Retry Loop Gate & LLM-as-a-Judge**: The `evaluate` node acts as an intelligent quality gate utilizing structured LLM output (`EvaluationJudge`) to evaluate tool lookup completeness and factual accuracy before allowing the workflow to proceed or triggering a retry up to `max_attempts`.
- **Human-In-The-Loop (HITL)**: High-risk operations (refunds, account deletions) pass through `risky_action` and pause at `approval` for human verification.
- **Unified Termination**: All paths converge at `finalize` to emit comprehensive audit logs before reaching `END`.

## 3. State schema

The workflow manages state via `AgentState` (TypedDict) utilizing lean serializable data structures and explicit reducer annotations:

| Field | Reducer | Why |
|---|---|---|
| `messages` | append (`add`) | Retains complete audit history of conversation and prompts |
| `tool_results` | append (`add`) | Records outputs from tool lookups across multiple retry attempts |
| `errors` | append (`add`) | Logs transient failure messages and stack traces during retries |
| `events` | append (`add`) | Normalized `LabEvent` tracking for latency, node visits, and grading metrics |
| `route` | overwrite | Maintains the active execution path decided by classification |
| `risk_level` | overwrite | Identifies whether the current transaction requires elevated scrutiny |
| `attempt` | overwrite | Tracks the current retry counter to prevent unbounded loops |
| `evaluation_result`| overwrite | Drives conditional routing between success answer and retry fallback |
| `approval` | overwrite | Captures reviewer decision (`approved`, `reviewer`, `comment`) |

## 4. Scenario results

Summary Metrics:
- **Total Scenarios**: {metrics.total_scenarios}
- **Success Rate**: {metrics.success_rate:.2%}
- **Average Nodes Visited**: {metrics.avg_nodes_visited:.1f}
- **Total Retries Executed**: {metrics.total_retries}
- **Total HITL Interrupts**: {metrics.total_interrupts}

Per-Scenario Execution Table:

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
{table_content}

## 5. Failure analysis

We analyzed and mitigated several critical failure modes:
1. **Transient Tool Failure & Unbounded Retries**: When calling external lookup services (`S05_error`), network timeouts can occur. Without bounded checks, the agent could loop infinitely producing high API costs. We mitigated this by tracking `attempt` against `max_attempts` in `route_after_retry`. Once exhausted (`S07_dead_letter`), the ticket is gracefully moved to `dead_letter`.
2. **Unauthorized Risky Actions**: Queries requesting refunds or account deletions (`S04_risky`, `S06_delete`) carry high business risk if hallucinated or executed autonomously. We enforced a strict priority rule in LLM classification and inserted a mandatory HITL `approval` node gate. If rejected, the system routes to `clarify` instead of executing the tool.

## 6. Persistence / recovery evidence

The workflow integrates LangGraph checkpointers (`MemorySaver` and `SqliteSaver`). By isolating execution state per `thread_id` (`thread-<scenario_id>`), the system guarantees thread safety across concurrent user sessions. Checkpointing preserves full checkpoint history after every graph step, enabling crash-resume capabilities and state inspection at any intermediate node.

## 7. Extension work

We completed the following bonus extensions:
- **SQLite Checkpointer Integration**: Extended `persistence.py` to support `SqliteSaver` backed by SQLite WAL (Write-Ahead Logging) mode (`PRAGMA journal_mode=WAL;`), providing production-ready disk persistence that survives process restarts.
- **LLM-as-a-Judge QA Evaluation**: Upgraded `evaluate_node` from static string heuristic checks to an advanced AI QA Judge pattern (`EvaluationJudge`) that evaluates tool execution accuracy against user queries with structured reasoning logs.
- **Robust Offline Fallback**: Designed multi-layered fallback handling in LLM nodes so automated grading and CI pipelines run seamlessly even when external LLM endpoints experience outages.

## 8. Improvement plan

If given additional time to productionize this workflow, we would prioritize:
1. **PostgreSQL Checkpointer & Async Fan-out**: Deploying `AsyncPostgresSaver` for distributed multi-instance scaling and utilizing LangGraph's `Send()` API to execute parallel tool lookups concurrently.
2. **Real-time Webhook Dashboard**: Integrating automated Slack/Microsoft Teams webhook alerts when tickets hit `dead_letter` or require high-priority HITL approval.
"""
    return report_md


def render_html_report(metrics: MetricsReport) -> str:
    """Render a premium, interactive HTML dashboard from metrics data."""
    import json
    scenario_data = [
        {
            "id": s.scenario_id,
            "expected": s.expected_route,
            "actual": s.actual_route or "N/A",
            "success": s.success,
            "retries": s.retry_count,
            "interrupts": s.interrupt_count,
            "nodes": s.nodes_visited,
        }
        for s in metrics.scenario_metrics
    ]
    data_json = json.dumps(scenario_data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Day 08 LangGraph Agent Lab — Production Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-main: #0f172a;
            --bg-card: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-cyan: #38bdf8;
            --accent-indigo: #818cf8;
            --accent-green: #34d399;
            --accent-red: #f87171;
            --accent-amber: #fbbf24;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', sans-serif;
            background: radial-gradient(circle at top right, #1e1b4b, var(--bg-main) 50%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 2rem;
            line-height: 1.6;
        }}
        .container {{ max-width: 1300px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
        }}
        h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-indigo));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .badges {{ display: flex; gap: 0.75rem; }}
        .badge {{
            padding: 0.4rem 0.8rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            background: rgba(129, 140, 248, 0.15);
            color: var(--accent-indigo);
            border: 1px solid rgba(129, 140, 248, 0.3);
        }}
        .badge.success {{
            background: rgba(52, 211, 153, 0.15);
            color: var(--accent-green);
            border-color: rgba(52, 211, 153, 0.3);
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}
        .kpi-card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            border-color: var(--accent-cyan);
        }}
        .kpi-label {{ font-size: 0.9rem; color: var(--text-muted); font-weight: 500; }}
        .kpi-value {{ font-size: 2.5rem; font-weight: 700; margin-top: 0.5rem; color: var(--text-main); }}
        .charts-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}
        @media (max-width: 900px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
        .card {{
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.75rem;
        }}
        .card h2 {{ font-size: 1.3rem; margin-bottom: 1.25rem; color: var(--accent-cyan); }}
        .filters {{ display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
        .filter-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }}
        .filter-btn.active, .filter-btn:hover {{
            background: var(--accent-indigo);
            color: #fff;
            border-color: var(--accent-indigo);
        }}
        .search-box {{
            flex-grow: 1;
            min-width: 250px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.5rem 1rem;
            color: #fff;
            font-size: 0.95rem;
        }}
        .search-box:focus {{ outline: none; border-color: var(--accent-cyan); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; }}
        th, td {{ padding: 1rem; border-bottom: 1px solid var(--border-color); }}
        th {{ font-weight: 600; color: var(--text-muted); font-size: 0.9rem; text-transform: uppercase; }}
        tr:hover td {{ background: rgba(255, 255, 255, 0.03); }}
        .status-pill {{
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .status-pill.success {{ background: rgba(52, 211, 153, 0.2); color: var(--accent-green); }}
        .status-pill.fail {{ background: rgba(248, 113, 113, 0.2); color: var(--accent-red); }}
        .route-tag {{
            font-family: monospace;
            padding: 0.2rem 0.5rem;
            background: rgba(0, 0, 0, 0.4);
            border-radius: 4px;
            color: var(--accent-cyan);
        }}
        .arch-section {{ margin-top: 2.5rem; }}
        .arch-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-top: 1.25rem; }}
        .arch-item h3 {{ font-size: 1.1rem; color: var(--accent-indigo); margin-bottom: 0.5rem; }}
        .arch-item p {{ font-size: 0.95rem; color: var(--text-muted); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>LangGraph Agentic Orchestration</h1>
                <p style="color: var(--text-muted); margin-top: 0.3rem;">Day 08 Lab Report & Interactive Benchmark Dashboard</p>
            </div>
            <div class="badges">
                <span class="badge">LLM-as-a-Judge QA</span>
                <span class="badge">SQLite WAL Checkpoint</span>
                <span class="badge success">Success Rate: {metrics.success_rate:.2%}</span>
            </div>
        </header>

        <section class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Overall Success Rate</div>
                <div class="kpi-value" style="color: var(--accent-green);">{metrics.success_rate:.0%}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total Scenarios Tested</div>
                <div class="kpi-value">{metrics.total_scenarios}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Avg Nodes Visited</div>
                <div class="kpi-value" style="color: var(--accent-cyan);">{metrics.avg_nodes_visited:.1f}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total Retries Executed</div>
                <div class="kpi-value" style="color: var(--accent-amber);">{metrics.total_retries}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">HITL Approvals Required</div>
                <div class="kpi-value" style="color: var(--accent-indigo);">{metrics.total_interrupts}</div>
            </div>
        </section>

        <section class="charts-grid">
            <div class="card">
                <h2>Execution Complexity per Scenario</h2>
                <canvas id="complexityChart" height="130"></canvas>
            </div>
            <div class="card">
                <h2>Route Distribution</h2>
                <canvas id="routeChart" height="200"></canvas>
            </div>
        </section>

        <section class="card">
            <h2>Scenario Execution Results</h2>
            <div class="filters">
                <button class="filter-btn active" onclick="filterTable('all', this)">All Scenarios ({metrics.total_scenarios})</button>
                <button class="filter-btn" onclick="filterTable('passed', this)">Passed ✅</button>
                <button class="filter-btn" onclick="filterTable('retry', this)">With Retries 🔄</button>
                <button class="filter-btn" onclick="filterTable('hitl', this)">HITL Approval 🛡️</button>
                <input type="text" class="search-box" id="searchInput" placeholder="Search by Scenario ID or Route..." onkeyup="searchTable()">
            </div>
            <table id="scenariosTable">
                <thead>
                    <tr>
                        <th>Scenario ID</th>
                        <th>Expected Route</th>
                        <th>Actual Route</th>
                        <th>Status</th>
                        <th>Nodes Visited</th>
                        <th>Retries</th>
                        <th>HITL Interrupts</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
        </section>

        <section class="arch-section card">
            <h2>Production Architecture Highlights</h2>
            <div class="arch-grid">
                <div class="arch-item">
                    <h3>🧠 LLM-as-a-Judge Evaluation Gate</h3>
                    <p>Upgraded `evaluate_node` to use structured AI evaluation (`EvaluationJudge`). The judge inspects tool outputs against the original user query, providing grounded reasoning logs instead of simple keyword checks.</p>
                </div>
                <div class="arch-item">
                    <h3>💾 SQLite WAL Checkpointer</h3>
                    <p>Thread-safe state persistence isolated per `thread_id`. Write-Ahead Logging (`journal_mode=WAL`) ensures zero data corruption during concurrent executions and enables full crash recovery.</p>
                </div>
                <div class="arch-item">
                    <h3>🛡️ Strict Priority Classification</h3>
                    <p>Structured output intent routing enforcing strict hierarchy (`risky` > `tool` > `missing_info` > `error` > `simple`) to prevent unauthorized actions and protect business logic.</p>
                </div>
            </div>
        </section>
    </div>

    <script>
        const rawData = {data_json};
        
        function renderTable(data) {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = data.map(row => `
                <tr>
                    <td style="font-weight: 600;">${{row.id}}</td>
                    <td><span class="route-tag">${{row.expected}}</span></td>
                    <td><span class="route-tag" style="border-color: var(--accent-cyan);">${{row.actual}}</span></td>
                    <td><span class="status-pill ${{row.success ? 'success' : 'fail'}}">${{row.success ? 'Passed ✅' : 'Failed ❌'}}</span></td>
                    <td>${{row.nodes}}</td>
                    <td>${{row.retries > 0 ? `<span style="color: var(--accent-amber); font-weight:bold;">${{row.retries}} 🔄</span>` : '0'}}</td>
                    <td>${{row.interrupts > 0 ? `<span style="color: var(--accent-indigo); font-weight:bold;">${{row.interrupts}} 🛡️</span>` : '0'}}</td>
                </tr>
            `).join('');
        }}

        renderTable(rawData);

        function filterTable(type, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            let filtered = rawData;
            if (type === 'passed') filtered = rawData.filter(d => d.success);
            if (type === 'retry') filtered = rawData.filter(d => d.retries > 0);
            if (type === 'hitl') filtered = rawData.filter(d => d.interrupts > 0);
            renderTable(filtered);
        }}

        function searchTable() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const filtered = rawData.filter(d => d.id.toLowerCase().includes(query) || d.actual.toLowerCase().includes(query));
            renderTable(filtered);
        }}

        // Charts
        const ctxComplexity = document.getElementById('complexityChart').getContext('2d');
        new Chart(ctxComplexity, {{
            type: 'bar',
            data: {{
                labels: rawData.map(d => d.id),
                datasets: [
                    {{
                        label: 'Nodes Visited',
                        data: rawData.map(d => d.nodes),
                        backgroundColor: 'rgba(56, 189, 248, 0.6)',
                        borderColor: '#38bdf8',
                        borderWidth: 1,
                        borderRadius: 6
                    }},
                    {{
                        label: 'Retry Count',
                        data: rawData.map(d => d.retries),
                        backgroundColor: 'rgba(251, 191, 36, 0.6)',
                        borderColor: '#fbbf24',
                        borderWidth: 1,
                        borderRadius: 6
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#94a3b8' }} }},
                    x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8' }} }}
                }},
                plugins: {{ legend: {{ labels: {{ color: '#f8fafc' }} }} }}
            }}
        }});

        const routeCounts = {{}};
        rawData.forEach(d => routeCounts[d.actual] = (routeCounts[d.actual] || 0) + 1);
        const ctxRoute = document.getElementById('routeChart').getContext('2d');
        new Chart(ctxRoute, {{
            type: 'doughnut',
            data: {{
                labels: Object.keys(routeCounts),
                datasets: [{{
                    data: Object.values(routeCounts),
                    backgroundColor: ['#38bdf8', '#818cf8', '#34d399', '#fbbf24', '#f87171'],
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ position: 'right', labels: {{ color: '#f8fafc', boxWidth: 12 }} }} }}
            }}
        }});
    </script>
</body>
</html>"""
    return html_content


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered reports (.md and .html) to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
    
    html_path = path.with_suffix(".html")
    html_path.write_text(render_html_report(metrics), encoding="utf-8")

