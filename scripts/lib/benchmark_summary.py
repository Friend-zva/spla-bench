import csv
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from drivers.driver import ExecutionResult
from lib.algorithm import AlgorithmName
from lib.dataset import Dataset
from lib.tool import ToolName
from lib.util import print_status

"""

datatset | tool_1 | tool_2 | ... | tool_n
---------|--------|--------|-----|-------
name_1   | ...    | ...    | ... | ...
name_2   | ...    | ...    | ... | ...
...

"""


class OutputFormat(Enum):
    raw = "txt"
    csv = "csv"

    def extension(self):
        return f".{self.value}"


def print_all_results(result: ExecutionResult):
    return result.brief_str()


def print_median(result: ExecutionResult):
    return str(result.median())


class ResultsPrinter(Enum):
    all = "all"
    median = "median"

    def __str__(self) -> str:
        return self.value

    def print(self, result: ExecutionResult) -> str:
        match_printer = {
            ResultsPrinter.all: print_all_results,
            ResultsPrinter.median: print_median,
        }
        return match_printer[self](result)


class BenchmarkSummary:
    def __init__(self):
        self.measurements: Dict[
            AlgorithmName, Dict[str, Dict[ToolName, ExecutionResult]]
        ] = {}

    def add_measurement(
        self,
        tool: ToolName,
        dataset: Dataset,
        algo: AlgorithmName,
        result: ExecutionResult,
    ):
        (
            self.measurements.setdefault(algo, {})
            .setdefault(dataset.name, {})
            .setdefault(tool, result)
        )

    def algorithms(self) -> List[AlgorithmName]:
        return list(self.measurements.keys())

    def results_per_algorithm(
        self,
    ) -> List[Tuple[AlgorithmName, Dict[str, Dict[ToolName, ExecutionResult]]]]:
        return list(self.measurements.items())

    def results_per_algorithm_dataset(
        self,
    ) -> List[Tuple[AlgorithmName, str, Dict[ToolName, ExecutionResult]]]:
        items = []
        for algo, results in self.results_per_algorithm():
            items.extend(map(lambda item: (algo, item[0], item[1]), results.items()))
        return items

    def measurements_list(
        self,
    ) -> List[Tuple[AlgorithmName, str, ToolName, ExecutionResult]]:
        items = []
        for algo, tool_by_dataset in self.measurements.items():
            for dataset_name, result_by_tool in tool_by_dataset.items():
                for tool, result in result_by_tool.items():
                    items.append((algo, dataset_name, tool, result))
        return items

    def dump(self, format: OutputFormat, output_dir: Path, results_printer: Callable):
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        output.mkdir(exist_ok=False)

        if format == OutputFormat.raw:
            def process_result(t):
                algo, dataset, tool, result = t
                return (
                    f"algo: {algo}, dataset: {dataset}, tool: {tool}, "
                    f"result: {results_printer.print(result)}"
                )

            processed_measurements = list(map(process_result, self.measurements_list()))
            output_file_name = (output / "raw").with_suffix(format.extension())
            with output_file_name.open("w") as out_file:
                print(*processed_measurements, sep="\n", file=out_file)

        elif format == OutputFormat.csv:
            # Keep CSV values numeric so they can be loaded directly by pandas,
            # spreadsheet software, and plotting scripts.
            metric_names = ("warm_up_ms", "avg_ms", "median_ms", "stdev_ms")
            tools = [str(tool) for tool in self.tools()]
            fieldnames = ["dataset"] + [
                f"{tool}_{metric}" for tool in tools for metric in metric_names
            ]

            for algo, algo_results in self.results_per_algorithm():
                if not algo_results:
                    continue
                algo_output = (output / str(algo)).with_suffix(format.extension())
                with algo_output.open("w") as algo_file:
                    csv_writer = csv.DictWriter(algo_file, fieldnames)
                    csv_writer.writeheader()
                    for dataset_name, dataset_results in algo_results.items():
                        csv_row = {"dataset": dataset_name}
                        for tool, result in dataset_results.items():
                            prefix = str(tool)
                            csv_row[f"{prefix}_warm_up_ms"] = f"{result.warm_up:.6f}"
                            csv_row[f"{prefix}_avg_ms"] = f"{result.avg():.6f}"
                            csv_row[f"{prefix}_median_ms"] = f"{result.median():.6f}"
                            csv_row[f"{prefix}_stdev_ms"] = f"{result.stdev():.6f}"
                        csv_writer.writerow(csv_row)

        else:
            raise Exception(f"Format {format.name} is not supported")

        legacy_recent = output_dir / "recent"
        if legacy_recent.exists() or legacy_recent.is_symlink():
            legacy_recent.unlink()
        for tool in self.tools():
            recent_link = output_dir / f"recent_{tool}"
            if recent_link.exists() or recent_link.is_symlink():
                recent_link.unlink()
            os.symlink(
                output.name,
                recent_link,
                target_is_directory=True,
            )
            print_status(
                "summary",
                "dump",
                f"symlink: {recent_link}, original: {output}",
            )

    def tools(self) -> List[ToolName]:
        return sorted(
            {
                tool
                for _, _, tool, _ in self.measurements_list()
            },
            key=str,
        )
