import json
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8765"


def fetch(path):
    request = Request(
        BASE_URL + path,
        headers={"Cache-Control": "no-cache"},
    )
    start = time.perf_counter()
    with urlopen(request, timeout=10) as response:
        response.read()
        if response.status != 200:
            raise RuntimeError(f"{path}: HTTP {response.status}")
    return (time.perf_counter() - start) * 1000.0


def library_rows(params):
    base = {
        "batch": "40",
        "sort_by": "created",
        "sort_dir": "desc",
    }
    base.update(params)
    return "/library-rows?" + urlencode(base, doseq=True)


def median_sample(fn, repeats=7):
    fn()  # warmup
    values = [fn() for _ in range(repeats)]
    return {
        "median_ms": round(statistics.median(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
        "samples_ms": [round(value, 3) for value in values],
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: measure_library_http.py LABEL OUTPUT.json")
    label = sys.argv[1]
    output = Path(sys.argv[2])

    cases = {
        "initial_shell_plus_rows": lambda: fetch("/") + fetch(library_rows({})),
        "type_cover_rows": lambda: fetch(library_rows({"kind_filter": "Cover"})),
        "workspace_studio_a_rows": lambda: fetch(library_rows({"workspace": "Studio A"})),
        "tag_bulk_rows": lambda: fetch(library_rows({"tag_filter": "#bulk"})),
    }

    result = {"label": label, "cases": {}}
    for name, fn in cases.items():
        result["cases"][name] = median_sample(fn)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
