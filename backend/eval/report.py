from __future__ import annotations

import json
import subprocess
import statistics
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DIMENSIONS = [
    "followup_logic",
    "question_relevance",
    "scoring_consistency",
    "feedback_actionability",
    "difficulty_progression",
    "conversation_flow",
]

DIM_LABELS = {
    "followup_logic":        "追问逻辑",
    "question_relevance":    "题目切题性",
    "scoring_consistency":   "评分一致性",
    "feedback_actionability":"反馈可操作性",
    "difficulty_progression":"难度梯度",
    "conversation_flow":     "对话自然度",
}


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _score_bar(score: float, max_score: float = 5.0) -> str:
    filled = round(score / max_score * 10)
    return "█" * filled + "░" * (10 - filled) + f"  {score:.1f}/{max_score:.0f}"


def _severity_icon(sev: str) -> str:
    return {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}.get(sev, "⚪")


def build_report(
    results: list[dict],          # list of judge_result dicts
    mode: str,
    previous_results: list[dict] | None = None,
) -> tuple[str, dict]:
    """
    Build markdown report + raw JSON bundle.
    Returns (markdown_str, json_bundle).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    git = _git_hash()
    n = len(results)

    # ── Aggregate dimension scores ───────────────────────────────────────────
    dim_scores: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for r in results:
        for d in DIMENSIONS:
            s = r.get("dimensions", {}).get(d, {}).get("score")
            if s is not None:
                dim_scores[d].append(float(s))

    dim_avg = {d: (statistics.mean(v) if v else 0.0) for d, v in dim_scores.items()}
    overall_avg = statistics.mean(r.get("overall_score", 0.0) for r in results) if results else 0.0

    # Previous run deltas
    prev_avg: dict[str, float] = {}
    if previous_results:
        for d in DIMENSIONS:
            vals = [float(r.get("dimensions", {}).get(d, {}).get("score", 0)) for r in previous_results]
            if vals:
                prev_avg[d] = statistics.mean(vals)

    # ── Collect all issues by severity ──────────────────────────────────────
    all_issues: list[dict] = []
    for r in results:
        for item in r.get("severity_catalog", []):
            all_issues.append({**item, "_scenario": r.get("scenario_id", "?")})

    high_issues = [i for i in all_issues if i["severity"] == "HIGH"]
    med_issues  = [i for i in all_issues if i["severity"] == "MED"]
    low_issues  = [i for i in all_issues if i["severity"] == "LOW"]

    # ── Scoring consistency (C1/C2/C3 std dev) ──────────────────────────────
    c_scores = [
        r.get("overall_score", 0.0)
        for r in results if r.get("scenario_id", "").startswith("C")
    ]
    c_std = statistics.stdev(c_scores) if len(c_scores) >= 2 else None

    # ── Markdown ─────────────────────────────────────────────────────────────
    md = []
    md.append(f"# MockMate Eval Report")
    md.append(f"**运行时间：** {now}  |  **Git：** `{git}`  |  **模式：** {mode}  |  **场景数：** {n}")
    md.append("")

    md.append("## Dashboard")
    md.append("")
    md.append("| 维度 | 本次均分 | 趋势 | 状态 |")
    md.append("|---|---|---|---|")
    for d in DIMENSIONS:
        avg = dim_avg[d]
        bar = _score_bar(avg)
        delta = ""
        if d in prev_avg:
            diff = avg - prev_avg[d]
            delta = f"{'▲' if diff > 0 else '▼'} {abs(diff):.1f}" if abs(diff) >= 0.1 else "→ 持平"
        status = "✅" if avg >= 4 else ("⚠️" if avg >= 3 else "❌")
        md.append(f"| {DIM_LABELS[d]} | {bar} | {delta} | {status} |")

    md.append("")
    md.append(f"**综合均分：** {overall_avg:.2f} / 5.0")
    if c_std is not None:
        std_status = "✅" if c_std < 0.5 else ("⚠️" if c_std < 1.0 else "❌")
        md.append(f"**评分一致性 std（C组）：** {c_std:.2f} {std_status}  _(< 0.5 良好，> 1.0 需关注)_")
    md.append("")

    # ── Issue catalog ─────────────────────────────────────────────────────────
    md.append("## Issue Catalog")
    md.append("")

    def _render_issues(issues: list[dict], label: str) -> None:
        if not issues:
            return
        md.append(f"### {label}（{len(issues)} 个）")
        md.append("")
        for i, item in enumerate(issues, 1):
            icon = _severity_icon(item["severity"])
            md.append(f"**{i}. [{item['_scenario']}] {item['description']}**  {icon}")
            md.append(f"> 维度：`{item['dimension']}`")
            if item.get("quote"):
                md.append(f"> 原文：_{item['quote']}_")
            if item.get("suggested_fix"):
                md.append(f"> 建议：{item['suggested_fix']}")
            md.append("")

    _render_issues(high_issues, "HIGH — 需优先处理")
    _render_issues(med_issues,  "MED — 次要问题")
    _render_issues(low_issues,  "LOW — 改进空间")

    if not all_issues:
        md.append("_本次未发现问题。_")
        md.append("")

    # ── Per-session detail ───────────────────────────────────────────────────
    md.append("## 场景详情")
    md.append("")
    for r in results:
        sid = r.get("scenario_id", "?")
        overall = r.get("overall_score", 0.0)
        turns = r.get("turn_count", "?")
        md.append(f"### {sid} | 综合分 {overall:.1f} | 共 {turns} 轮")
        dims = r.get("dimensions", {})
        row = " | ".join(
            f"{DIM_LABELS.get(d, d)}: {dims.get(d, {}).get('score', '-')}"
            for d in DIMENSIONS
        )
        md.append(f"_{row}_")
        highs = [i for i in r.get("severity_catalog", []) if i["severity"] == "HIGH"]
        if highs:
            for h in highs:
                md.append(f"- 🔴 {h['description']}")
        md.append("")

    md_text = "\n".join(md)

    # ── JSON bundle ──────────────────────────────────────────────────────────
    bundle = {
        "meta": {"timestamp": now, "git": git, "mode": mode, "n_sessions": n},
        "summary": {"dim_avg": dim_avg, "overall_avg": overall_avg, "c_std": c_std},
        "results": results,
    }

    return md_text, bundle


def save_report(md_text: str, bundle: dict, mode: str) -> Path:
    git = bundle["meta"]["git"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{mode}_{git}_{ts}"
    md_path = REPORTS_DIR / f"{stem}.md"
    json_path = REPORTS_DIR / f"{stem}.json"
    md_path.write_text(md_text, encoding="utf-8")
    json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path


def load_latest_report(mode: str = "diagnose") -> dict | None:
    """Load the most recent JSON report of given mode for delta comparison."""
    candidates = sorted(REPORTS_DIR.glob(f"{mode}_*.json"), reverse=True)
    if not candidates:
        return None
    try:
        return json.loads(candidates[0].read_text(encoding="utf-8"))
    except Exception:
        return None
