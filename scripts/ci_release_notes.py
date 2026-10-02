"""Release description for the Render workflow: what was rendered and how long each job took (pure Python).

    python3 scripts/ci_release_notes.py DIR --samples 256 --sha abc1234 --started 2026-10-03T08:00:00Z

DIR holds one `<name>.time` file per job, written by the workflow: `<name> <mode> <seconds>`.
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path


def hms(seconds):
    if seconds >= 3600:
        h, m = divmod(round(seconds / 60), 60)
        return f"{h} h {m:02d} min"
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s:02d} s"


def read_times(folder):
    rows = []
    for f in sorted(Path(folder).glob("*.time")):
        name, mode, seconds = f.read_text().split()
        rows.append((name, mode, float(seconds)))
    return rows


def notes(rows, samples, sha, wall_seconds):
    total = sum(s for _, _, s in rows)
    lines = [
        f"Final renders from `{sha}`: Cycles on CPU (GitHub-hosted runners), {samples} samples per pixel, "
        "adaptive sampling with OpenImageDenoise.",
        "",
        f"- Wall-clock time of the whole run: **{hms(wall_seconds)}** (jobs run in parallel)",
        f"- Total job time: **{hms(total)}** over {len(rows)} jobs",
        "",
        "| Job | Mode | Time |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {n} | {m} | {hms(s)} |" for n, m, s in rows]
    lines += [
        "",
        "Each camera view is attached twice: PNG (lossless) and JPG (quality 92, smaller, used by the README).",
        "Also attached: the technical plan (PDF and PNGs), the furnished plan, the layout proposal and the shell overviews.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--samples", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--started", required=True, help="ISO time the workflow run started (UTC)")
    a = ap.parse_args()
    started = datetime.fromisoformat(a.started.replace("Z", "+00:00"))
    wall = (datetime.now(UTC) - started).total_seconds()
    sys.stdout.write(notes(read_times(a.folder), a.samples, a.sha, wall))
