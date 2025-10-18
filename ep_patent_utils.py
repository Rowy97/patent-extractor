import re
from nonpatent_utils import read_pdf_from

#citations info from the articles
def extract_ep_foa_citation(text):
    # Step 1: Split into individual entries based on known country + number prefix
    start_marker = "DOCUMENTS CONSIDERED TO BE RELEVANT"
    end_marker = "CATEGORY OF CITED DOCUMENTS"

    start_match = re.search(re.escape(start_marker), text)
    end_match = re.search(re.escape(end_marker), text)

    if start_match and end_match:
        clean_text = text[start_match.end():end_match.start()].strip()
    else:
        print("fuckkkkkkkkkk")
    entry_splits = re.split(r'(?=[A-Z]{2}\s+\d{3,4}(?:\s|/))', clean_text)

    # Step 2: Define a list to hold all extracted entries
    citation_data = []

    # Step 3: Process each entry individually
    for entry in entry_splits:
        entry = entry.strip()
        if not entry:
            continue

        # Extract basic metadata
        meta_match = re.search(
            r'(?P<country>[A-Z]{2})\s+(?P<number>(?:\d{4}/\d+|\d{3}(?:\s+\d{3})*))\s+(?P<kind>[A-Z1I]{1,2}\d?)',
            entry)
        
        if not meta_match:
            continue
        
        country = meta_match.group("country")
        patent_number = meta_match.group("number").replace(" ", "").replace("/", "")
        kind_code = meta_match.group("kind").replace("I", "1").upper()

        # Extract applicant
        # applicant_match = re.search(r'\(([^()]*?)\s*\[[A-Z]{2}\]\)', entry)
        applicant_match = re.search(r'\(([^()]+)\)', entry)
        applicant = applicant_match.group(1).strip() if applicant_match else ""
        clean_applicant = re.sub(r'\s*\[.*?\]', '', applicant)

        # Extract publication date in parentheses
        date_match = re.search(r'\((\d{4}-\d{2}-\d{2})\)', entry)
        pub_date = date_match.group(1) if date_match else ""

        # Extract relevant info (paragraphs, claims, figures), simplified
        # relevant_match = re.search(r'\*\s*(paragraphs?|claims?).*?(?=\*|TECHNICAL|$)', entry, re.DOTALL)
        relevant_match = re.search(
            r'(?:(?:paragraphs?|claims?|figures?)\s*[\[\(]?.*?[\]\)]?(?:\s*[,;_\-]?\s*)?)+(?=\*|TECHNICAL|$)',
            entry,
            re.DOTALL
        )
        relevant = relevant_match.group(0).strip(" *") if relevant_match else ""

        # Save the structured entry
        citation_data.append({
            "country_code": country,
            "patent_number": patent_number,
            "kind_code": kind_code,
            "applicant": clean_applicant,
            "publication_date": pub_date,
            "relevant": relevant
        })

    return citation_data
    
#article info: office name, patent number, filled date
def extract_ep_article_info(text):
    """
    Extract patent application number and (optional) filing date from European Office Action text.

    Returns:
        patent_no (str), filing_date (str in YYYY-MM-DD or empty if not found)
    """
    # Match EP application number format like: EP 19933584.5 or 19 93 3584 .5
    pattern = r"Application Number SUPPLEMENTARY EUROPEAN SEARCH REPORT\s+([A-Z]{2}(?:\s*\d+)+)"
    match = re.search(pattern, text)
    if match:
        p_no =  match.group(1).strip()
    else:
        print("Warning: application number is not detected!")
        p_no = ""

    # Match date format like 26.07.2022 or 15 July 2022
    date_pattern = r"Date\s+(\d{2})\.(\d{2})\.(\d{4})"
    date_match = re.search(date_pattern, text)
    if date_match:
        day, month, year = date_match.groups()
        filing_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    else:
        print("Warning: No filled date is detected!")
        filing_date = ""

    return p_no.replace(" ", ""), filing_date

# text, _ = read_pdf_from("test_3_foa/First Office Action of family patent EP3981541.pdf")
# print(extract_ep_foa_citation(text))