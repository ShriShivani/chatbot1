import pytesseract
from pdf2image import convert_from_bytes
import re
from PIL import Image

def parse_resume_from_bytes(pdf_bytes):
    """
    Extracts structured data from resume PDF (bytes format).
    Returns dict with text, skills, education, experience, etc.
    """
    try:
        images = convert_from_bytes(pdf_bytes)
        extracted_text = ""

        for image in images:
            text = pytesseract.image_to_string(image)
            extracted_text += text + "\n"

        # Skills
        skills = re.findall(
            r'\b(Python|Java|SQL|Machine Learning|Data|Engineer|Developer|AI|Marketing|Sales|Excel|React|Node|Frontend|Backend|Flask|Django|AWS|Cloud|PostgreSQL|MongoDB|UI|UX|Design|Testing|C\+\+|C|Leadership|Teamwork|Communication)\b',
            extracted_text, re.IGNORECASE)
        skills = list(set(skill.lower() for skill in skills))

        # Education
        education_patterns = [
            r'(?i)(?:B\.?Tech|Bachelor of Technology|B\.?E\.?|Bachelor of Engineering)[\s\w]*?(?:20\d{2})',
            r'(?i)(?:M\.?Tech|Master of Technology|M\.?E\.?|Master of Engineering)[\s\w]*?(?:20\d{2})',
            r'(?i)(?:B\.?A\.?|Bachelor of Arts)[\s\w]*?(?:20\d{2})',
            r'(?i)(?:M\.?A\.?|Master of Arts)[\s\w]*?(?:20\d{2})',
            r'(?i)(?:B\.?Sc\.?|Bachelor of Science)[\s\w]*?(?:20\d{2})',
            r'(?i)(?:M\.?Sc\.?|Master of Science)[\s\w]*?(?:20\d{2})',
            r'(?i)(?:Ph\.?D\.?|Doctor of Philosophy)[\s\w]*?(?:20\d{2})'
        ]
        education = []
        for pattern in education_patterns:
            matches = re.findall(pattern, extracted_text)
            education.extend(matches)

        # Experience
        exp_match = re.search(r'(?:(\d+)(?:\+)?\s*(?:years?|yrs?)(?:\s*of)?(?:\s*experience)?)', extracted_text, re.IGNORECASE)
        experience = exp_match.group(1) if exp_match else "Not specified"

        return {
            "text": extracted_text,
            "skills": skills,
            "education": education[:3] or ["Not detected"],
            "experience_years": experience
        }

    except Exception as e:
        print("❌ Error parsing resume:", e)
        return {
            "text": "",
            "skills": [],
            "education": ["Not detected"],
            "experience_years": "Unknown"
        }
