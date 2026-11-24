"""
PDF from the HTML reports, printed by a browser in headless mode (Microsoft Edge ships with Windows;
Chrome or Chromium also work). No PDF library to install.

Set ORG_ASSESSMENT_BROWSER to the browser's full path to choose one explicitly.
"""
import os
import shutil
import subprocess
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
NAMES = ["msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser"]


def find_browser():
    env = os.environ.get("ORG_ASSESSMENT_BROWSER")
    if env:
        return env if Path(env).exists() else None
    for name in NAMES:
        found = shutil.which(name)
        if found:
            return found
    for path in CANDIDATES:
        if Path(path).exists():
            return path
    return None


def to_pdf(html_path, pdf_path, browser=None, run=subprocess.run):
    """Print `html_path` to `pdf_path`. Returns the PDF path, or raises RuntimeError."""
    browser = browser or find_browser()
    if not browser:
        raise RuntimeError("no Edge, Chrome or Chromium found; set ORG_ASSESSMENT_BROWSER, "
                           "or open the HTML report and print it to PDF")
    html_path, pdf_path = Path(html_path).resolve(), Path(pdf_path).resolve()
    args = [browser, "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
            "--print-to-pdf-no-header", f"--print-to-pdf={pdf_path}", html_path.as_uri()]
    p = run(args, capture_output=True, timeout=120)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        err = (p.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
        raise RuntimeError(f"the browser did not write the PDF ({err[-1] if err else 'no message'})")
    return pdf_path
