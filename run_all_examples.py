"""
run_all_examples.py
====================
Batch runner - runs ontology_extractor_openai.py on all images in a folder
and saves all outputs into a structured results directory.

Usage:
  python run_all_examples.py
  python run_all_examples.py --input "F:\path\to\images" --output "F:\path\to\results"

Requirements:
  Same folder as ontology_extractor_openai.py
"""

import os
import sys
import time
import json
import argparse
import traceback
from pathlib import Path

# ── Import the extractor ─────────────────────────────────────────────────────
# Make sure this script is in the same folder as ontology_extractor_openai.py
sys.path.insert(0, str(Path(__file__).parent))
from ontology_extractor_openai import extract_ontology_to_owl

# ── Supported image extensions ───────────────────────────────────────────────
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# ── Default paths  (edit these if you don't use --input / --output flags) ───
DEFAULT_INPUT_DIR  = r"F:\Ontology extractor codes\graph-images"
DEFAULT_OUTPUT_DIR = r"F:\Ontology extractor codes\results"
DEFAULT_BASE_URI   = "http://example.org/ontology#"


def run_all(input_dir: str, output_dir: str, base_uri: str):
    input_path  = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Collect all image files
    images = sorted([
        f for f in input_path.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS
    ])

    if not images:
        print(f"[!] No image files found in: {input_dir}")
        return

    print(f"\n{'='*60}")
    print(f"  Batch Ontology Extractor v4")
    print(f"  Input  : {input_dir}")
    print(f"  Output : {output_dir}")
    print(f"  Images : {len(images)} found")
    print(f"{'='*60}\n")

    summary_rows = []
    failed       = []

    for idx, img_path in enumerate(images, 1):
        stem = img_path.stem
        print(f"\n[{idx}/{len(images)}] Processing: {img_path.name}")
        print("-" * 50)

        # Create per-image output subfolder
        img_out_dir = output_path / stem
        img_out_dir.mkdir(parents=True, exist_ok=True)

        owl_path = img_out_dir / f"{stem}_ontology.owl"
        ttl_path = img_out_dir / f"{stem}.ttl"
        json_path = img_out_dir / f"{stem}_extraction.json"

        start = time.time()
        try:
            graph, extraction, report = extract_ontology_to_owl(
                image_path  = str(img_path),
                output_path = str(owl_path),
                base_uri    = base_uri,
            )

            # Move ttl and json to per-image folder if created in cwd
            _move_if_exists(Path(f"{stem}.ttl"),             ttl_path)
            _move_if_exists(Path(f"{stem}_extraction.json"), json_path)

            elapsed = time.time() - start
            report["image"]   = img_path.name
            report["elapsed"] = f"{elapsed:.1f}s"
            report["status"]  = "OK"
            summary_rows.append(report)

            print(f"  Done in {elapsed:.1f}s  |  "
                  f"classes={report['total_classes']}  "
                  f"instances={report['total_instances']}  "
                  f"edges={report['total_edges']}  "
                  f"completeness={report['completeness']}")

        except Exception as e:
            elapsed = time.time() - start
            print(f"  [ERROR] {e}")
            traceback.print_exc()
            failed.append({"image": img_path.name, "error": str(e)})
            summary_rows.append({
                "image":   img_path.name,
                "status":  "FAILED",
                "error":   str(e),
                "elapsed": f"{elapsed:.1f}s",
            })

        # Small delay to avoid rate limits
        if idx < len(images):
            time.sleep(2)

    # ── Write summary report ─────────────────────────────────────────────────
    summary_path = output_path / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_rows, f, indent=2, ensure_ascii=False)

    # ── Print final table ────────────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print(f"  BATCH COMPLETE")
    print(f"{'='*60}")
    print(f"  Total    : {len(images)}")
    print(f"  Success  : {len(images) - len(failed)}")
    print(f"  Failed   : {len(failed)}")
    print(f"\n  Results saved to: {output_dir}")
    print(f"  Summary  : {summary_path}")

    if failed:
        print(f"\n  Failed images:")
        for f in failed:
            print(f"    - {f['image']}: {f['error']}")

    print(f"\n{'='*60}\n")


def _move_if_exists(src: Path, dst: Path):
    """Move a file to dst if it exists at src and not already at dst."""
    if src.exists() and not dst.exists():
        src.rename(dst)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch ontology extractor - runs on all images in a folder")
    parser.add_argument(
        "--input",  "-i",
        default=DEFAULT_INPUT_DIR,
        help=f"Folder containing input images (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Folder to save results (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument(
        "--base-uri", "-b",
        default=DEFAULT_BASE_URI,
        help=f"Base URI for the ontology (default: {DEFAULT_BASE_URI})")

    args = parser.parse_args()
    run_all(args.input, args.output, args.base_uri)
