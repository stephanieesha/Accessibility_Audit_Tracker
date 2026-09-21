"""
Builds the accessibility report as a static site for Netlify.

The scans themselves run on GitHub Actions (see .github/workflows/scan.yml),
which commit history/a11y-history.jsonl and screenshots/ back to the repo.
Netlify then rebuilds this site from those files, so the trend data is kept
in git and needs no database or running server.

Run locally with:  python build_site.py   (writes ./site)
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "analyzer"))

import generate_report  # noqa: E402

SITE = ROOT / "site"


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    generate_report.OUTPUT_PATH = SITE / "index.html"
    generate_report.main()

    screenshots = ROOT / "screenshots"
    if screenshots.exists():
        shutil.copytree(screenshots, SITE / "screenshots")

    print(f"Static report ready in {SITE}")


if __name__ == "__main__":
    main()
