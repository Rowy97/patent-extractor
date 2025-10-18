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
import argostranslate.translate
from nonpatent_utils import read_pdf_from, lang_code_translate
from shutil import which
from pathlib import Path


#initial offline reader for three languages
reader_cn = easyocr.Reader(['ch_sim', 'en'], gpu=False)
reader_jp = easyocr.Reader(['ja', 'en'], gpu=False)
reader_kr = easyocr.Reader(['ko', 'en'], gpu=False)

def search_find_patentee(country_code, patent_no, kind_code, rootpath = "./", find_date = False):
    """
    Tne function is called to search and locate patentee info from the original patent pdf file.
    The country_code, patent_no, kind_code are used to search corresponding file under the root_folder

    input:
        patent_no: country code + patent_no + kind_code

    output:
        patentee info, (publication_date)
    """
    patent_no = patent_no.replace("-", "")
    whole_patent_no = f"{country_code}{patent_no}{kind_code}"
    #search for folder that starts with the kind code
    folder_path = None
    for name in os.listdir(rootpath):
        real_path = os.path.join(rootpath, name)
        #if name exclude the kindcode is matched
        if name == whole_patent_no or name[:-1] == whole_patent_no:
            folder_path = real_path
    #find the real folder path for each pdf from citations
    if folder_path is not None:
        for dirpath, _, filenames in os.walk(folder_path):
            for filename in filenames:
                if filename.startswith(whole_patent_no) and filename.lower().endswith(".pdf"):
                    pdf_path = os.path.join(dirpath, filename)
                    try:
                        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_DIR)
                        full_text = ""
                        for img in images[:3]:
                            if country_code == "CN":
                                result = reader_cn.readtext(np.array(img), detail=0)
                            elif country_code =="JP":
                                result = reader_jp.readtext(np.array(img), detail=0)
                            elif country_code =="KR":
                                result = reader_kr.readtext(np.array(img), detail=0)
                            else:
                                print("Country code out of bound!")
                            full_text += "\n".join(result) + "\n"

                        # # Detect language from some of the text
                        # lang_code = detect_language_basic(full_text)
                        lang_code = lang_code_translate[country_code]
                        # print(lang_code)
                        if find_date:
                            return extract_patentee_from_text(full_text, lang_code), extract_publication_date_from_text(full_text, lang_code)
                        else:
                            return extract_patentee_from_text(full_text, lang_code)
                    except Exception as e:
                        print(f"Error reading {pdf_path}: {e}")
    else:
        print(f"No pdf folder found based on this info: {country_code}, {patent_no}, {kind_code}, return two empty strings")
        return "", ""

def extract_patentee_from_text(text, lang_code='zh'):
    patterns = {
        'zh': r"(?:申请人|专利权人)[:：]?\s*(\S+)",
        'ja': r"出願人[:：]?\s*(.+)",
        'ko': r"\(주\)\s*([가-힣]+)",
        # 'ko': r"\(\s*73\s*\)\s*특허권자\s*\(주\)(\S+)",
        'en': r"(?:Applicant|Patentee|Assignee)[:：]?\s*(.+)"
    }
    pattern = patterns.get(lang_code)
    if pattern:
        # text = normalize_ocr(text) #normalize some error in ocr
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            patentee_raw = match.group(1).strip()
            print(patentee_raw)
            if lang_code != 'en':
                return translate_offline_argos(patentee_raw, from_lang=lang_code, to_lang='en')
            return patentee_raw
    print(f"Warning: No patentee detected from searched pdf in {lang_code}!")
    return ""

def extract_publication_date_from_text(text, lang_code='zh'):
    patterns = {
        "zh": r"(?:申请日|申请公布日|公开日)[^\d\n]*\s*\n*\s*(\d{4})[.\-年](\d{1,2})[.\-月]?(?:日)?[.\-]?(\d{1,2})",
        "ja": r"(?:出願日|公開日)[^\d\n]*\s*\n*\s*(\d{4})[.\-/年](\d{1,2})[.\-/月]?(?:日)?[.\-]?(\d{1,2})",
        # "ko": r"(?:출원일자|공고일자)[^\d\n]*\s*\n*(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
        "ko": r"(?:\(\s*\d+\s*\)\s*)?(?:출원일자|공고일자)[^\d\s]*\s*(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
        "en": r"(?:Publication Date|Date of publication):?\s*(\w+\s+\d{1,2},\s+\d{4})"
        # "EP": r"Date of publication\s*(\d{2}/\d{2}/\d{4})",
        # "WO": r"Publication Date\s*(\d{2} \w+ \d{4})"
    }

    pattern = patterns.get(lang_code)
    if pattern:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            if lang_code.upper() not in {"US", "EP", "WO"}:
                year, month, day = match.groups()
                return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                return match.group(1).strip()

    print(f"Warning: No publication date detected from searched pdf in {lang_code}!")
    return ""

def translate_offline_argos(text, from_lang="zh", to_lang="en"):
    installed_languages = argostranslate.translate.get_installed_languages()
    from_lang_obj = next((lang for lang in installed_languages if lang.code == from_lang), None)
    to_lang_obj = next((lang for lang in installed_languages if lang.code == to_lang), None)

    if from_lang_obj and to_lang_obj:
        translation = from_lang_obj.get_translation(to_lang_obj)
        return translation.translate(text)
    else:
        print("fallback!")
        return text  # fallback

def detect_language_basic(text):
    if '申请人' in text or "专利权人" in text:
        return 'zh'
    elif '出願人' in text:
        return 'ja'
    elif '출원인' in text:
        return 'ko'
    else:
        return 'en'    

# search_find_patentee("CN", "108378744", "A", "test_2_fsr")