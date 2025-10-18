from __future__ import annotations
# --- Poppler init (put near the top of app.py, before you import/use pdf2image) ---
import os, sys
from pathlib import Path
from shutil import which

def init_poppler_dir() -> str | None:
    """
    Prefer bundled Poppler under _MEIPASS/bin (if running as a .app built with the spec),
    otherwise fall back to Homebrew (/opt/homebrew/bin or /usr/local/bin).
    Returns a directory path you can pass to pdf2image's poppler_path=...
    """
    # 1) If bundled (from your .spec using Tree(..., prefix='bin'/'lib')), expose it.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
        bin_dir = base / "bin"
        lib_dir = base / "lib"
        if bin_dir.exists():
            os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH','')}"
        if lib_dir.exists():
            # helps resolve libpoppler*.dylib for the bundled tools
            os.environ["DYLD_LIBRARY_PATH"] = f"{lib_dir}:{os.environ.get('DYLD_LIBRARY_PATH','')}"
        if (bin_dir / "pdfinfo").exists():
            return str(bin_dir)

    # 2) Otherwise try Homebrew/system installs.
    # Add common Homebrew locations to PATH (Finder launches miss these).
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if os.path.isdir(p) and p not in os.environ.get("PATH", ""):
            os.environ["PATH"] = p + ":" + os.environ.get("PATH", "")

    p = which("pdfinfo")
    return str(Path(p).parent) if p else None

POPPLER_DIR = init_poppler_dir()
# --- end poppler init ---

# app.py
import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, Tuple
import pandas as pd
from main_utils import handle_foa_or_sup, handle_fsr, handle_generic, handle_isr
from output_utils import output2Doc
from nonpatent_utils import nonpatent_articles, initial_df

# Default for CLI; GUI will pass an explicit Path
DEFAULT_INPUT = Path("./input")

# ---- Output directory resolver (as you have) ----
def _pick_out_dir(preferred: Optional[Path] = None) -> Path:
    """
    Picks a writable output directory in priority order.
    """
    candidates: list[Path] = []
    if preferred:
        candidates.append(Path(preferred))
    if os.environ.get("OUTPUT_DIR"):
        candidates.append(Path(os.environ["OUTPUT_DIR"]))
    candidates += [
        Path("/out"),                                # Docker
        Path.cwd() / "out",                          # Local default
        Path.home() / "Desktop" / "IDS-Results",    # Fallback
    ]

    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            test = p / ".write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return p
        except Exception:
            continue

    raise RuntimeError("No writable output directory found. Set OUTPUT_DIR or pass out_dir.")

# ---- Helpers ----
def _is_pdf_to_process(fname: str) -> bool:
    """Case-insensitive PDF check and exclude 'English Translation' anywhere in name."""
    f = fname.lower()
    return f.endswith(".pdf") and "english translation" not in f

def _iter_pdf_files(roots: Sequence[Path]) -> Iterable[Tuple[Path, str]]:
    """
    Walk one or more roots and yield (root_path, filename) for target PDFs.
    Sorted for stable order (nice for GUI progress).
    """
    for base in roots:
        base = Path(base)
        for root, _, files in os.walk(base):
            # sort files for predictable processing order
            for fname in sorted(files):
                if _is_pdf_to_process(fname):
                    yield Path(root), fname

def _guess_article(fname: str, article_prefixes: Tuple[str, ...]) -> Optional[str]:
    """Return matched article prefix by startswith (case-sensitive as your original)."""
    for a in article_prefixes:
        if fname.startswith(a):
            return a
    return None

def _as_paths(folder_path: Path | Sequence[Path]) -> list[Path]:
    """Allow a single Path or a list/tuple of Paths."""
    if isinstance(folder_path, (list, tuple)):
        return [Path(p) for p in folder_path]
    return [Path(folder_path)]

# ---- Main pipeline ----
def main(
    folder_path: Path | Sequence[Path] = DEFAULT_INPUT,
    progress_cb: Optional[Callable[[int, int, str, float], None]] = None,
    out_dir: Optional[Path] = None,
):
    """
    Run extraction over a folder (or list of folders).

    Returns: path to the generated output file (str or Path, depending on output2Doc).
    """
    
    t0 = time.time()

    roots = _as_paths(folder_path)
    # Extract a "case_no" label: for a single folder use its name; for multiple, join names
    if len(roots) == 1:
        case_no = roots[0].name
    else:
        case_no = "_".join(p.name for p in roots)

    # Resolve output directory
    OUT_DIR = _pick_out_dir(out_dir)

    # Pandas display options (useful if you print DataFrames during debugging)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_colwidth", None)

    # Pre-scan
    pdf_files = list(_iter_pdf_files(roots))
    total = len(pdf_files)
    done = 0
    if progress_cb:
        progress_cb(done, total, "Scanning complete. Starting…", 0.0)

    # Initialize DataFrames
    df_us, df_us_application, df_foreign, df_non_patent = initial_df()

    # Article prefixes
    # (keep original values, no lowercasing: your handlers expect exact names)
    article_prefixes = tuple(nonpatent_articles.values())

    # Process
    errors: list[str] = []
    for root_path, fname in pdf_files:
        try:
            files_set = set(os.listdir(root_path))  # membership for sibling checks
            file_path = (root_path / fname)

            # Build expected English translation name in the SAME directory
            eng_path = file_path.with_name(f"English Translation of {fname}")

            matched_article = _guess_article(fname, article_prefixes)

            # print("******************************")
            # print(f"[DEBUG] Processing file: {fname}")
            # print(f"[DEBUG] Detected article: {matched_article}")

            if matched_article is None:
                # Skip if starts with two capital letters (your rule)
                if re.match(r"^[A-Z]{2}", fname):
                    pass  # skip silently
                else:
                    # generic non-patent
                    df_non_patent = handle_generic(fname, str(file_path), df_non_patent)

            elif matched_article == "International Search Report":
                df_us, df_us_application, df_foreign, df_non_patent = handle_isr(
                    str(file_path),
                    str(eng_path),
                    files_set,
                    df_us,
                    df_us_application,
                    df_foreign,
                    df_non_patent,
                )

            elif matched_article == "First Search Report":
                df_us, df_us_application, df_foreign, df_non_patent = handle_fsr(
                    str(file_path),
                    str(eng_path),
                    df_us,
                    df_us_application,
                    df_foreign,
                    df_non_patent,
                )

            elif matched_article == "First Office Action":
                df_us, df_us_application, df_foreign, df_non_patent = handle_foa_or_sup(
                    str(file_path),
                    str(eng_path),
                    df_us,
                    df_us_application,
                    df_foreign,
                    df_non_patent,
                    is_sup=False,
                )

            elif matched_article == "Supplementary Search":
                df_us, df_us_application, df_foreign, df_non_patent = handle_foa_or_sup(
                    str(file_path),
                    str(eng_path),
                    df_us,
                    df_us_application,
                    df_foreign,
                    df_non_patent,
                    is_sup=True,
                )

        except Exception as e:
            # collect error but keep going
            errors.append(f"{file_path}: {e}")
        finally:
            done += 1
            if progress_cb:
                progress_cb(done, total, f"Processed: {fname}", time.time() - t0)

    # Deduplicate
    df_us_clean = df_us.drop_duplicates(subset=["Patent Number"])
    df_us_application_clean = df_us_application.drop_duplicates(subset=["Patent Number"])
    df_foreign_clean = df_foreign.drop_duplicates(subset=["Foreign Document Number³"])
    df_non_patent_clean = df_non_patent.drop_duplicates(
        subset=[
            "Include name of the author (in CAPITAL LETTERS), title of the article (when appropriate), title of the item (book, magazine, journal, serial, symposium, catalog, etc), date, pages(s), volume-issue number(s), publisher, city and/or country where published."
        ]
    )

    # Output
    out_file = output2Doc(
        df_us_clean,
        df_us_application_clean,
        df_foreign_clean,
        df_non_patent_clean,
        case_no=f"{case_no}_results",
        output_path=OUT_DIR,
    )

    if progress_cb:
        progress_cb(total, total, "Done", time.time() - t0)

    # Optionally, return a small summary alongside the output path (GUI could display it)
    # return {"out_file": out_file, "errors": errors, "counts": {"total": total, "ok": total - len(errors), "errors": len(errors)}}
    return out_file


# ---- CLI entrypoint (handy for testing without GUI) ----
def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Patent/IDS extractor")
    p.add_argument("input", nargs="*", help="One or more input folders (default: ./input)")
    p.add_argument("--out", dest="out_dir", type=Path, help="Output folder (optional)")
    return p.parse_args(argv)

if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    inputs: list[Path]
    if args.input:
        inputs = [Path(x) for x in args.input]
    else:
        inputs = [DEFAULT_INPUT]
    main(inputs if len(inputs) > 1 else inputs[0], out_dir=args.out_dir)
