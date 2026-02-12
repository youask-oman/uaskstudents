from __future__ import annotations

import importlib
import os
from pathlib import Path

import matplotlib


def test_numeric_stack_imports():
    modules = ["numpy", "sympy", "matplotlib", "pypdfium2"]
    for module_name in modules:
        importlib.import_module(module_name)


def test_matplotlib_headless_png_render(tmp_path: Path):
    os.environ["MPLBACKEND"] = "Agg"
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(2, 2), dpi=72)
    ax.plot([0, 1], [0, 1])
    target = tmp_path / "smoke_plot.png"
    fig.savefig(target, format="png")
    plt.close(fig)

    assert target.exists()
    assert target.stat().st_size > 0
