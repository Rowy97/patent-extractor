import pandas as pd

def add_us_citation(df, patent_number = "", kind_code= "", issue_date= "", patentee_name= "", relevant_info= ""):
    next_cite_no = len(df) + 1
    new_row = {
        "Cite No": next_cite_no,
        "Patent Number": patent_number,
        "Kind Code¹": kind_code,
        "issue Date": issue_date,
        "Name of Patentee or Applicant of cited Document": patentee_name,
        "Pages, Columns, Lines where Relevant Passages or Relevant Figures Appear": relevant_info
    }
    
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

def add_us_app_citation(df, patent_number= "", kind_code= "", publication_date= "", patentee_name= "", relevant_info= ""):
    next_cite_no = len(df) + 1
    new_row = {
        "Cite No": next_cite_no,
        "Patent Number": patent_number,
        "Kind Code¹": kind_code,
        "Publication Date": publication_date,
        "Name of Patentee or Applicant of cited Document": patentee_name,
        "Pages, Columns, Lines where Relevant Passages or Relevant Figures Appear": relevant_info
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

def add_foreign_citation(df, doc_number= "", country_code= "", kind_code= "", pub_date= "", patentee_name= "", relevant_info= ""):
    next_cite_no = len(df) + 1
    new_row = {
        "Cite No": next_cite_no,
        "Foreign Document Number³": doc_number,
        "Country Code²": country_code,
        "Kind Code⁴": kind_code,
        "Publication Date": pub_date,
        "Name of Patentee or Applicant of cited Document": patentee_name,
        "Pages, Columns, Lines where Relevant Passages or Relevant Figures Appear": relevant_info
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

def add_non_patent_citation(df, new_content):
    # Get next cite number
    next_cite_no = len(df) + 1
    new_row = {
        "Cite No": next_cite_no,
        "Include name of the author (in CAPITAL LETTERS), title of the article (when appropriate), title of the item (book, magazine, journal, serial, symposium, catalog, etc), date, pages(s), volume-issue number(s), publisher, city and/or country where published.": new_content
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)