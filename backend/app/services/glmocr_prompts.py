from __future__ import annotations

import os


GLMOCR_TRANSCRIBE_PROMPT = os.getenv(
    "GLMOCR_TRANSCRIBE_PROMPT",
    (
        "Transcribe all visible content from this math document image. Include all diagram/figure labels, "
        "measurements, units, symbols, options, and captions exactly as shown. Keep line breaks. Do not solve."
    ),
)

GLMOCR_MEASUREMENT_RECOVERY_PROMPT = os.getenv(
    "GLMOCR_MEASUREMENT_RECOVERY_PROMPT",
    (
        "Extract only measurement labels and figure annotations from the image. Include every number with unit "
        "and nearby label text. One item per line. Do not solve."
    ),
)

GLMOCR_MCQ_STRUCT_PROMPT = os.getenv(
    "GLMOCR_MCQ_STRUCT_PROMPT",
    (
        "Extract the question stem and the answer choices. Output as:\n"
        "STEM:\n<verbatim stem text>\n"
        "CHOICES:\nA) ...\nB) ...\nC) ...\nD) ...\nE) ...\n"
        "Keep exact formatting and math. Do not solve."
    ),
)

GLMOCR_GRAPH_EXTRACTION_PROMPT = os.getenv(
    "GLMOCR_GRAPH_EXTRACTION_PROMPT",
    (
        "Extract graph/plot information only. Include:\n"
        "- axis labels (x/y), units if shown\n"
        "- tick labels and scale/range visible on each axis\n"
        "- legend entries (exact text)\n"
        "- any equations shown on the graph/legend\n"
        "- notable labeled points, intercept labels, asymptote labels if explicitly marked\n"
        "- describe each plotted curve by its legend name and visible style (color/line type) ONLY.\n"
        "Do not compute or infer values not shown. Do not solve."
    ),
)

GLMOCR_TABLE_EXTRACTION_PROMPT = os.getenv(
    "GLMOCR_TABLE_EXTRACTION_PROMPT",
    (
        "Extract the table exactly. Output:\n"
        "1) Markdown table\n"
        "2) CSV version\n"
        "Include row/column headers and all visible cell values. Do not solve."
    ),
)

GLMOCR_GEOMETRY_DIAGRAM_PROMPT = os.getenv(
    "GLMOCR_GEOMETRY_DIAGRAM_PROMPT",
    (
        "Extract diagram structure and labels:\n"
        "- list shapes/objects (cone/cylinder/etc) only if explicitly depicted\n"
        "- list all dimension labels (numbers + units) and where they apply (height/radius/diameter)\n"
        "- list any marked relationships (parallel/perpendicular/congruent) if shown\n"
        "Do not calculate. Do not solve."
    ),
)

GLMOCR_TEXT_ONLY_CLEAN_PROMPT = os.getenv(
    "GLMOCR_TEXT_ONLY_CLEAN_PROMPT",
    (
        "Extract only the problem statement text (no headers/footers, no confidence lines). "
        "Keep math exactly. Do not solve."
    ),
)

