from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import os
import requests
import re
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import firebase_admin
from firebase_admin import credentials

# Load environment variables
load_dotenv()
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_API_KEY")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# Initialize Firebase Admin SDK
try:
    cred_path = os.path.join(os.path.dirname(__file__), "firebase-config.json")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
except Exception as e:
    print("⚠ Firebase initialization failed:", str(e))

# Initialize FastAPI app
app = FastAPI()

# Enable CORS (allow all for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hugging Face FLAN-T5 model
chatbot_pipeline = pipeline("text2text-generation", model="google/flan-t5-small")

# -------------------- Pydantic Models -------------------- #
class ChatRequest(BaseModel):
    message: str

class UserAuthRequest(BaseModel):
    email: EmailStr
    password: str

# -------------------- Auth Endpoints -------------------- #
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
        return HTTPException(status_code=res.status_code, detail=res.json().get("error", {}).get("message", "Unknown error"))

# -------------------- Helper Functions -------------------- #
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
            f"✅ *{job['job_title']}* at {job['employer_name']} ({job.get('location', 'Location not specified')})"
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
    response_map = {
        "hi": "Hello! How can I support your career today?",
        "hello": "Hi there! Looking for job listings or mentorship?",
        "how are you": "I'm great! Ready to assist with your career goals.",
        "what is a resume": "A resume is a summary of your education, work experience, skills, and achievements used to apply for jobs.",
        "what is a cover letter": "A cover letter is a personalized letter that accompanies your resume, introducing yourself to employers and explaining why you're a good fit for the position.",
        "how to write a resume": "Start with contact info, then add a summary, work experience, education, and skills. Keep it clear and concise.",
        "how to prepare for interview": "Research the company, practice common questions, dress professionally, and be confident.",
        "what is python": "Python is a popular, beginner-friendly programming language used in web development, data science, automation, and more.",
        "what is machine learning": "Machine learning is a field of AI where computers learn from data without being explicitly programmed.",
        "what is data science": "Data science involves analyzing large sets of data to extract meaningful insights using statistics, programming, and domain knowledge.",
        "what are soft skills": "Soft skills are interpersonal qualities like communication, teamwork, time management, and empathy that are essential in the workplace.",
        "how to improve communication": "Practice active listening, read and write regularly, and seek feedback to enhance your communication skills.",
        "how to find jobs": "You can find jobs through portals like LinkedIn, Indeed, or by networking and attending career events.",
        "what is freelancing": "Freelancing is working independently for clients on a project basis instead of being a full-time employee."
    }
    user_input = user_input.lower().strip()
    if user_input in response_map:
        return response_map[user_input]
    return "I'm Asha, your AI guide for women careers, mentorship, and empowerment. Ask me about jobs, events, or career help!"

# -------------------- Smart Chat Handling -------------------- #
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

# -------------------- Chat Endpoint -------------------- #
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

