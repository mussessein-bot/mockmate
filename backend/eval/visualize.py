"""
MockMate Eval — Data Export & Visualization

Usage:
  python eval/visualize.py <report_json_path>
  python eval/visualize.py eval/reports/diagnose_xxx.json

Reads a diagnose report JSON bundle and generates:
  1. CSV with per-scenario dimension scores
  2. Radar chart (6-dimension average)
  3. Grouped bar chart (per-scenario scores)
  4. Heatmap (scenario × dimension)
  5. Group comparison chart (A/B/C/D/E)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# --- Chinese font support ---
_ZH_FONTS = [
    "C:/Windows/Fonts/msyh.ttc",   # Microsoft YaHei
    "C:/Windows/Fonts/simhei.ttf",  # SimHei
    "C:/Windows/Fonts/simsun.ttc",  # SimSun
]

def _setup_zh_font():
    for fp in _ZH_FONTS:
        if Path(fp).exists():
            fm.fontManager.addfont(fp)
            prop = fm.FontProperties(fname=fp)
            plt.rcParams["font.family"] = prop.get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return prop.get_name()
    return None

ZH_FONT = _setup_zh_font()

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
    "feedback_actionability": "反馈可操作性",
    "difficulty_progression": "难度梯度",
    "conversation_flow":     "对话自然度",
}

GROUP_LABELS = {
    "followup_logic":       "A-追问逻辑",
    "question_relevance":   "B-题目切题",
    "scoring_consistency":  "C-评分一致",
    "feedback_actionability": "D-反馈质量",
    "difficulty_progression": "E-基准综合",
    "conversation_flow":    "F-对话自然",
}


def load_report(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Report not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def to_dataframe(bundle: dict) -> pd.DataFrame:
    """Convert report JSON to a tidy DataFrame."""
    rows = []
    for r in bundle["results"]:
        sid = r.get("scenario_id", "?")
        dims = r.get("dimensions", {})
        row = {
            "scenario_id": sid,
            "persona": r.get("persona", ""),
            "job_type": r.get("job_type", ""),
            "overall_score": r.get("overall_score", 0.0),
            "turn_count": r.get("turn_count", 0),
        }
        for d in DIMENSIONS:
            row[f"{d}_score"] = dims.get(d, {}).get("score", None)
        rows.append(row)
    return pd.DataFrame(rows)


def export_csv(df: pd.DataFrame, out_dir: Path) -> Path:
    path = out_dir / "eval_scores.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


# ─── Chart 1: Radar Chart (average scores across all scenarios) ────────────

def plot_radar(df: pd.DataFrame, out_dir: Path) -> Path:
    labels = [DIM_LABELS[d] for d in DIMENSIONS]
    means = [df[f"{d}_score"].mean() for d in DIMENSIONS]
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    means_plot = means + [means[0]]
    angles_plot = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.fill(angles_plot, means_plot, color="#4C78A8", alpha=0.25)
    ax.plot(angles_plot, means_plot, color="#4C78A8", linewidth=2, marker="o", markersize=8)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=13)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=10)

    # Annotate scores
    for angle, val, label in zip(angles, means, labels):
        ax.annotate(
            f"{val:.1f}",
            xy=(angle, val),
            xytext=(angle, val + 0.35),
            ha="center", fontsize=12, fontweight="bold", color="#333",
        )

    avg = np.mean(means)
    ax.set_title(f"MockMate 六维评估雷达图（综合均分 {avg:.2f}）", fontsize=16, pad=30)

    path = out_dir / "radar_chart.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ─── Chart 2: Grouped Bar Chart (per-scenario scores) ──────────────────────

def plot_bar_per_scenario(df: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(14, 7))

    scenarios = df["scenario_id"].tolist()
    x = np.arange(len(scenarios))
    width = 0.12
    colors = ["#4C78A8", "#F58518", "#E45756", "#72B7B2", "#54A24B", "#EECA3B"]

    for i, d in enumerate(DIMENSIONS):
        scores = df[f"{d}_score"].tolist()
        ax.bar(x + i * width, scores, width, label=DIM_LABELS[d], color=colors[i])

    ax.set_xticks(x + width * 2.5)
    ax.set_xticklabels(scenarios, fontsize=11)
    ax.set_ylabel("Score (1-5)", fontsize=12)
    ax.set_ylim(0, 5.5)
    ax.set_title("各场景六维评分对比", fontsize=16)
    ax.legend(loc="upper right", fontsize=9, ncol=3)
    ax.axhline(y=3, color="gray", linestyle="--", alpha=0.5, label="基线 3分")
    ax.grid(axis="y", alpha=0.3)

    path = out_dir / "bar_per_scenario.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ─── Chart 3: Heatmap (scenario × dimension) ──────────────────────────────

def plot_heatmap(df: pd.DataFrame, out_dir: Path) -> Path:
    score_matrix = df[[f"{d}_score" for d in DIMENSIONS]].values
    scenarios = df["scenario_id"].tolist()
    dim_labels = [DIM_LABELS[d] for d in DIMENSIONS]

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(score_matrix, cmap="RdYlGn", aspect="auto", vmin=1, vmax=5)

    ax.set_xticks(np.arange(len(dim_labels)))
    ax.set_xticklabels(dim_labels, fontsize=12, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(scenarios)))
    ax.set_yticklabels(scenarios, fontsize=12)

    # Annotate cells
    for i in range(len(scenarios)):
        for j in range(len(DIMENSIONS)):
            val = score_matrix[i, j]
            if not np.isnan(val):
                text_color = "white" if val <= 2 else "black"
                ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                        fontsize=13, fontweight="bold", color=text_color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Score", fontsize=12)
    ax.set_title("场景 × 维度评分热力图", fontsize=16)

    path = out_dir / "heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ─── Chart 4: Group Comparison ─────────────────────────────────────────────

SCENARIO_GROUPS = {
    "A": "追问逻辑",
    "B": "题目切题性",
    "C": "评分一致性",
    "D": "反馈可操作性",
    "E": "基准与综合",
}

def plot_group_comparison(df: pd.DataFrame, out_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))

    groups = []
    group_scores = []
    group_labels = []

    for prefix, label in SCENARIO_GROUPS.items():
        mask = df["scenario_id"].str.startswith(prefix)
        if mask.any():
            sub = df[mask]
            avg = sub["overall_score"].mean()
            groups.append(prefix)
            group_scores.append(avg)
            group_labels.append(f"{prefix}组-{label}\n(n={len(sub)})")

    colors = ["#4C78A8" if s >= 3.5 else "#F58518" if s >= 2.5 else "#E45756" for s in group_scores]
    bars = ax.bar(group_labels, group_scores, color=colors, width=0.6, edgecolor="white", linewidth=1.5)

    for bar, score in zip(bars, group_scores):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{score:.2f}", ha="center", fontsize=14, fontweight="bold")

    ax.set_ylim(0, 5.5)
    ax.set_ylabel("综合均分 (1-5)", fontsize=12)
    ax.set_title("各组场景综合评分对比", fontsize=16)
    ax.axhline(y=3, color="gray", linestyle="--", alpha=0.5)
    ax.grid(axis="y", alpha=0.3)

    path = out_dir / "group_comparison.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python eval/visualize.py <report_json_path>")
        sys.exit(1)

    report_path = sys.argv[1]
    bundle = load_report(report_path)

    out_dir = Path(report_path).parent / "charts"
    out_dir.mkdir(exist_ok=True)

    df = to_dataframe(bundle)

    print(f"Loaded {len(df)} scenarios from {report_path}")
    print(f"Overall average: {df['overall_score'].mean():.2f}")
    print()

    # CSV
    csv_path = export_csv(df, out_dir)
    print(f"[CSV] {csv_path}")

    # Charts
    paths = [
        ("Radar",  plot_radar),
        ("Bar",    plot_bar_per_scenario),
        ("Heatmap", plot_heatmap),
        ("Group",  plot_group_comparison),
    ]
    for name, fn in paths:
        try:
            p = fn(df, out_dir)
            print(f"[{name}] {p}")
        except Exception as e:
            print(f"[{name}] FAILED: {e}")

    print(f"\nDone! All outputs in {out_dir}")


if __name__ == "__main__":
    main()
