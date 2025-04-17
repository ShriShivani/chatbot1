import PyPDF2 
import re
import json
import os

def extract_text_from_pdf(file_path):
    """
    Extracts text from a PDF using PyPDF2.
    """
    text = ""
    with open(file_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    return text

def extract_skills_and_titles(text):
    keywords = re.findall(r'\b(Python|Java|SQL|Machine Learning|Data|Engineer|Developer|AI|Marketing|Sales|Excel|React|Node|Frontend|Backend|Flask|Django|AWS|Cloud|PostgreSQL|MongoDB|UI|UX|Design|Testing|C\+\+|C|Leadership|Teamwork|Communication)\b', text, re.IGNORECASE)

    return list(set(keyword.lower() for keyword in keywords))

def suggest_jobs_from_text(resume_text, job_data):
    resume_keywords = extract_skills_and_titles(resume_text)
    matched_jobs = []

    for job in job_data:
        job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()
        if any(keyword in job_text for keyword in resume_keywords):
            matched_jobs.append(job)

    return matched_jobs