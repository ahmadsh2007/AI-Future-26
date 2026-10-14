"""Run the full validation suite and print a pass/fail report per area.

    python scripts/run_all_tests.py            # everything (first run downloads e5-large + reranker, ~5 GB)
    python scripts/run_all_tests.py --fast     # skip @slow tests (e5-large, reranker)
Requires: pip install -r requirements.txt -r requirements-test.txt, `python download_test_data.py`,
and (for LLM tests) a running Ollama with qwen2.5:7b / qwen3:8b - missing models are reported as SKIP.
"""
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AREAS = {
    "TestThreshold": "Vector threshold filtering (+ per-model config, calibration)",
    "TestLLMRefusal": "In-context LLM refusal + post-processing + prompt modes",
    "TestPDF": "Arabic PDF text extraction integrity",
    "TestBackends": "Multi-backend config sanity (ollama/openai/hf/reranker)",
}


def main():
    xml = Path(tempfile.mkdtemp()) / "junit.xml"
    cmd = [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}", "-p", "no:cacheprovider"]
    if "--fast" in sys.argv:
        cmd += ["-m", "not slow"]
    rc = subprocess.call(cmd, cwd=ROOT)

    stats = defaultdict(lambda: defaultdict(int))
    failures = []
    for tc in ET.parse(xml).getroot().iter("testcase"):
        area = tc.get("classname").split(".")[-1]
        if tc.find("failure") is not None or tc.find("error") is not None:
            stats[area]["FAIL"] += 1
            failures.append(f"{area}::{tc.get('name')}")
        elif tc.find("skipped") is not None:
            stats[area]["SKIP"] += 1
        else:
            stats[area]["PASS"] += 1

    print("\n" + "=" * 78 + "\nVALIDATION REPORT\n" + "=" * 78)
    for key, title in AREAS.items():
        s = stats[key]
        status = "FAIL" if s["FAIL"] else ("PASS" if s["PASS"] else "SKIP")
        print(f"[{status}] {title:<64} pass={s['PASS']} fail={s['FAIL']} skip={s['SKIP']}")
    for f in failures:
        print("  FAILED:", f)
    print("=" * 78 + f"\nOVERALL: {'PASS' if rc == 0 else 'FAIL'}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
