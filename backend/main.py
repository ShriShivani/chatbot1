from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, EmailStr
import os
import requests
import re
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import firebase_admin
from firebase_admin import credentials
from db import get_collection  # Import MongoDB collection function

# Resume upload dependencies
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import tempfile
from bson import ObjectId  # 👈 Required for handling MongoDB ObjectId

# Load environment variables
load_dotenv()
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_API_KEY")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# Firebase Admin SDK
try:
    cred_path = os.path.join(os.path.dirname(__file__), "firebase_config.json")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
except Exception as e:
    print("⚠ Firebase initialization failed:", str(e))

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize chatbot model (text2text generation)
chatbot_pipeline = pipeline("text2text-generation", model="google/flan-t5-small")

# MongoDB - Fetch 'resumes' collection from the database
resumes_collection = get_collection('resumes')

class ChatRequest(BaseModel):
    message: str

class UserAuthRequest(BaseModel):
    email: EmailStr
    password: str

@app.post("/signup")
def signup_user(user: UserAuthRequest):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {"email": user.email, "password": user.password, "returnSecureToken": True}
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        return {"message": "✅ User created successfully", "data": res.json()}
    except requests.exceptions.HTTPError as e:
        return HTTPException(status_code=res.status_code, detail=res.json().get("error", {}).get("message", "Unknown error"))

@app.post("/login")
def login_user(user: UserAuthRequest):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": user.email, "password": user.password, "returnSecureToken": True}
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        return {"message": "✅ Login successful", "data": res.json()}
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=res.status_code, detail=res.json().get("error", {}).get("message", "Unknown error"))

def extract_job_details(message):
    match = re.search(r'find (.+?) jobs in (.+)', message, re.IGNORECASE)
    if match:
        job_title, location = match.groups()
        return f"{job_title.strip()} jobs in {location.strip()}"
    return message

def get_job_listings(query):
    if not JSEARCH_API_KEY:
        return "🚫 JSearch API key is missing."

    query = extract_job_details(query)
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": JSEARCH_API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    params = {"query": query, "page": "1"}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        jobs = response.json().get("data", [])
        if not jobs:
            return "⚠ No jobs found for your query."
        return "\n\n".join([
            f"✅ {job['job_title']} at {job['employer_name']} ({job.get('location', 'Location not specified')})"
            for job in jobs[:5]
        ])
    except Exception as e:
        return f"❌ Error fetching jobs: {str(e)}"

def get_events():
    if not EVENTBRITE_API_KEY:
        return "🚫 Eventbrite API key is missing."
    url = "https://www.eventbriteapi.com/v3/events/search/"
    headers = {"Authorization": f"Bearer {EVENTBRITE_API_KEY}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        events = response.json().get("events", [])
        if not events:
            return "⚠ No events found."
        return "\n\n".join([
            f"🎉 {event['name']['text']}" for event in events[:5]
        ])
    except Exception as e:
        return f"❌ Error fetching events: {str(e)}"

def chatbot_response(user_input):
    response = chatbot_pipeline(user_input, max_length=100)
    return response[0]['generated_text']

thank_you_variants = ["thank you", "thanks", "thanks a lot", "ty", "thx", "thankyou"]
irrelevant_keywords = [
    "recipe", "cooking", "cook", "sambar", "food", "dish", "biryani", "movie", "film", "actor",
    "actress", "celebrity", "cricket", "football", "IPL", "TV show", "series", "gossip", "music",
    "song", "lyrics", "weather", "temperature", "cold", "hot", "rain", "marriage", "wedding",
    "love", "boyfriend", "girlfriend", "crush", "pet", "dog", "cat", "shopping", "dress",
    "makeup", "skincare", "hair", "fitness", "gym", "weight loss", "horoscope", "zodiac", "astrology",
    "festival", "holiday", "vacation", "travel", "trip", "game", "video game", "YouTube", "TikTok",
    "Instagram", "Snapchat", "Facebook", "reels", "memes"
]

def is_thank_you(message):
    return any(thank in message.lower() for thank in thank_you_variants)

def is_irrelevant(message):
    return any(word in message.lower() for word in irrelevant_keywords)

def is_relevant_topic(message):
    topics = ["job", "career", "event", "session", "mentorship", "networking", "growth", "women", "empowerment"]
    return any(topic in message.lower() for topic in topics)

def is_how_are_you(message):
    how_phrases = ["how are you", "how r you", "how are u", "how r u"]
    return any(phrase in message.lower() for phrase in how_phrases)

@app.post("/chat")
def chatbot_api(request: ChatRequest):
    user_message = request.message.strip().lower()

    if is_thank_you(user_message):
        return {"reply": "You're welcome! 😊 I'm here to support you with women careers, jobs, mentorship, and events!"}
    if is_how_are_you(user_message):
        return {"reply": "I'm good, thanks for asking! 😊 Let me know how I can help you with your career or job search today."}
    if is_irrelevant(user_message):
        return {"reply": "🙏 Please ask relevant questions about careers, jobs, mentorship, or events focused on women empowerment."}
    if "job" in user_message:
        return {"reply": get_job_listings(user_message)}
    if "event" in user_message or "session" in user_message:
        return {"reply": get_events()}
    if is_relevant_topic(user_message):
        return {"reply": chatbot_response(user_message)}
    return {"reply": "I'm Asha, an AI assistant focused on women careers, mentorship, and empowerment. Please ask me about job listings, career guidance, events, or professional growth!"}

@app.get("/chat")
def chat(message: str):
    return {"reply": chatbot_response(message)}

@app.get("/")
def home():
    return {"message": "✅ Asha AI Chatbot Backend is running!"}

# -------------------- ✅ Resume Upload Endpoint -------------------- #
@app.post("/upload-resume/")
async def upload_resume(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        images = convert_from_bytes(pdf_bytes)

        extracted_text = ""
        for image in images:
            text = pytesseract.image_to_string(image)
            extracted_text += text + "\n"

        keywords = ["python", "java", "sql", "ml", "ai", "marketing", "data", "frontend", "backend"]
        matches = [word for word in keywords if word.lower() in extracted_text.lower()]

        resume_data = {
            "file_name": file.filename,
            "extracted_text": extracted_text,
            "skills_detected": list(set(matches)),
        }

        result = resumes_collection.insert_one(resume_data)
        return {
            "message": "✅ Resume processed and saved.",
            "skills_detected": list(set(matches)),
            "summary": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "resume_id": str(result.inserted_id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error processing resume: {str(e)}")

# -------------------- ✅ Get All Resumes -------------------- #
@app.get("/resumes/")
def get_resumes():
    try:
        resumes = list(resumes_collection.find())
        for r in resumes:
            r["_id"] = str(r["_id"])  # Convert ObjectId to string for JSON
        return {"resumes": resumes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error fetching resumes: {str(e)}")

# -------------------- ✅ Get Resume by ID -------------------- #
@app.get("/resumes/{resume_id}")
def get_resume_by_id(resume_id: str):
    try:
        resume = resumes_collection.find_one({"_id": ObjectId(resume_id)})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found.")
        resume["_id"] = str(resume["_id"])  # Convert for JSON response
        return {"resume": resume}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error fetching resume: {str(e)}")
    

