#!/usr/bin/env python3

"""Plot all GPU timings from dump_<dataset>_spla.txt files on one number line."""

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, NamedTuple

TIME_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


class Measurement(NamedTuple):
    value_ms: float
    warm_up: bool
    source: str


def _dataset_name(path: Path) -> str:
    stem = path.stem
    prefix = "dump_"
    suffix = "_spla"
    if stem.startswith(prefix) and stem.endswith(suffix):
        return stem[len(prefix) : -len(suffix)]
    return stem


def _times(line: str) -> List[float]:
    return [float(value) for value in TIME_RE.findall(line.split(":", 1)[1])]


def parse_dump(path: Path) -> List[Measurement]:
    """Read GPU runs and mark only the first timing as warm-up."""
    measurements: List[Measurement] = []
    first_timing = True

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("warm-up(ms):"):
            for value in _times(line):
                measurements.append(Measurement(value, first_timing, path.name))
                first_timing = False
        elif line.startswith("gpu(ms):"):
            for value in _times(line):
                measurements.append(Measurement(value, first_timing, path.name))
                first_timing = False

    return measurements


def _plot(dataset_measurements: Dict[str, List[Measurement]], output: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise SystemExit(
            "Plotting requires matplotlib. Install it with: python3 -m pip install matplotlib"
        ) from error

    datasets = sorted(dataset_measurements)
    fig, axes = plt.subplots(
        len(datasets),
        1,
        figsize=(12, max(2.4, 2.4 * len(datasets))),
        squeeze=False,
    )

    for row, dataset in enumerate(datasets):
        ax = axes[row][0]
        # Convert the dump's milliseconds to seconds for the number line.
        measurements = [
            item._replace(value_ms=item.value_ms / 1000.0)
            for item in dataset_measurements[dataset]
        ]
        regular = [item for item in measurements if not item.warm_up]
        warm_up = [item for item in measurements if item.warm_up]

        # Spread nearby points vertically so overlapping measurements remain visible.
        point_y = []
        placed_x = []
        for item in regular:
            nearby = sum(abs(item.value_ms - previous) < 0.08 for previous in placed_x)
            point_y.append(0.05 + (nearby % 5 - 2) * 0.012)
            placed_x.append(item.value_ms)
        ax.scatter(
            [item.value_ms for item in regular],
            point_y,
            color="tab:blue",
            s=28,
        )
        for item in warm_up[:1]:
            ax.scatter(
                item.value_ms,
                0.09,
                color="tab:red",
                marker="o",
                s=42,
            )

        ax.set_ylim(0, 0.12)
        ax.set_yticks([])
        ax.set_ylabel(dataset, rotation=0, ha="right", va="center", labelpad=12)
        ax.grid(axis="x", alpha=0.25)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        if measurements:
            from matplotlib.ticker import MultipleLocator

            ax.xaxis.set_major_locator(MultipleLocator(1.0))

    axes[-1][0].set_xlabel("Time, s")
    fig.suptitle("Spla / tc")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="dump files; default: dump_*_spla.txt in the current directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("spla_gpu_timings.png"),
        help="output PNG path",
    )
    args = parser.parse_args()

    inputs = args.inputs or sorted(Path(".").glob("dump_*_spla.txt"))
    inputs = [path for path in inputs if path.is_file()]
    if not inputs:
        parser.error("no dump files found")

    dataset_measurements = defaultdict(list)
    for path in inputs:
        dataset_measurements[_dataset_name(path)].extend(parse_dump(path))
    dataset_measurements = {
        dataset: measurements
        for dataset, measurements in dataset_measurements.items()
        if measurements
    }
    if not dataset_measurements:
        parser.error("no `gpu(ms):` or `warm-up(ms):` timings found")

    _plot(dataset_measurements, args.output)
    total = sum(len(values) for values in dataset_measurements.values())
    print(f"Read {total} GPU timings from {len(dataset_measurements)} dataset(s)")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
