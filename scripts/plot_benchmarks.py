#!/usr/bin/env python3

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, Iterable, List

ALGORITHMS = ("pr", "tc")
DEFAULT_TOOLS = ("spla", "lagraph")
TOOL_COLORS = ("tab:blue", "tab:orange")
ERROR_BARS = ("none", "stdev")


def _read_results(
    run_directory: Path,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    results: Dict[str, Dict[str, Dict[str, float]]] = {}
    for csv_path in run_directory.glob("*.csv"):
        tool, separator, algorithm = csv_path.stem.partition("_")
        if not separator:
            algorithm = csv_path.stem
            tool = "spla"
        if algorithm not in ALGORITHMS:
            continue
        with csv_path.open(newline="") as csv_file:
            for row in csv.DictReader(csv_file):
                dataset = row["dataset"]
                prefix = f"{tool}_" if f"{tool}_median_ms" in row else ""
                median = row.get(f"{prefix}median_ms")
                warm_up = row.get(f"{prefix}warm_up_ms")
                if median and warm_up:
                    results.setdefault(algorithm, {})[f"{dataset}:{tool}"] = {
                        "median": float(median) / 1000,
                        "warm_up": float(warm_up) / 1000,
                        "stdev": float(row.get(f"{prefix}stdev_ms") or 0) / 1000,
                    }
    return results


def _datasets(results: Dict[str, Dict[str, Dict[str, float]]]) -> List[str]:
    datasets = set()
    for values in results.values():
        datasets.update(key.split(":", 1)[0] for key in values)
    return sorted(datasets)


def _dataset_labels(
    datasets: Iterable[str],
    values: Dict[str, Dict[str, float]],
) -> List[str]:
    labels = []
    for dataset in datasets:
        spla = values.get(f"{dataset}:spla", {}).get("median", math.nan)
        lagraph = values.get(f"{dataset}:lagraph", {}).get("median", math.nan)
        if math.isfinite(spla) and math.isfinite(lagraph) and spla > 0:
            labels.append(f"{dataset}\n({lagraph / spla:.1f}x)")
        else:
            labels.append(dataset)
    return labels


def _draw_algorithm(
    algorithm: str,
    datasets: Iterable[str],
    values: Dict[str, Dict[str, float]],
    ax,
    show_metric_label: bool = True,
    show_graph_label: bool = True,
    show_legend: bool = True,
    error_bars: str = "none",
) -> None:
    datasets = list(datasets)
    x = list(range(len(datasets)))
    width = 0.36

    for offset, tool, color in zip((-width / 2, width / 2), DEFAULT_TOOLS, TOOL_COLORS):
        tool_values = [
            values.get(f"{dataset}:{tool}", {}).get("median", math.nan)
            for dataset in datasets
        ]
        tool_errors = [
            values.get(f"{dataset}:{tool}", {}).get("stdev", math.nan)
            for dataset in datasets
        ]
        warm_up_values = [
            values.get(f"{dataset}:{tool}", {}).get("warm_up", math.nan)
            for dataset in datasets
        ]
        ax.bar(
            [position + offset for position in x],
            tool_values,
            width,
            label=tool,
            color=color,
            yerr=tool_errors if error_bars == "stdev" else None,
            capsize=4 if error_bars == "stdev" else 0,
        )
        ax.scatter(
            [position + offset for position in x],
            warm_up_values,
            marker="o",
            s=12,
            color="black",
            linewidths=1.5,
            zorder=3,
        )
        for position, median, warm_up, stdev in zip(
            x, tool_values, warm_up_values, tool_errors
        ):
            if not math.isnan(median):
                label_y = median
                if not math.isnan(warm_up):
                    line_up = warm_up - stdev < 10
                    label_y = max(label_y, stdev if line_up else warm_up)
                if error_bars == "stdev" and not math.isnan(stdev):
                    label_y = max(label_y, median + stdev)
                ax.annotate(
                    f"{median:.4f}",
                    (position + offset, label_y),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    rotation=0,
                    fontsize=8,
                )

    ax.set_title(algorithm.upper())
    if show_metric_label:
        ax.set_ylabel("Time, s")
    ax.set_yscale("log")
    ax.margins(y=0.2)
    from matplotlib.ticker import LogFormatterMathtext

    ax.yaxis.set_major_formatter(LogFormatterMathtext())
    ax.set_xticks(x)
    ax.set_xticklabels(_dataset_labels(datasets, values), rotation=20, ha="center")
    if show_graph_label:
        ax.set_xlabel("Graph, name")
    ax.grid(axis="y", alpha=0.25)
    if show_legend:
        ax.legend()


def _plot_algorithm(
    algorithm: str,
    datasets: Iterable[str],
    values: Dict[str, Dict[str, float]],
    output_path: Path,
    plt,
    error_bars: str,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    _draw_algorithm(algorithm, datasets, values, ax, error_bars=error_bars)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _plot_all_algorithms(
    datasets: Iterable[str],
    results: Dict[str, Dict[str, Dict[str, float]]],
    output_path: Path,
    plt,
    error_bars: str,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for index, (algorithm, ax) in enumerate(zip(ALGORITHMS, axes.flat)):
        row, column = divmod(index, 2)
        _draw_algorithm(
            algorithm,
            datasets,
            results.get(algorithm, {}),
            ax,
            show_metric_label=column == 0,
            show_graph_label=row == 1,
            show_legend=index == 1,
            error_bars=error_bars,
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent.parent / "benchmarks" / "main",
        help="Directory containing benchmark CSV files, for example benchmarks/main",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "plots",
        help="Directory for three PNG files",
    )
    parser.add_argument(
        "--error-bars",
        choices=ERROR_BARS,
        default="stdev",
        help="Show variability bars as plus/minus one standard deviation",
    )
    args = parser.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise SystemExit(
            "Plotting requires matplotlib. Install it with: "
            "python3 -m pip install matplotlib"
        ) from error

    if not args.input.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {args.input}")

    results = _read_results(args.input)
    datasets = _datasets(results)
    if not datasets:
        raise ValueError(f"No algorithm CSV files found in {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)
    for algorithm in ALGORITHMS:
        _plot_algorithm(
            algorithm,
            datasets,
            results.get(algorithm, {}),
            args.output / f"{algorithm}.png",
            plt,
            args.error_bars,
        )
    _plot_all_algorithms(
        datasets,
        results,
        args.output / "all_algorithms.png",
        plt,
        args.error_bars,
    )
    print(f"Read: {args.input}")
    output_names = [f"{algorithm}.png" for algorithm in ALGORITHMS]
    output_names.append("all_algorithms.png")
    print(f"Wrote: {args.output} ({', '.join(output_names)})")


if __name__ == "__main__":
    main()
