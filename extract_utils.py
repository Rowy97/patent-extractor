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
import camelot
from datetime import datetime
from pdf2image import convert_from_path
from add_ids import add_foreign_citation, add_us_app_citation, add_us_citation
from nonpatent_utils import foreign_code2name, read_pdf_from, initial_df, _cleanup_pil_images
from search_pdf_utils import search_find_patentee
from jp_patent_utils import extract_jp_article_info, extract_jp_foa_citation
from kr_patent_utils import extract_kr_article_info, extract_kr_foa_citation
from ep_patent_utils import extract_ep_article_info, extract_ep_foa_citation
from cn_patent_utils import extract_cn_foa
import warnings
from cryptography.utils import CryptographyDeprecationWarning
from argo_translate import install_argos_packages

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)  # Shows full text in each cell

############ RUN FIRST TIME #################
#install argos packages to local
install_argos_packages()
#############################################

# smaller functions
def extract_fsr(text, tables, pdf_path):
    """
    return:
        df_patent: (pd.dataframe) {country_code: "", patent_number:"", kind_code:"", publication_date:"", applicant:"", relevant:""}
        non_patent_info_list: (list) [p_no, filing_date]
    """
    # Initialize empty DataFrame with expected columns
    df_patent = pd.DataFrame(columns=[
        "country_code", "patent_number", "kind_code",
        "publication_date", "applicant", "relevant"
    ])

    # Extract filing date at the very end of the text
    filing_date = None
    application_number = ""
    match = re.search(r'([A-Za-z]{3,9}) (\d{1,2})(?:st|nd|rd|th),\s*(\d{4})\s*$', text.strip())
    if match:
        month = match.group(1)
        day = match.group(2)
        year = match.group(3)
        try:
            filing_date = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date()
        except ValueError:
            try:
                filing_date = datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()
            except ValueError:
                filing_date = None

    #extract table data
    for table in tables:
        df = table.df
        if df.shape[1] == 6: 
            for _, row in df.iterrows():
                entry = row.tolist()
                if entry[0] in {"X", "Y", "A", "R", "P", "E", "T", "L"}:
                    m = re.match(r"([A-Z]{2})(\d+)([A-Z]\d?)$", entry[1]) #entry[1] is the raw patent no: country code + patent_no + kind code
                    df_patent.loc[len(df_patent)] = {
                                                        "country_code": m.group(1),
                                                        "patent_number": m.group(2),
                                                        "kind_code": m.group(3),
                                                        "publication_date": entry[2],                                        #the root path of the pdf
                                                        "applicant": search_find_patentee(m.group(1), m.group(2), m.group(3), os.path.join(*pdf_path.split("/")[:-1])),
                                                        "relevant": entry[4].replace("\n", "")
                                                    }

        else:
            for _, row in df.iterrows():
                entry = row.tolist()
                entry[0].replace("\n", " ")
                if entry[0].startswith("Application Number"):
                    parts = entry[0].split("Application Number:")
                    if len(parts) > 1:
                        application_number = parts[1].strip()
                    else:
                        print("ERROR: application number not found!")

            if application_number == "":
                print("ERROR: application number not detected!")

    #put non_patent_info_list together
    filled_date = str(filing_date) if filing_date else "" 
    non_patent_info_list = [application_number, filled_date]

    return df_patent, non_patent_info_list   

def extract_foa(text_eng, text_ori, country_code, pdf_path):
    """
    return:
        df_patent: (pd.dataframe) {country_code: "", patent_number:"", kind_code:"", publication_date:"", applicant:"", relevant:""}
        non_patent_info_list: (list) [p_no, filing_date]
    """
    # Initialize empty DataFrame with expected columns
    df_patent = pd.DataFrame(columns=[
        "country_code", "patent_number", "kind_code",
        "publication_date", "applicant", "relevant"
    ])
    # Initialize non patent info list as empthy
    non_patent_info_list = []
    # cn foa: doesn't need to extract any info; only required non-patent info: info
    if country_code == "JP":
        try:
            c_code, patent_no, kind_code = extract_jp_foa_citation(text_ori) #c_code stands for citation country code 
        except Exception as e:
            print(f"Error extracting JP citations: {e}")
            c_code, patent_no, kind_code = [], [], []
        relevant = "" # relevant is empty
        #search the missing patentee and application date for each citation
        if len(c_code) == 0:
            print(f"No {country_code} citations detected!")
        else:
            for c, p, k in zip(c_code, patent_no, kind_code):
                try:
                    applicant, publication_date = search_find_patentee(c, p, k, rootpath = pdf_path.split("/")[0], find_date=True)
                except Exception as e:
                    print(f"Error searching patentee for {c} {p} {k}: {e}")
                    applicant, publication_date = "", ""
                df_patent.loc[len(df_patent)] = {
                                                    "country_code": c,
                                                    "patent_number": p,
                                                    "kind_code": k,
                                                    "publication_date": publication_date,
                                                    "applicant": applicant,
                                                    "relevant": relevant
                                                }
        #Extract the patent office info from the foa article; this is only based on the foa
        patent_office = foreign_code2name[country_code]
        try:
            p_no, filing_date = extract_jp_article_info(text_eng)
        except Exception as e:
            print(f"Error extracting JP article info: {e}")
            p_no, filing_date = "", ""
        non_patent_info_list = [patent_office, p_no, filing_date]
    
    elif country_code == "KR":
        try:
            c_code, patent_no, kind_code = extract_kr_foa_citation(text_ori) #c_code stands for citation country code 
        except Exception as e:
            print(f"Error extracting KR citations: {e}")
            c_code, patent_no, kind_code = [], [], []
        relevant = "" # relevant is empty
        #search the missing patentee and application date for each citation
        if len(c_code) == 0:
            print(f"No {country_code} citations detected!")
        else:
            for c, p, k in zip(c_code, patent_no, kind_code):
                try:
                    applicant, publication_date = search_find_patentee(c, p, k, rootpath = pdf_path.split("/")[0], find_date=True)
                except Exception as e:
                    print(f"Error searching patentee for {c} {p} {k}: {e}")
                    applicant, publication_date = "", ""
                df_patent.loc[len(df_patent)] = {
                                                    "country_code": c,
                                                    "patent_number": p,
                                                    "kind_code": k,
                                                    "publication_date": publication_date,
                                                    "applicant": applicant,
                                                    "relevant": relevant
                                                }
        #Extract the patent office info from the foa article; this is only based on the foa
        patent_office = foreign_code2name[country_code]
        p_no, filing_date = extract_kr_article_info(text_ori)
        non_patent_info_list = [patent_office, p_no, filing_date]

    elif country_code == "EP":
        try:
            citations = extract_ep_foa_citation(text_ori)  # A list of dictionary
        except Exception as e:
            print(f"Error extracting EP citations: {e}")
            citations = []

        if len(citations) == 0:
            print(f"No {country_code} citations detected!")
        else:
            #read dictionary one by one
            df_new = pd.DataFrame(citations)
            df_patent = pd.concat([df_new, df_patent], ignore_index=True)
        #Extract the patent office info from the foa article; this is only based on the foa
        patent_office = foreign_code2name[country_code]
        p_no, filing_date = extract_ep_article_info(text_ori)
        non_patent_info_list = [patent_office, p_no, filing_date]
    
    elif country_code == "CN":
        try:
            patent_office, p_no, filing_date = extract_cn_foa(text_ori, country_code)
        except Exception as e:
            print(f"Error extracting CN FOA info: {e}")
            patent_office, p_no, filing_date = "", "", ""
        non_patent_info_list = [patent_office, p_no, filing_date]
    
    return df_patent, non_patent_info_list

def extract_patents(text):
    # Normalize spacing and common OCR issues
    text = text.replace("\n", " ").replace("  ", " ")
    text = re.sub(r"([A-Z])\s+([0-9]{6,})", r"\1 \2", text)  # CN123456789 fix
    text = re.sub(r"([0-9]{4})\s+([A-Z]{2,})", r"\1 \2", text)  # 2023 CN
    text = text.replace("Al", "A1").replace(",,", ",").replace(":", "")
    text = text.replace("20023", "2023")

    pattern = re.compile(
        r"(?P<country_code>[A-Z]{2})\s*"
        r"(?P<patent_number>\d{6,})\s+"
        r"(?P<kind_code>[A-Z]\d?)?\s*"
        r"\((?P<applicant>[^)]*?\([^)]*?\)[^)]*?|[^)]*?)\)\s+"
        r"(?P<pub_date>\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+"
        r"\((?P<publication_date>\d{4}-\d{2}-\d{2})\)\s*"
        r"(?P<relevant>entire document|description.*?(?:paragraphs\s*\d+-\d+,?\s*)?(?:and\s*)?figures\s*\d+-\d+)",
        re.IGNORECASE
    )

    pattern_date = r"Date of mailing of the international search\s+\w+[\s:]*([\d]{1,2} [A-Za-z]+ \d{4})\s+([\d]{1,2} [A-Za-z]+ \d{4})"
    match_date = re.search(pattern_date, text)
    if match_date:
        mailedDate = match_date.group(2)
    else:
        mailedDate = ""
        print("mailed Date missed!")

    pattern_pct = r"International application No[_:\s]*PCT/?([A-Z]{2,3})(\d{4})/(\d+)"
    match_pct = re.search(pattern_pct, text)

    if match_pct:
        pct_no = f"PCT/{match_pct.group(1)}{match_pct.group(2)}/{match_pct.group(3)}"
    else:
        pct_no = ""
        print("pct no not detected!")

    non_patent_output = [pct_no, mailedDate]

    matches = []
    for m in pattern.finditer(text):
        data = m.groupdict()
        matches.append(data)

    return pd.DataFrame(matches), non_patent_output     

# bigger functions
def extract_isr_from_path(pdf_path, df_us, df_us_application, df_foreign):
    """
    input:
        pdf_path (str)
        df_us (pd.df)
        df_us_application (pd.df)
        df_foreign (pd.df)
    output:
        df_us (pd.df)
        df_us_application (pd.df)
        df_foreign (pd.df)
        non_patent_info_list (list): [patent_no, filled_Date, num_pages]
    """
    # PDF to image
    # pdf_path = "P23SZ1NW00476US-IDS/IDS-nonpatent/English Translation of the ISR.pdf"
    images = convert_from_path(pdf_path, dpi=300,poppler_path=POPPLER_DIR)

    # Initialize EasyOCR
    reader = easyocr.Reader(['en'])

    # Extract text from each page
    full_text = ""
    for img in images:
        try:
            img_np = np.array(img)  # Convert PIL image to NumPy array
            results = reader.readtext(img_np, detail=0, paragraph=True)
            # print(results)
            page_text = " ".join(results)
            full_text += page_text + "\n"
        finally:
            img.close()

    df_patent, non_patent_info_list = extract_patents(full_text) #df_patent is a df, non_patent_output is a list

    for row in df_patent.itertuples(index=True):
        if row.country_code == "US":
            pattern = r"^[A-Z]\d$"
            if re.fullmatch(pattern, row.kind_code):
                df_us_application = add_us_app_citation(df_us_application, 
                                    patent_number=row.patent_number,
                                    kind_code=row.kind_code,
                                    publication_date = row.publication_date,
                                    patentee_name=row.applicant,
                                    relevant_info = row.relevant
                                    )
            else:
                df_us = add_us_citation(df_us, 
                                patent_number=row.patent_number,
                                kind_code=row.kind_code,
                                issue_date = row.publication_date,
                                patentee_name=row.applicant,
                                relevant_info = row.relevant
                                )
        else:
            df_foreign = add_foreign_citation(df_foreign, 
                                doc_number=row.patent_number,
                                country_code=row.country_code,
                                kind_code=row.kind_code,
                                pub_date = row.publication_date,
                                patentee_name=row.applicant,
                                relevant_info = row.relevant)
    return df_us, df_us_application, df_foreign, non_patent_info_list  

def extract_fsr_from_path(pdf_path, df_us, df_us_application, df_foreign):
    """
    input:
        pdf_path (str)
        df_us (pd.df)
        df_us_application (pd.df)
        df_foreign (pd.df)
    output:
        df_us (pd.df)
        df_us_application (pd.df)
        df_foreign (pd.df)
        non_patent_info_list (list): [patent_no, filled_Date, num_pages, ** country of article ** ]
    """
    # PDF to image
    images = convert_from_path(pdf_path, dpi=600, poppler_path=POPPLER_DIR)

    # Initialize EasyOCR
    reader = easyocr.Reader(['en'])
    # tables from camelot
    tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
    # Extract text from each page
    full_text = ""
    for img in images:
        try:
            img_np = np.array(img)  # Convert PIL image to NumPy array
            results = reader.readtext(img_np, detail=0, paragraph=True)
            # print(results)
            page_text = " ".join(results)
            full_text += page_text + "\n"
        finally:
                img.close()

    df_patent, non_patent_info_list = extract_fsr(full_text, tables, pdf_path) #df_patent is a df, non_patent_output is a list

    #Add pages into non patent info list
    pages = len(images) #extract number of pages from the pdf
    non_patent_info_list.append(pages) #update the non_patent_info: [p_no, filled date, n_pages]
    country_code = pdf_path.split(" ")[-1].split(".")[0][:2] #extract country code from pdf_path
    non_patent_info_list.append(foreign_code2name[country_code])#[p_no, filled date, pages, patent country name]

    #df_patent columns: country_code, patent_number, kind_code, publication_date, applicant, relevant
    for row in df_patent.itertuples(index=True):
        if row.country_code == "US":
            pattern = r"^[A-Z]\d$"
            if re.fullmatch(pattern, row.kind_code):
                df_us_application = add_us_app_citation(df_us_application, 
                                    patent_number=row.patent_number,
                                    kind_code=row.kind_code,
                                    publication_date = row.publication_date,
                                    patentee_name=row.applicant,
                                    relevant_info = row.relevant
                                    )
            else:
                df_us = add_us_citation(df_us, 
                                patent_number=row.patent_number,
                                kind_code=row.kind_code,
                                issue_date = row.publication_date,
                                patentee_name=row.applicant,
                                relevant_info = row.relevant
                                )
        else:
            df_foreign = add_foreign_citation(df_foreign, 
                                doc_number=row.patent_number,
                                country_code=row.country_code,
                                kind_code=row.kind_code,
                                pub_date = row.publication_date,
                                patentee_name=row.applicant,
                                relevant_info = row.relevant)
    return df_us, df_us_application, df_foreign, non_patent_info_list  

def extract_foa_from_path(pdf_path, df_us, df_us_application, df_foreign, ori_pdf_path=None):
    """
    input:
        pdf_path (str)
        df_us (pd.df)
        df_us_application (pd.df)
        df_foreign (pd.df)
    output:
        df_us (pd.df)
        df_us_application (pd.df)
        df_foreign (pd.df)
        non_patent_info_list (list): [patent_no, filled_Date, num_pages, ** country of article ** ]
    """
    # PDF to image
    if ori_pdf_path is not None:
        try:
            ori_text, country_code = read_pdf_from(ori_pdf_path)
            eng_text, country_code = read_pdf_from(pdf_path, False)
        except Exception as e:
            print(f"Error reading FOA files: {e}")
            return df_us, df_us_application, df_foreign, []
    else:
        #no english version, then ori and eng all equal to the ori text -> ep
        try:
            eng_text, country_code = read_pdf_from(pdf_path, False)
        except Exception as e:
            print(f"Error reading European FOA file: {e}")
            return df_us, df_us_application, df_foreign, []
        if country_code == "JP" or country_code == "KR":
            print("Wrong for jp and kr")
        ori_text = eng_text
        ori_pdf_path = pdf_path

    # country_code = pdf_path.split(" ")[-1].split(".")[0][:2] #extract country code from pdf_path
    df_patent, non_patent_info_list = extract_foa(eng_text, ori_text, country_code, ori_pdf_path) #df_patent is a df, non_patent_output is a list

    for row in df_patent.itertuples(index=True):
        if row.country_code == "US":
            pattern = r"^[A-Z]\d$"
            if re.fullmatch(pattern, row.kind_code):
                df_us_application = add_us_app_citation(df_us_application, 
                                    patent_number=row.patent_number,
                                    kind_code=row.kind_code,
                                    publication_date = row.publication_date,
                                    patentee_name=row.applicant,
                                    relevant_info = row.relevant
                                    )
            else:
                df_us = add_us_citation(df_us, 
                                patent_number=row.patent_number,
                                kind_code=row.kind_code,
                                issue_date = row.publication_date,
                                patentee_name=row.applicant,
                                relevant_info = row.relevant
                                )
        else:
            df_foreign = add_foreign_citation(df_foreign, 
                                doc_number=row.patent_number,
                                country_code=row.country_code,
                                kind_code=row.kind_code,
                                pub_date = row.publication_date,
                                patentee_name=row.applicant,
                                relevant_info = row.relevant)
    return df_us, df_us_application, df_foreign, non_patent_info_list  

# df_us, df_us_app, df_foreign, df_nonpatent = initial_df()
# df1, df2, df3, list4 = extract_foa_from_path("IDS-示例/P22FS1NW00011US-IDS/First Office Action of family patent CN114056749A.pdf",
#                      df_us,
#                      df_us_app,
#                      df_foreign,
#                      "IDS-示例/P22FS1NW00011US-IDS/English Translation of First Office Action of family patent CN114056749A.pdf"
#                      )
# print(df1, df2, df3)
# print(list4)
