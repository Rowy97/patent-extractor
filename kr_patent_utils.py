import re

def extract_kr_article_info(text):
    """
    Extract patent application number and filing date from Korean Office Action text.

    Returns:
        patent_no (str), filing_date (str in YYYY-MM-DD)
    """

    # Match 10-2022-7038959 or 10--2022-7038959 with optional hyphen duplication
    app_match = re.search(r"출\s*원\s*번\s*호\s*[:：]?\s*(10[-–]{1,2}\d{4}[-–]?\d+)", text)
    if app_match:
        p_no = app_match.group(1).replace("–", "-").replace("--", "-")
    else:
        print("Warning: No application number is detected!")
        p_no = ""

    # Match filing date in formats like 2022.11.07 or 2022-11-07
    date_match = re.search(r"출\s*원\s*일\s*자\s*[:：]?\s*(\d{4})[.\-년]\s*(\d{1,2})[.\-월]?\s*(\d{1,2})[.\-일]?", text)
    if date_match:
        year, month, day = date_match.groups()
        filing_date = f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
    else:
        print("Warning: No filing date is detected!")
        filing_date = ""

    return p_no, filing_date


def normalize_digits(s):
    return s.replace(" ", "").translate(str.maketrans("０１２３４５６７８９", "0123456789"))

def extract_kr_foa_citation(text):
    """
    Extract Korean FOA-style patent citations: country, number, kind code.
    Returns:
        - country_codes: list of "KR"
        - patent_numbers: list of numbers like "10-1869042"
        - kind_codes: list of kind codes: A, B, U
    """
    kind_mapping = {
        "등록특허공보": "B",
        "공개특허공보": "A",
        "공개실용신안공보": "U"
    }

    pattern = re.compile(
        r"(등록특허공보|공개특허공보|공개실용신안공보)\s*제\s*([0-9０-９\-–]+)호"
    )

    country_codes = []
    patent_numbers = []
    kind_codes = []

    for match in pattern.finditer(text):
        kind_kor, raw_number = match.groups()
        country_codes.append("KR")
        patent_numbers.append(normalize_digits(raw_number.replace("–", "-")))
        kind_codes.append(kind_mapping.get(kind_kor, ""))

    # if not country_codes:
    #     print("No KR-style citations detected!")

    return country_codes, patent_numbers, kind_codes