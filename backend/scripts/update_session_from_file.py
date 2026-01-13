import argparse
import json
from pathlib import Path

from sqlmodel import Session, select

from app.database import engine
from app.models import ChatMessage
from app.schemas.na_math_solver_v3 import PlotPlanV3
from app.services.visualization.plot_renderer import get_plot_renderer


def build_visuals_from_plot(plot: dict) -> list[dict]:
    if not plot or not plot.get("should_plot") or not plot.get("plan"):
        return []

    plan_raw = plot["plan"]
    plan = PlotPlanV3(**plan_raw) if isinstance(plan_raw, dict) else plan_raw
    series = get_plot_renderer().generate_data(plan)
    if not series:
        return []

    markers = []
    for ann in plan.annotations or []:
        if ann.point:
            markers.append({
                "label": ann.detail or ann.name,
                "x": ann.point.x,
                "y": ann.point.y
            })

    plot_type = plot.get("plot_type", "function")
    visual_type = "line_plot" if plot_type in ["line", "line_plot"] else "function_plot"

    return [{
        "id": "plot-1",
        "type": visual_type,
        "title": plan.title,
        "series": series,
        "markers": markers,
        "axes": {
            "x_label": plan.axes.x_label,
            "y_label": plan.axes.y_label
        },
        "domain": {
            "x_min_latex": str(plan.recommended_window.x_min),
            "x_max_latex": str(plan.recommended_window.x_max)
        }
    }]


def update_session_structured_data(session_id: int, json_path: Path) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    visuals = build_visuals_from_plot(data.get("plot", {}))
    if visuals and not data.get("visuals"):
        data["visuals"] = visuals

    final_answer = data.get("solution", {}).get("final_answer")

    with Session(engine) as session:
        msg = session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.role == "assistant")
            .order_by(ChatMessage.created_at.desc())
        ).first()

        if not msg:
            raise SystemExit(f"No assistant message found for session {session_id}.")

        msg.structured_data = data
        if final_answer:
            msg.content = final_answer

        session.add(msg)
        session.commit()

    steps_count = len(data.get("solution", {}).get("steps", []))
    print(f"Updated session {session_id} with {steps_count} steps and {len(data.get('visuals', []))} visuals.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace session structured_data from a JSON file.")
    parser.add_argument("--session-id", type=int, default=63)
    parser.add_argument(
        "--json-path",
        type=Path,
        default=Path("static_design/response.txt"),
        help="Path to JSON response file"
    )
    args = parser.parse_args()

    if not args.json_path.exists():
        raise SystemExit(f"Response file not found: {args.json_path}")

    update_session_structured_data(args.session_id, args.json_path)


if __name__ == "__main__":
    main()
