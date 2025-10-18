from nonpatent_utils import read_pdf_from, foreign_code2name
import re
import os


def article_info_from_path(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}, skipping...")
        return None, None, None  # skip to next file
    else:
        file_name = os.path.basename(pdf_path)

    try:
        text, country_code = read_pdf_from(pdf_path)
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}, skipping...")
        return None, None, None

    country_office = patent_no = date = ""
    if country_code == "CN":
        country_office = foreign_code2name[country_code]
        m_date = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日月]", text)
        if m_date:
            y, mo, d = m_date.groups()
            date = f"{y}-{int(mo):02d}-{int(d):02d}"   # force the correct ‘日’ ending
        else:
            print("date is not detected from patent pdf")
            date = ""

        # --- Patent No.: allow optional spaces between Chinese chars & both ':'/ '：' ---
        m_no = re.search(r"(申\s*请\s*号\s*或\s*专\s*利\s*号)\s*[:：]\s*([0-9A-Za-z.\-]+)", text)
        if m_no:
            _, num = m_no.groups()
            patent_no = f"{num}"
        else:
            PATENT_RE = re.compile(
                r'\b([A-Z]{2})\s*[-_ ]?\s*(\d{6,}(?:\.\d+)?)(?:\s*[-_ ]?\s*([A-Z]\d))?\b'
                #  ^country^^ sep? ^^^^^^^ number ^^^^^^^^  ^ optional sep ^  ^kind A1^
            )
            m = PATENT_RE.search(file_name)
            if m:
                patent_no = str("PCT")+str(''.join(m.groups()))
            else:
                print("patent_no is not detected from filename")
                patent_no = ""

    return country_office, patent_no, date

