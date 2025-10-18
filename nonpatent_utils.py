
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
import pandas as pd
import numpy as np
import re
import os
import easyocr
from pdf2image import convert_from_path
import atexit, gc
from PIL import Image
import cv2
import pytesseract
from shutil import which
from pathlib import Path
poppler_dir = Path(which("pdfinfo")).parent if which("pdfinfo") else None


nonpatent_articles = {"foa": "First Office Action", 
                      "supplement":"Supplementary Search", 
                      "fsr":"First Search Report",
                      "isr":"International Search Report",
                      "isr_wo":"Written Opinion of the International Search Authority"
                    }

international_office_name = "INTERNATIONAL SEARCHING AUTHORITY"
foreign_code2name = {"CN": "THE STATE INTELLECTUAL PROPERTY OFFICE OF PEOPLE'S REPUBLIC OF CHINA",
                     "EP": "European Patent Office",
                     "JP": "Japan Patent Office (JPO)",
                     "KR": "Patent Office of the Republic of Korea (KR)"
                     } 

month_map = {
    'January': '01', 'February': '02', 'March': '03', 'April': '04',
    'May': '05', 'June': '06', 'July': '07', 'August': '08',
    'September': '09', 'October': '10', 'November': '11', 'December': '12'
}

china_kind_codes = {
    "A": "unexamined",
    "B": "Invention",
    "U": "Utility",
    "S": "Design",
    "C": "Reexamination"
}
korea_kind_codes = {
    "A": "unexamined",
    "B": "Patent",
    "B2": "post-grant",
    "U": "Utility",
    "Y1": "Registered utility model (granted)"
}
japan_kind_codes = {
    "A": "Patent application publication (unexamined)",
    "B1": "Patent grant (initial publication)",
    "B2": "Amended patent publication",
    "U": "Utility model application publication",
    "Y": "Registered utility model"
}
europe_kind_codes = {
    "A1": "EP application with search report",
    "A2": "EP application without search report",
    "A3": "EP search report (for A2)",
    "B1": "EP patent granted (first publication)",
    "B2": "EP patent granted with amendments (second publication)"
}

lang_code_translate = {
            "CN": "zh",
            "EP": "en",
            "JP": "ja",
            "KR": "ko"
}

ocr_lang_code_translate = {
    "CN": "ch_sim",
    "EP": "en",
    "JP": "ja",
    "KR": "ko"
}

def preprocess(img):
    # img: BGR or gray numpy array
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Local contrast (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)

    # Light denoise that preserves strokes
    gray = cv2.bilateralFilter(gray, 5, 75, 75)

    # Adaptive threshold (works well on uneven backgrounds)
    th = cv2.adaptiveThreshold(gray, 255,
                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 31, 15)

    # Deskew
    coords = np.column_stack(np.where(th > 0))
    if coords.size:
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        (h, w) = th.shape[:2]
        M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
        th = cv2.warpAffine(th, M, (w, h), flags=cv2.INTER_CUBIC,
                            borderMode=cv2.BORDER_REPLICATE)

    # Upscale small text
    th = cv2.resize(th, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    return th

def read_pdf_from(pdf_path, detect_lang_code=True):
    images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_DIR)
    # use Country code 
    country_code = pdf_path.split("/")[-1].split(" ")[-1].split(".")[0][:2]
    if detect_lang_code:
        lang_code = ocr_lang_code_translate[country_code]
    else:
        lang_code = "en"

    # Initialize EasyOCR
    reader = easyocr.Reader([lang_code])

    # Extract text from each page
    full_text = ""
    for img in images:
        try:
            img_np = np.array(img)  # Convert PIL image to NumPy array
            img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            img_np = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            img_np = cv2.resize(img_np, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            # img_np = preprocess(np.array(img))
            results = reader.readtext(img_np, 
                                        detail=0, 
                                        paragraph=True)
            page_text = " ".join(results)
            full_text += page_text + "\n"
        finally:
            img.close()  # Close the image to free memory

    return full_text, country_code

@atexit.register
def _cleanup_pil_images():
    for obj in gc.get_objects():
        if isinstance(obj, Image.Image):
            try:
                obj.close()
            except:
                pass

def initial_df():
    df_us = pd.DataFrame(columns = [
                                "Cite No",
                                "Patent Number",
                                "Kind Code¹",
                                "issue Date",
                                "Name of Patentee or Applicant of cited Document",
                                "Pages, Columns, Lines where Relevant Passages or Relevant Figures Appear"
                                ]
                            )

    df_us_application = pd.DataFrame(columns=[
                                "Cite No",
                                "Patent Number",
                                "Kind Code¹",
                                "Publication Date",
                                "Name of Patentee or Applicant of cited Document",
                                "Pages, Columns, Lines where Relevant Passages or Relevant Figures Appear"
                                ])

    df_foreign = pd.DataFrame(columns= [
                                        "Cite No",
                                        "Foreign Document Number³",
                                        "Country Code²",
                                        "Kind Code⁴",
                                        "Publication Date",
                                        "Name of Patentee or Applicant of cited Document",
                                        "Pages, Columns, Lines where Relevant Passages or Relevant Figures Appear"
                                    ]
                            )

    df_non_patent = pd.DataFrame(columns=[
                                "Cite No",
                                "Include name of the author (in CAPITAL LETTERS), title of the article (when appropriate), title of the item (book, magazine, journal, serial, symposium, catalog, etc), date, pages(s), volume-issue number(s), publisher, city and/or country where published."
                                ])

    return df_us, df_us_application, df_foreign, df_non_patent

# read_pdf_from("IDS-示例/P22FS1NW00011US-IDS/First Office Action of family patent CN114056749A.pdf")