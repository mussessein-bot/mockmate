#!/usr/bin/env python3
"""
MockMate Eval CLI

Usage:
  python eval/run_eval.py --mode diagnose
  python eval/run_eval.py --mode probe --dimension followup_logic --profile brief_answerer --repeat 5
  python eval/run_eval.py --mode regress
  python eval/run_eval.py --mode diagnose --scenario A1,A2,A3   # run subset
"""
from __future__ import annotations

import sys
import argparse
import asyncio
import subprocess
from pathlib import Path

# Bootstrap sys.path so app.* imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eval  # noqa: F401

from eval.scenarios import SCENARIOS, get_scenario, get_scenarios_by_group
from eval.runner import run_session
from eval.judge import evaluate_transcript
from eval.report import build_report, save_report, load_latest_report
from eval.regression import (
    save_regression_cases, load_open_cases,
    run_regression, format_regression_report,
)


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _print_progress(current: int, total: int, label: str) -> None:
    bar_len = 30
    filled = int(bar_len * current / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r[{bar}] {current}/{total}  {label:<40}", end="", flush=True)


async def _run_scenarios(scenarios: list[dict], git: str, verbose: bool = False) -> list[dict]:
    results = []
    total = len(scenarios)
    for i, scenario in enumerate(scenarios, 1):
        label = f"{scenario['id']} | {scenario['persona']} | {scenario['job_type']}"
        _print_progress(i - 1, total, label)
        try:
            transcript = await run_session(scenario)
            judge_result = await evaluate_transcript(transcript, scenario)
            results.append(judge_result)

            # Auto-save HIGH issues as regression cases
            saved = save_regression_cases(judge_result, scenario, git)
            if saved and verbose:
                print(f"\n  ↳ 保存了 {len(saved)} 个回归用例", flush=True)

        except Exception as e:
            print(f"\n  ⚠️  {scenario['id']} 运行失败: {e}", flush=True)

    _print_progress(total, total, "完成")
    print(flush=True)
    return results


async def cmd_diagnose(args: argparse.Namespace) -> None:
    # Filter scenarios if --scenario specified
    if args.scenario:
        ids = [s.strip() for s in args.scenario.split(",")]
        scenarios = [get_scenario(sid) for sid in ids]
    else:
        scenarios = SCENARIOS

    print(f"\n▶ Diagnose 模式 | {len(scenarios)} 个场景\n")
    git = _git_hash()
    results = await _run_scenarios(scenarios, git, verbose=args.verbose)

    # Load previous run for delta
    prev_bundle = load_latest_report("diagnose")
    prev_results = prev_bundle.get("results") if prev_bundle else None

    md_text, bundle = build_report(results, mode="diagnose", previous_results=prev_results)
    path = save_report(md_text, bundle, mode="diagnose")

    print("\n" + md_text)
    print(f"\n✅ 报告已保存：{path}")


async def cmd_probe(args: argparse.Namespace) -> None:
    dim = args.dimension
    profile = args.profile
    repeat = args.repeat or 5

    # Find matching scenarios
    candidates = get_scenarios_by_group(dim) if dim else SCENARIOS
    if profile:
        candidates = [s for s in candidates if s["persona"] == profile]
    if not candidates:
        print(f"找不到匹配的场景 (dimension={dim}, profile={profile})")
        sys.exit(1)

    # Repeat the first matching scenario N times
    base = candidates[0]
    scenarios = [base] * repeat

    print(f"\n▶ Probe 模式 | 维度={dim} | 人设={base['persona']} | 重复{repeat}次\n")
    git = _git_hash()
    results = await _run_scenarios(scenarios, git)

    md_text, bundle = build_report(results, mode="probe")
    path = save_report(md_text, bundle, mode="probe")
    print("\n" + md_text)
    print(f"\n✅ 报告已保存：{path}")


async def cmd_regress(args: argparse.Namespace) -> None:
    cases = load_open_cases()
    if not cases:
        print("\n✅ 没有 open 状态的回归用例。")
        return

    print(f"\n▶ Regress 模式 | {len(cases)} 个 open 用例\n")
    results = await run_regression(cases)
    report_text = format_regression_report(results)
    print(report_text)

    # Also run a quick diagnose for new issues
    if args.quick:
        print("\n▶ 附加快速初诊（Group A + E）...\n")
        quick_scenarios = [s for s in SCENARIOS if s["id"].startswith(("A", "E"))]
        git = _git_hash()
        diag_results = await _run_scenarios(quick_scenarios, git)
        md_text, bundle = build_report(diag_results, mode="regress")
        path = save_report(md_text, bundle, mode="regress")
        print(md_text)
        print(f"\n✅ 报告已保存：{path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MockMate Eval CLI")
    sub = parser.add_subparsers(dest="mode")

    p_diag = sub.add_parser("diagnose", help="全量覆盖矩阵初诊")
    p_diag.add_argument("--scenario", help="逗号分隔的场景ID，如 A1,A2,B1")
    p_diag.add_argument("--verbose", action="store_true")

    p_probe = sub.add_parser("probe", help="针对单一维度深查")
    p_probe.add_argument("--dimension", help="维度key，如 followup_logic")
    p_probe.add_argument("--profile", help="候选人人设，如 brief_answerer")
    p_probe.add_argument("--repeat", type=int, default=5)

    p_reg = sub.add_parser("regress", help="回归测试已保存的 HIGH 用例")
    p_reg.add_argument("--quick", action="store_true", help="附加运行 A+E 组快速初诊")

    # Also support --mode as a flat argument for convenience
    parser.add_argument("--mode", choices=["diagnose", "probe", "regress"])
    parser.add_argument("--scenario")
    parser.add_argument("--dimension")
    parser.add_argument("--profile")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()
    mode = args.mode or (args.mode if hasattr(args, "mode") else None)
    if not mode:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "diagnose": cmd_diagnose,
        "probe": cmd_probe,
        "regress": cmd_regress,
    }
    asyncio.run(dispatch[mode](args))


if __name__ == "__main__":
    main()
