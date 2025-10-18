import pandas as pd
import time
import os
from pdf2image import convert_from_path
from add_ids import add_non_patent_citation
from extract_utils import extract_isr_from_path, extract_foa_from_path, extract_fsr_from_path
from output_utils import output2Doc
from article_utils import article_info_from_path
from nonpatent_utils import nonpatent_articles, international_office_name, initial_df, read_pdf_from

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)  # Shows full text in each cell

#track the start time
start = time.perf_counter()

folder_path = "IDS-示例/P25JM1NW00126US-IDS"
#initialize all dfs under one folder
df_us, df_us_application, df_foreign, df_non_patent = initial_df()
#extract all articles that need to extract citations out in a list
articles = [v for v in nonpatent_articles.values()]
#loop through the path
for _,_, files in os.walk(folder_path):
    for file in files:
        if file.endswith("pdf") and "English Translation".lower() not in file.lower():
            print(file)
            if file.startswith(tuple(articles)):
                article = next((a for a in articles if file.startswith(a)), None)
                #filter the articles that need to extract citations
                # if article in file and "English Translation" not in file:
                #isr
                if article=="International Search Report":
                    print(f"is entering the {article}")
                    file_path = os.path.join(folder_path, file)
                    eng_ver = "English Translation of " + file
                    eng_path = os.path.join(folder_path, eng_ver)
                    # if there is english translation: 
                    if os.path.exists(eng_path):
                        print("with English translation")
                        eng_path = os.path.join(folder_path, eng_ver)
                        df_us, df_us_application, df_foreign, non_patent_info = extract_isr_from_path(eng_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign)
                        p_no, date = non_patent_info[0], non_patent_info[1]
                        eng_images = convert_from_path(eng_path, dpi=300)
                        en_pages = len(eng_images)
                        images = convert_from_path(file_path, dpi=300)
                        pages = len(images)
                        total_pages = en_pages + pages
                        if "Written Opinion" in files:
                            citation = f"{international_office_name}. International Search Report and Written Opinion for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                            df_non_patent = add_non_patent_citation(df_non_patent, citation)   
                        else:
                            citation = f"{international_office_name}. International Search Report for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                            df_non_patent = add_non_patent_citation(df_non_patent, citation)  
                    #there is no english translation
                    else:
                        print("without english translation")
                        file_path = os.path.join(folder_path, file)
                        df_us, df_us_application, df_foreign, non_patent_info = extract_isr_from_path(file_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign)
                        p_no, date = non_patent_info[0], non_patent_info[1]
                        images = convert_from_path(file_path, dpi=300)
                        pages = len(images)
                        total_pages = pages
                        if "Written Opinion" in files:
                            citation = f"{international_office_name}. International Search Report and Written Opinion for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                            df_non_patent = add_non_patent_citation(df_non_patent, citation)   
                        else:
                            citation = f"{international_office_name}. International Search Report for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                            df_non_patent = add_non_patent_citation(df_non_patent, citation)  

                #fsr usually for cn
                elif article == "First Search Report":
                    print(f"is entering the {article}")
                    eng_ver = "English Translation of " + file
                    eng_path = os.path.join(folder_path, eng_ver)
                    if os.path.exists(eng_path):
                        print("with english translation here")
                        file_path = os.path.join(folder_path, file)
                        df_us, df_us_application, df_foreign, non_patent_info = extract_fsr_from_path(eng_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign)
                        
                        p_no, date, en_pages, article_country = non_patent_info[0], non_patent_info[1], non_patent_info[2], non_patent_info[3]
                        images = convert_from_path(file_path, dpi=300)
                        pages = len(images)
                        total_pages = en_pages + pages
                        citation = f"{article_country}. First Search Report for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                    else:
                        print("without english translation")
                        file_path = os.path.join(folder_path, file)
                        df_us, df_us_application, df_foreign, non_patent_info = extract_fsr_from_path(file_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign)
                        p_no, date, pages, article_country = non_patent_info[0], non_patent_info[1], non_patent_info[2], non_patent_info[3]
                        total_pages = pages
                        citation = f"{article_country}. First Search Report for PCT Application no. {p_no}, mailed {date}. pages 1-{total_pages}."
                    df_non_patent = add_non_patent_citation(df_non_patent, citation)  

                #foa for non cn eg: kr, jp, wo, ep
                elif article == "First Office Action":
                    print(f"is entering the {article}")
                    eng_ver = "English Translation of " + file
                    eng_path = os.path.join(folder_path, eng_ver)
                    if os.path.exists(eng_path):
                        file_path = os.path.join(folder_path, file)
                        #file_path in foa to introduce country code
                        df_us, df_us_application, df_foreign, non_patent_info = extract_foa_from_path(eng_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign, 
                                                                                                file_path)
                        if len(non_patent_info) != 0:
                            patent_office, p_no, date = non_patent_info[0], non_patent_info[1], non_patent_info[2]
                        else:
                            patent_office = "None"
                            p_no = "None"
                            date = "None"
                        en_images = convert_from_path(eng_path, dpi=300)
                        en_pages = len(en_images)
                        images = convert_from_path(file_path, dpi=300)
                        pages = len(images)
                        total_pages = en_pages + pages
                        citation = f"{patent_office}. First Office Action for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                    else:
                        file_path = os.path.join(folder_path, file)
                        df_us, df_us_application, df_foreign, non_patent_info = extract_foa_from_path(file_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign)
                        patent_office, p_no, date = non_patent_info[0], non_patent_info[1], non_patent_info[2]
                        images = convert_from_path(file_path, dpi=300)
                        pages = len(images)
                        total_pages = pages
                        citation = f"{patent_office}. First Office Action for PCT Application no. {p_no}, mailed {date}. pages 1-{total_pages}."
                    df_non_patent = add_non_patent_citation(df_non_patent, citation)
                #supplimentary search
                elif article == "Supplementary Search":
                    print(f"is entering the {article}")
                    eng_ver = "English Translation of " + file
                    eng_path = os.path.join(folder_path, eng_ver)
                    if os.path.exists(eng_path):
                        file_path = os.path.join(folder_path, file)
                        #file_path in foa to introduce country code
                        df_us, df_us_application, df_foreign, non_patent_info = extract_foa_from_path(eng_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign, 
                                                                                                file_path)
                        patent_office, p_no, date = non_patent_info[0], non_patent_info[1], non_patent_info[2]
                        en_images = convert_from_path(eng_path, dpi=300)
                        en_pages = len(en_images)
                        images = convert_from_path(file_path, dpi=300)
                        pages = len(images)
                        total_pages = en_pages + pages
                        citation = f"{patent_office}. Supplementary Search for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                    else:
                        file_path = os.path.join(folder_path, file)
                        df_us, df_us_application, df_foreign, non_patent_info = extract_foa_from_path(file_path, 
                                                                                                df_us, 
                                                                                                df_us_application,
                                                                                                df_foreign)
                        patent_office, p_no, date = non_patent_info[0], non_patent_info[1], non_patent_info[2]
                        images = convert_from_path(file_path, dpi=300)
                        pages = len(images)
                        total_pages = pages
                        citation = f"{patent_office}. Supplementary Search for PCT Application no. {p_no}, mailed {date}. pages 1-{total_pages}."
                    df_non_patent = add_non_patent_citation(df_non_patent, citation)
            

            #for those articles that don't need to extract citations, only {p_no, maildate, pages}
            else:
                file_path = os.path.join(folder_path, file)
                #into the file that not the english translation
                if os.path.exists(file_path):
                    if "English Translation" not in file_path:
                        eng_ver = "English Translation of " + file
                        eng_path = os.path.join(folder_path, eng_ver)
                        #check if the engligh version exist
                        if os.path.exists(eng_path):
                            print(f"{file_path} is entering no citation English version section")
                            patent_office, p_no, date = article_info_from_path(file_path)
                            #count eng pages
                            en_images = convert_from_path(eng_path, dpi=300)
                            en_pages = len(en_images)
                            #count original pages
                            images = convert_from_path(file_path, dpi=300)
                            pages = len(images)
                            total_pages = en_pages + pages
                            #get article name from file: xxxx of pct xxx
                            article_name = file.split("of")[0]
                            citation = f"{patent_office}. {article_name} for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                        else:
                            print(f"{file_path} is entering no citation no English version section")
                            patent_office, p_no, date = article_info_from_path(file_path)
                            #count pages from file
                            images = convert_from_path(file_path, dpi=300)
                            pages = len(images)
                            total_pages = pages
                            #get article name from file
                            article_name = file.split("of")[0]
                            citation = f"{patent_office}. {article_name} for PCT Application no. {p_no} and English translation, mailed {date}. pages 1-{total_pages}."
                        df_non_patent = add_non_patent_citation(df_non_patent, citation)
                

#extract case_no from folder path
case_no = folder_path.split("/")[-1]
#remove duplicates from df
df_us_clean = df_us.drop_duplicates(subset=['Patent Number'])
df_us_application_clean = df_us_application.drop_duplicates(subset=['Patent Number'])
df_foreign_clean = df_foreign.drop_duplicates(subset=["Foreign Document Number³"])
df_non_patent_clean = df_non_patent.drop_duplicates(subset=["Include name of the author (in CAPITAL LETTERS), title of the article (when appropriate), title of the item (book, magazine, journal, serial, symposium, catalog, etc), date, pages(s), volume-issue number(s), publisher, city and/or country where published."])

#output to docx file
output2Doc(df_us_clean, df_us_application_clean, df_foreign_clean, df_non_patent, case_no=case_no)     

#track end time in minutes
end = time.perf_counter()
elapsed_minutes = (end - start) / 60
print("#########################################")
print(f"Time used: {elapsed_minutes:.2f} minutes")


