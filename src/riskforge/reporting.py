"""Model card rendering for a ``riskforge.workflow.Run``.

``model_card(run, fmt="md")`` returns a markdown (or HTML) summary of the
experiment: config name, dataset shape + features, and a per-model block with
metrics + a calibration-table preview. The HTML output wraps the canonical
markdown in a minimal HTML5 document (``<pre>``); a real markdown parser is a
``plot`` extra candidate when reports need styling.

ponytail: deliberately tiny -- md is the canonical form, html is a thin wrap.
"""

from __future__ import annotations

import html
import textwrap
from typing import Literal

import pandas as pd

from riskforge.workflow import Run

__all__ = ["model_card"]


def _fmt(x, dp: int = 4) -> str:
    """Format a scalar (number / NaN) for the card with ``dp`` decimals."""
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return "nan"
    return f"{x:.{dp}f}"


def _df_preview_md(df: pd.DataFrame, n: int = 12) -> str:
    """Render the first ``n`` rows of ``df`` as a markdown table.

    ponytail: preview only; full calibration tables are written next to the
    card via the CLI when needed. Markdown tables on wide frames would overflow
    the rendered card.
    """
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = [head, sep]
    for _, row in df.head(n).iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                cells.append(_fmt(v, 4))
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _metrics_block_md(name: str, kind: str, params: dict, metrics: dict) -> str:
    lines = [
        f"### Model: `{name}` ({kind})",
        "",
        f"- params: `{params}`",
        f"- gini (train): {_fmt(metrics.get('gini_train'))}",
        f"- gini (test):  {_fmt(metrics.get('gini_test'))}",
        f"- O/P ratio (test):  {_fmt(metrics.get('op_ratio_test'))}",
        f"- deviance (test):  {_fmt(metrics.get('deviance_test'), 6)}",
    ]
    return "\n".join(lines)


def _render_markdown(run: Run) -> str:
    cfg = run.config
    lines = [
        f"# RiskForge model card -- {cfg.name}",
        "",
        "## Experiment",
        f"- name: `{cfg.name}`",
        f"- data: `{cfg.data_path}`",
        f"- split: `{cfg.split}` (test_size={cfg.test_size}, random_state={cfg.random_state})",
        f"- target: `{cfg.spec.target}`  exposure: `{cfg.spec.exposure}`",
        f"- data fingerprint: `{run.data_fingerprint}`",
        f"- rows: {run.n_rows}  (train {run.n_train} / test {run.n_test})",
        f"- features ({len(run.feature_names)}): "
        + ", ".join(f"`{c}`" for c in run.feature_names),
        "",
    ]
    for name, res in run.models.items():
        lines.append(_metrics_block_md(name, res.kind, res.params, res.metrics))
        lines.append("")
        lines.append("#### Calibration table (test, first 12 rows)")
        lines.append("")
        lines.append(_df_preview_md(res.calibration_table))
        lines.append("")
    return "\n".join(lines)


def _wrap_html(markdown: str, *, title: str) -> str:
    """Wrap markdown in a minimal HTML5 doc; body is ``<pre>``-escaped.

    ponytail: no markdown parser in core deps; replace with a renderer in a
    `plot`/`reporting` extra when styling matters. M5 only needs an HTML
    artifact to exist alongside the markdown.
    """
    body = html.escape(markdown)
    return textwrap.dedent(
        """\
        <!doctype html>
        <html lang="en">
        <head>
        <meta charset="utf-8">
        <title>{title}</title>
        </head>
        <body>
        <pre>{body}</pre>
        </body>
        </html>
        """
    ).format(title=html.escape(title), body=body)


def model_card(run: Run, *, fmt: Literal["md", "html"] = "md") -> str:
    """Return the model card for ``run`` as markdown (default) or HTML."""
    md = _render_markdown(run)
    if fmt == "md":
        return md
    if fmt == "html":
        return _wrap_html(md, title=run.config.name)
    raise ValueError(f"unknown fmt {fmt!r}; expected 'md' or 'html'")
