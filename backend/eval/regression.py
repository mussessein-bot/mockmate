from __future__ import annotations

import json
import asyncio
from datetime import datetime
from pathlib import Path

import eval  # noqa: F401
from eval.judge import extract_high_issues

REGRESSION_DIR = Path(__file__).parent / "reports" / "regression"
REGRESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_regression_cases(judge_result: dict, scenario: dict, git_hash: str) -> list[Path]:
    """
    For every HIGH issue in judge_result, persist a regression test case file.
    Returns list of written paths.
    """
    high_issues = extract_high_issues(judge_result)
    written: list[Path] = []
    for item in high_issues:
        dim = item.get("dimension", "unknown")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        issue_id = f"{scenario['id']}_{dim}_{ts}"

        case = {
            "issue_id": issue_id,
            "created_at": datetime.now().isoformat(),
            "git_commit": git_hash,
            "scenario_id": scenario["id"],
            "dimension": dim,
            "description": item.get("description", ""),
            "quote": item.get("quote", ""),
            "suggested_fix": item.get("suggested_fix", ""),
            "expected_behavior": item.get("expected", ""),
            "actual_behavior_at_discovery": item.get("actual", ""),
            "status": "open",
        }
        path = REGRESSION_DIR / f"{issue_id}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def load_open_cases() -> list[dict]:
    cases = []
    for p in sorted(REGRESSION_DIR.glob("*.json")):
        try:
            case = json.loads(p.read_text(encoding="utf-8"))
            if case.get("status") == "open":
                cases.append(case)
        except Exception:
            continue
    return cases


def mark_case_resolved(issue_id: str) -> bool:
    for p in REGRESSION_DIR.glob(f"{issue_id}*.json"):
        try:
            case = json.loads(p.read_text(encoding="utf-8"))
            case["status"] = "resolved"
            case["resolved_at"] = datetime.now().isoformat()
            p.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            pass
    return False


async def run_regression(cases: list[dict]) -> list[dict]:
    """
    Re-run each open regression case through a minimal session and
    check whether the flagged issue (HIGH) still appears.

    Strategy: re-run the full scenario the case came from, then check
    if judge still flags HIGH for the same dimension.
    Returns list of result dicts: {issue_id, dimension, scenario_id, status, detail}
    """
    from eval.runner import run_session
    from eval.judge import evaluate_transcript
    from eval.scenarios import get_scenario

    results = []
    seen_scenarios: dict[str, tuple] = {}  # scenario_id → (transcript, judge_result)

    for case in cases:
        sid = case.get("scenario_id")
        dim = case.get("dimension")
        issue_id = case.get("issue_id")

        try:
            scenario = get_scenario(sid)
        except KeyError:
            results.append({
                "issue_id": issue_id,
                "dimension": dim,
                "scenario_id": sid,
                "status": "error",
                "detail": f"Scenario {sid!r} not found",
            })
            continue

        # Re-use transcript if we already ran this scenario this session
        if sid not in seen_scenarios:
            transcript = await run_session(scenario)
            judge_result = evaluate_transcript(transcript, scenario)
            seen_scenarios[sid] = (transcript, judge_result)
        else:
            _, judge_result = seen_scenarios[sid]

        # Check if the dimension still scores poorly (HIGH = score <= 2)
        dim_score = judge_result.get("dimensions", {}).get(dim, {}).get("score")
        still_failing = dim_score is not None and dim_score <= 2

        status = "FAIL" if still_failing else "PASS"
        results.append({
            "issue_id": issue_id,
            "dimension": dim,
            "scenario_id": sid,
            "status": status,
            "dim_score_now": dim_score,
            "detail": case.get("description", ""),
        })

    return results


def format_regression_report(results: list[dict]) -> str:
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    errors = [r for r in results if r["status"] == "error"]

    lines = [
        "## 回归测试结果",
        f"总计：{len(results)} 个用例  |  ✅ 通过：{len(passed)}  |  ❌ 仍失败：{len(failed)}  |  ⚠️ 错误：{len(errors)}",
        "",
    ]
    if failed:
        lines.append("### ❌ 仍失败（未修复）")
        for r in failed:
            lines.append(f"- [{r['scenario_id']}] `{r['dimension']}` 当前分={r.get('dim_score_now', '?')} — {r['detail']}")
        lines.append("")
    if passed:
        lines.append("### ✅ 已通过（问题已修复）")
        for r in passed:
            lines.append(f"- [{r['scenario_id']}] `{r['dimension']}` 当前分={r.get('dim_score_now', '?')} — {r['detail']}")
        lines.append("")
    return "\n".join(lines)
