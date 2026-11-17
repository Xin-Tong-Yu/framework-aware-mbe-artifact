#!/usr/bin/env python3
"""Plot the five paired ET2/ET1 observations that underlie Table VII."""

import argparse
import json
import math
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


LIMITS = (-16, 14)
OFFSETS = (-0.24, -0.12, 0, 0.12, 0.24)
FRAMEWORKS = (("single", "Single", "#19578a"), ("double", "Double", "#00685a"))


def paired_points(graphs, framework):
    for graph in graphs:
        contrast = graph["frameworks"][framework]["comparisons"]["ET2/ET1"]
        ratios = contrast["block_ratios"]
        if len(ratios) != len(OFFSETS) or any(not math.isfinite(value) or value <= 0 for value in ratios):
            raise ValueError(f"{graph['graph']}: expected five positive, finite paired observations")
        if not math.isclose(median(ratios), contrast["median_ratio"], rel_tol=1e-12):
            raise ValueError(f"{graph['graph']}: paired observations do not reproduce the median")
        yield [100 * (value - 1) for value in ratios]


def plot(summary, output):
    graphs = summary["table_vii"]["graphs"]
    labels = [graph["label"] for graph in graphs]
    if len(labels) != 13 or len(set(labels)) != 13:
        raise ValueError("use the complete thirteen-graph Table VII summary")

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
        "font.size": 8,
        "pdf.fonttype": 42,
        "axes.linewidth": 0.55,
    })
    figure, axes = plt.subplots(1, 2, figsize=(3.48, 3.10), sharey=True)
    figure.subplots_adjust(left=0.123, right=0.992, top=0.914, bottom=0.17, wspace=0.085)
    for ax, (framework, title, color) in zip(axes, FRAMEWORKS):
        ax.set_title(title, loc="left", fontweight="bold", fontsize=9, pad=5)
        ax.set_xlim(*LIMITS)
        ax.set_ylim(len(labels) - 0.52, -0.55)
        ax.set_xticks((-15, -10, -5, 0, 5, 10))
        ax.set_yticks(range(len(labels)), labels)
        ax.tick_params(axis="y", length=0, pad=4)
        ax.tick_params(axis="x", length=2.4, pad=2)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#747474")
        ax.grid(axis="x", linewidth=0.42, color="#e4e4e4", zorder=0.3)
        ax.set_axisbelow(True)
        ax.axvline(0, color="#525252", linewidth=0.65, zorder=1)

        for row, (graph, points) in enumerate(zip(graphs, paired_points(graphs, framework))):
            if all(graph["frameworks"][name]["median_st_s"] < 1.0 for name, _, _ in FRAMEWORKS):
                ax.axhspan(row - 0.5, row + 0.5, color="#f1f1f1", linewidth=0, zorder=0)
            positions = [row + offset for offset in OFFSETS]
            interior = [(value, y) for value, y in zip(points, positions) if LIMITS[0] <= value <= LIMITS[1]]
            if interior:
                x, y = zip(*interior)
                ax.scatter(x, y, s=9, facecolors="white", edgecolors=color, linewidths=0.62, zorder=2.2)
            for value, y in zip(points, positions):
                if not LIMITS[0] <= value <= LIMITS[1]:
                    right = value > LIMITS[1]
                    edge = LIMITS[1] - 0.85 if right else LIMITS[0] + 0.85
                    ax.scatter(edge, y, marker=">" if right else "<", s=11, color=color, zorder=2.2)
                    ax.annotate(f"{value:+.1f}", (edge, y), xytext=(-4 if right else 4, 0),
                                textcoords="offset points", ha="right" if right else "left",
                                va="center", fontsize=6.6, color=color)
            ax.scatter(median(points), row, marker="D", s=17, facecolors=color, edgecolors="white",
                       linewidths=0.35, zorder=3)
    figure.text(0.56, 0.048, "Paired ET2/ET1 search-speed gain (%)", ha="center", fontsize=8)
    figure.savefig(output, format="pdf", metadata={"Creator": "Matplotlib", "CreationDate": None, "ModDate": None})
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    plot(summary, args.output)


if __name__ == "__main__":
    main()
