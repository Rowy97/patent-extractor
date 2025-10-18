from nonpatent_utils import foreign_code2name
import re

def extract_cn_foa(text, country_code):
    country_office = patent_no = date = ""
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
        print("patent_no is not detected from patent pdf")
        patent_no = ""
    return country_office, patent_no, date