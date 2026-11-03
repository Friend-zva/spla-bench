import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

_dump_enabled = False
_dump_dir = None
_dump_tool = None


def configure_dump(enabled: bool, output_dir: Path) -> Optional[Path]:
    global _dump_enabled, _dump_dir, _dump_tool
    _dump_enabled = enabled
    _dump_tool = None
    if enabled:
        _dump_dir = output_dir / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        _dump_dir.mkdir(parents=True, exist_ok=False)
    else:
        _dump_dir = None
    return _dump_dir


def set_dump_tool(tool: str):
    global _dump_tool
    _dump_tool = tool

def print_status(x, status: str, *args):
    print(f"[{str(x)} | {status}]:", *args)


def check_paths_exist(paths: List[Union[str, Path]]) -> bool:
    return sum(map(lambda p: not os.path.exists(p), paths)) == 0


def parent_directory(path: Path) -> Path:
    parents = path.parents
    if len(parents) < 1:
        raise Exception(f"Path `{path}` does not have a parent")
    return parents[0]


def check_call(args, *other_args, **kwargs):
    print_status("subprocess", "check_call", *args)
    return subprocess.check_call(args, *other_args, **kwargs)


def check_output(args, *other_args, **kwargs):
    print_status("subprocess", "check_output", *args)
    output = subprocess.check_output(args, *other_args, **kwargs)
    if _dump_enabled:
        dataset = next(
            (
                Path(str(arg).split("=", 1)[1]).stem
                for arg in args
                if str(arg).startswith("--mtxpath=")
            ),
            next(
                (
                    Path(str(arg)).stem
                    for arg in args[1:]
                    if str(arg).lower().endswith((".mtx", ".gr", ".grb"))
                ),
                "unknown",
            ),
        )
        _dump_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"_{_dump_tool}" if _dump_tool else ""
        dump_path = _dump_dir / f"dump_{dataset}{suffix}.txt"
        with dump_path.open("a", encoding="utf-8") as dump_file:
            dump_file.write(f"\n===== {' '.join(map(str, args))} =====\n")
            dump_file.write(output.decode("utf-8", errors="replace"))
    return output
