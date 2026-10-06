"""Exercise the real Streamlit script with representative M6 questions.

This hits the configured embedding, vector search, reranker, and answer APIs.
It records UI element counts and service reranking metrics, not chunk text.
"""
from __future__ import annotations

import csv
import json
import logging
import sys
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    logging.getLogger().setLevel(logging.WARNING)
    eval_path = ROOT / "src/car_search_rag/car_search/docs/M6_RETRIEVAL_RESULTS.csv"
    with eval_path.open(encoding="utf-8-sig", newline="") as file:
        questions = {
            row["ID"]: row["Question"]
            for row in csv.DictReader(file)
            if row["ID"] in {"M6-03", "M6-04", "M6-05", "M6-09", "M6-11"}
        }

    results = []
    for question_id, question in questions.items():
        app = AppTest.from_file(str(ROOT / "app_kbj.py"), default_timeout=150)
        app.run(timeout=150)
        if app.exception:
            raise RuntimeError(f"{question_id}: initial app render error: {app.exception[0].message}")
        started = time.perf_counter()
        app.chat_input[0].set_value(question).run(timeout=150)
        elapsed = time.perf_counter() - started
        exceptions = [item.message for item in app.exception]
        texts = [item.value for item in app.markdown]
        sources = [text for text in texts if "chunk" in text and "p." in text]
        answers = [text for text in texts if text and question not in text and "chunk" not in text]
        images = len(app.get("imgs"))
        service = app.session_state.get("messages", [])
        assistant = next((item for item in reversed(service) if item.get("role") == "assistant"), {})
        results.append({
            "question_id": question_id,
            "question": question,
            "elapsed_seconds": round(elapsed, 3),
            "answer_rendered": bool(assistant.get("content")),
            "source_count": len(assistant.get("sources", [])),
            "image_count": len(assistant.get("images", [])),
            "ui_image_elements": images,
            "ui_exceptions": exceptions,
            "answer_preview": (assistant.get("content") or "")[:300],
        })
        print(json.dumps(results[-1], ensure_ascii=False))
        if exceptions:
            raise RuntimeError(f"{question_id}: Streamlit UI exception: {exceptions}")
        if not assistant.get("content"):
            raise RuntimeError(f"{question_id}: no assistant answer rendered")
        if not assistant.get("sources"):
            raise RuntimeError(f"{question_id}: no source citations rendered")
    print(json.dumps({"summary": {
        "questions": len(results),
        "all_answered": all(row["answer_rendered"] for row in results),
        "all_cited": all(row["source_count"] > 0 for row in results),
        "total_images_rendered": sum(row["ui_image_elements"] for row in results),
        "mean_elapsed_seconds": round(sum(row["elapsed_seconds"] for row in results) / len(results), 3),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
