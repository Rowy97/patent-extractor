import re
from nonpatent_utils import month_map

def extract_jp_article_info(text):
    """
    Extract patent application no and filling date from the English translation of jp patent.

    return:
        patent_no, filling_date
    """

    app_match = re.search(r"Japanese Patent Application No[\._:\s]*\s*(\d{4}-\d+)", text)
    if app_match:
        p_no = app_match.group(1)
    else:
        print("Warning: No application number is detected!")
        p_no = ""

    date_match = re.search(r"Date of Drafting:\s*([A-Za-z]+\s+[A-Za-z]+)?\s*(\d+)?\(?(\d{4})\)?\s+([A-Za-z]+)\s+(\d{1,2})", text)
    if date_match:
        _, _, western_year, month_str, day = date_match.groups()
        
        #convert to YYYY-MM-DD
        month = month_map.get(month_str, '01')
        filling_date = f"{western_year}-{month}-{day.zfill(2)}"
    else:
        print("Warning: No filled date is detected!")
        filling_date = ""
    
    return p_no, filling_date

def normalize_digits(s):
    # Convert full-width to ASCII digits and remove internal spaces
    return s.replace(" ", "").translate(str.maketrans("０１２３４５６７８９", "0123456789"))

def extract_jp_foa_citation(text):
    kind_mapping = {
        "特許出願公開": "A",
        "実用新案": "U",
        "特許公報": "B",
        "意匠登録": "S",
    }

    country_mapping = {
        "中国": "CN",
        "日本": "JP",
        "韓国": "KR",
        "米国": "US",
        "欧州": "EP",
        "国際": "WO"
    }

    # Main pattern: allow full-width digits and spaces between them
    pattern = re.compile(
        r"(中国|日本|韓国|米国|欧州|国際)\s*"
        r"(特許出願公開|特許公報|実用新案|意匠登録)?\s*"
        r"第\s*((?:[0-9０-９]\s*)+?)号"
    )

    country_codes = []
    patent_numbers = []
    kind_codes = []

    for match in pattern.finditer(text):
        raw_country, kind_phrase, raw_number = match.groups()
        country_codes.append(country_mapping.get(raw_country, raw_country))
        patent_numbers.append(normalize_digits(raw_number))
        kind_codes.append(kind_mapping.get(kind_phrase, ""))

    # if len(country_codes) == 0:
    #     print("No JP-style citations detected!")

    return country_codes, patent_numbers, kind_codes