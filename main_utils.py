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
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT, WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
import os
from pathlib import Path
from pdf2image import pdfinfo_from_path
from add_ids import add_non_patent_citation
from extract_utils import extract_isr_from_path, extract_foa_from_path, extract_fsr_from_path
from article_utils import article_info_from_path
from nonpatent_utils import nonpatent_articles, international_office_name, initial_df
from shutil import which
from pathlib import Path

# Citation templates
TEMPLATE_ISR = "{office}. International Search Report{extra} for PCT Application no. {p_no}{lang}, mailed {date}. pages 1-{pages}."
TEMPLATE_FSR = "{office}. First Search Report for PCT Application no. {p_no}{lang}, mailed {date}. pages 1-{pages}."
TEMPLATE_FOA = "{office}. First Office Action for PCT Application no. {p_no}{lang}, mailed {date}. pages 1-{pages}."
TEMPLATE_SUP = "{office}. Supplementary Search for PCT Application no. {p_no}{lang}, mailed {date}. pages 1-{pages}."
TEMPLATE_GENERIC = "{article}. pages 1-{pages}."

def parent_dirs_for_filename(root: str | Path, filename: str):
    # returns all parent dirs of files named exactly `filename`
    return [p.parent for p in Path(root).rglob(filename)]

def english_suffix(eng_exists: bool) -> str:
    """Returns language suffix used in your citations when English translation is present."""
    return " and English translation" if eng_exists else ""

def count_pages(pdf_path: str) -> int:
    """Fast page count without rendering images."""
    try:
        return int(pdfinfo_from_path(pdf_path, poppler_path=POPPLER_DIR)["Pages"])
    except Exception:
        print("Error counting pages for:", pdf_path)
        return 0
    
def total_pages(file_path: str, eng_path: str) -> int:
    pages = count_pages(file_path)
    en_pages = count_pages(eng_path) if os.path.exists(eng_path) else 0
    return pages + en_pages

def handle_isr(file_path, eng_path, files, df_us, df_us_application, df_foreign, df_non_patent):
    # Choose which path to parse for data extraction
    path_for_extract = eng_path if os.path.exists(eng_path) else file_path
    df_us, df_us_application, df_foreign, info = extract_isr_from_path(
        path_for_extract, df_us, df_us_application, df_foreign
    )
    p_no, date = info[0], info[1]

    pages = total_pages(file_path, eng_path)
    extra = " and Written Opinion" if "Written Opinion" in files else ""
    citation = TEMPLATE_ISR.format(
        office=international_office_name,
        p_no=p_no,
        date=date,
        pages=pages,
        extra=extra,
        lang=english_suffix(os.path.exists(eng_path))
    )
    df_non_patent = add_non_patent_citation(df_non_patent, citation)
    return df_us, df_us_application, df_foreign, df_non_patent

def handle_fsr(file_path, eng_path, df_us, df_us_application, df_foreign, df_non_patent):
    path_for_extract = eng_path if os.path.exists(eng_path) else file_path
    df_us, df_us_application, df_foreign, info = extract_fsr_from_path(
        path_for_extract, df_us, df_us_application, df_foreign
    )
    p_no, date, en_pages_or_pages, article_country = info[0], info[1], info[2], info[3]

    pages = total_pages(file_path, eng_path)
    citation = TEMPLATE_FSR.format(
        office=article_country,
        p_no=p_no,
        date=date,
        pages=pages,
        lang=english_suffix(os.path.exists(eng_path))
    )
    df_non_patent = add_non_patent_citation(df_non_patent, citation)
    return df_us, df_us_application, df_foreign, df_non_patent

def handle_foa_or_sup(file_path, eng_path, df_us, df_us_application, df_foreign, df_non_patent, is_sup=False):
    # For FOA/Supplementary Search you pass file_path to introduce country code when eng exists
    if os.path.exists(eng_path):
        df_us, df_us_application, df_foreign, info = extract_foa_from_path(
            eng_path, df_us, df_us_application, df_foreign, file_path
        )
    else:
        df_us, df_us_application, df_foreign, info = extract_foa_from_path(
            file_path, df_us, df_us_application, df_foreign
            )

    if len(info) >= 3:
        patent_office, p_no, date = info[0], info[1], info[2]
    else:
        patent_office, p_no, date = "None", "None", "None"
    try:
        pages = total_pages(file_path, eng_path)
        template = TEMPLATE_SUP if is_sup else TEMPLATE_FOA
        citation = template.format(
            office=patent_office,
            p_no=p_no,
            date=date,
            pages=pages,
            lang=english_suffix(os.path.exists(eng_path))
        )
        df_non_patent = add_non_patent_citation(df_non_patent, citation)
    except Exception as e:
        print(f"Error processing FOA in total pages for {file_path}: {e}")  
  
    return df_us, df_us_application, df_foreign, df_non_patent

def handle_generic(file, file_path,  df_non_patent):
    """Articles that don't need extraction; only office/pno/date/pages."""
    # patent_office, p_no, date = article_info_from_path(file_path)
    pages = count_pages(file_path)
    # article_name = file.split("of")[0].strip()  # e.g., "Written Opinion", "Decision", etc.
    article_name = file

    citation = TEMPLATE_GENERIC.format(
        article=article_name.split(".pdf")[0],  # remove .pdf suffix if present
        pages=pages
    )
    df_non_patent = add_non_patent_citation(df_non_patent, citation)
    return df_non_patent
