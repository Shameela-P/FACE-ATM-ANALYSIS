"""Execute the generated Phase 4 notebook and persist cell outputs."""

import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient

NOTEBOOK_DIR = Path(__file__).resolve().parent.parent.parent / "notebooks"
NOTEBOOK_PATH = NOTEBOOK_DIR / "face_biometrics_and_antispoofing_analysis.ipynb"


def run_notebook():
    print(f"Reading notebook from: {NOTEBOOK_PATH}")
    with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    # Set working directory to project root or backend so paths resolve cleanly
    client = NotebookClient(
        nb,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOK_DIR.parent)}}
    )

    print("Executing notebook cells with NotebookClient...")
    client.execute()

    print(f"Saving executed notebook with outputs to: {NOTEBOOK_PATH}")
    with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    print("Notebook successfully executed and persisted.")


if __name__ == "__main__":
    from build_notebook import build_notebook
    build_notebook()
    run_notebook()
