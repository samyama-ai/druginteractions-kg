"""Download all required data files for druginteractions-kg.

Fetches DrugBank CC0, DGIdb, SIDER, ChEMBL, TTD, and OpenFDA datasets.
Supports resume (skips files that already exist).

Usage:
    python -m etl.download_data --data-dir data
    python -m etl.download_data --data-dir data --sources drugbank dgidb sider
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sys
import time
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

DRUGBANK_FILES = {
    "drugbank_vocabulary.csv": (
        "https://go.drugbank.com/releases/latest/downloads/all-drugbank-vocabulary"
    ),
}

DGIDB_FILES = {
    "interactions.tsv": "https://dgidb.org/data/monthly_tsvs/2024-Feb/interactions.tsv",
    "genes.tsv": "https://dgidb.org/data/monthly_tsvs/2024-Feb/genes.tsv",
    "drugs.tsv": "https://dgidb.org/data/monthly_tsvs/2024-Feb/drugs.tsv",
}

SIDER_FILES = {
    "meddra_all_se.tsv.gz": "http://sideeffects.embl.de/media/download/meddra_all_se.tsv.gz",
    "meddra_all_indications.tsv.gz": (
        "http://sideeffects.embl.de/media/download/meddra_all_indications.tsv.gz"
    ),
    "drug_names.tsv": "http://sideeffects.embl.de/media/download/drug_names.tsv",
}

CHEMBL_FILES = {
    "chembl_34_sqlite.tar.gz": (
        "https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/"
        "chembl_34_sqlite.tar.gz"
    ),
}

TTD_FILES = {
    "P1-01-TTD_target_download.txt": (
        "https://db.idrblab.net/ttd/sites/default/files/ttd_database/"
        "P1-01-TTD_target_download.txt"
    ),
    "P1-05-Drug_disease.txt": (
        "https://db.idrblab.net/ttd/sites/default/files/ttd_database/"
        "P1-05-Drug_disease.txt"
    ),
}

SOURCES = {
    "drugbank": (DRUGBANK_FILES, "drugbank"),
    "dgidb": (DGIDB_FILES, "dgidb"),
    "sider": (SIDER_FILES, "sider"),
    "chembl": (CHEMBL_FILES, "chembl"),
    "ttd": (TTD_FILES, "ttd"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    elif nbytes < 1024 ** 2:
        return f"{nbytes / 1024:.1f} KB"
    elif nbytes < 1024 ** 3:
        return f"{nbytes / 1024**2:.1f} MB"
    else:
        return f"{nbytes / 1024**3:.2f} GB"


def _should_skip(path: Path, expected_size: int | None) -> bool:
    if not path.exists():
        return False
    if expected_size is None or expected_size <= 0:
        return path.stat().st_size > 0
    return path.stat().st_size == expected_size


def _remote_size(url: str, timeout: int = 15) -> int | None:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit():
            return int(cl)
    except requests.RequestException:
        pass
    return None


def download_file(url: str, dest: Path, label: str = "") -> Path:
    """Stream-download a single file with progress."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    display = label or dest.name

    remote_sz = _remote_size(url)
    if _should_skip(dest, remote_sz):
        size_str = _fmt_size(dest.stat().st_size)
        print(f"  [skip] {display} ({size_str}, already exists)")
        return dest

    print(f"  [download] {display} ...", end="", flush=True)
    t0 = time.time()

    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    total = int(resp.headers.get("Content-Length", 0))
    downloaded = 0
    last_pct = -1

    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=256 * 1024):
            if chunk:
                fh.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    if pct >= last_pct + 10:
                        print(f" {pct}%", end="", flush=True)
                        last_pct = pct

    elapsed = time.time() - t0
    final_size = dest.stat().st_size
    rate = final_size / elapsed if elapsed > 0 else 0
    print(f" done ({_fmt_size(final_size)}, {elapsed:.1f}s, {_fmt_size(int(rate))}/s)")
    return dest


def decompress_gzip(gz_path: Path) -> Path:
    """Decompress a .gz file in place, returning path of decompressed file."""
    if not gz_path.name.endswith(".gz"):
        return gz_path

    out_path = gz_path.with_suffix("")
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"  [skip] decompress {gz_path.name} (already done)")
        return out_path

    print(f"  [decompress] {gz_path.name} -> {out_path.name} ...", end="", flush=True)
    t0 = time.time()
    with gzip.open(gz_path, "rb") as fin, open(out_path, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    elapsed = time.time() - t0
    size = out_path.stat().st_size
    print(f" done ({_fmt_size(size)}, {elapsed:.1f}s)")
    return out_path


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def download_source(
    source_name: str,
    files: dict[str, str],
    data_dir: Path,
) -> dict[str, Path]:
    subdir = data_dir / source_name
    subdir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}

    print(f"\n=== {source_name.upper()} ===")
    for fname, url in files.items():
        try:
            dest = subdir / fname
            download_file(url, dest, label=fname)
            if fname.endswith(".gz"):
                decompressed = decompress_gzip(dest)
                result[decompressed.name] = decompressed
            else:
                result[fname] = dest
        except requests.RequestException as exc:
            print(f"  [ERROR] {fname}: {exc}")
        except OSError as exc:
            print(f"  [ERROR] {fname} (I/O): {exc}")

    return result


def download_all(
    data_dir: str | Path,
    phases: list[str] | None = None,
) -> dict[str, Path]:
    """Download all data files.

    Args:
        data_dir: Root data directory.
        phases: Optional list of source names. Default: all.

    Returns:
        Dict mapping filename to local path.
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    if phases is None:
        phases = list(SOURCES.keys())

    all_files: dict[str, Path] = {}
    t0 = time.time()

    for phase in phases:
        if phase in SOURCES:
            file_dict, _subdir = SOURCES[phase]
            result = download_source(phase, file_dict, data_path)
            all_files.update(result)
        else:
            print(f"\n[WARN] Unknown source: {phase}, skipping")

    elapsed = time.time() - t0
    print(f"\n--- Download complete: {len(all_files)} files in {elapsed:.0f}s ---")
    for name, path in sorted(all_files.items()):
        size = path.stat().st_size if path.exists() else 0
        print(f"  {name}: {_fmt_size(size)} -> {path}")

    return all_files


def main():
    parser = argparse.ArgumentParser(
        description="Download datasets for druginteractions-kg.",
    )
    parser.add_argument("--data-dir", default="data",
                        help="Root directory for downloaded data (default: data)")
    parser.add_argument("--sources", nargs="*", default=None,
                        help="Specific sources to download. Default: all")
    args = parser.parse_args()

    download_all(args.data_dir, phases=args.sources)


if __name__ == "__main__":
    main()
