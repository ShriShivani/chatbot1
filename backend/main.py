from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, EmailStr
import os
import requests
import re
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import firebase_admin
from firebase_admin import credentials
from db import get_collection  # Import MongoDB collection function
import uuid
from datetime import datetime

# Resume upload dependencies
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import tempfile
from bson import ObjectId  # Required for handling MongoDB ObjectId

# Load environment variables
load_dotenv()
JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY")
EVENTBRITE_API_KEY = os.getenv("EVENTBRITE_API_KEY")
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")

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
try:
    chatbot_pipeline = pipeline("text2text-generation", model="google/flan-t5-small")
except Exception as e:
    print(f"Failed to load chatbot model: {e}")
    chatbot_pipeline = None

# MongoDB collections
resumes_collection = get_collection('resumes')
conversations_collection = get_collection('conversations')
jobs_collection = get_collection('jobs')
mentorship_collection = get_collection('mentorship')
events_collection = get_collection('events')

class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    conversation_id: str

class UserAuthRequest(BaseModel):
    email: EmailStr
    password: str

class ResumeResponse(BaseModel):
    message: str
    skills_detected: List[str]
    summary: str
    resume_id: str

# Helper function for HuggingFace API
def query_huggingface(payload):
    API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-xxl"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

# Chat history functions
def get_conversation_history(conversation_id, limit=5):
    """Get the last few messages from the conversation history"""
    if not conversation_id:
        return []
    
    conversation = conversations_collection.find_one({"conversation_id": conversation_id})
    if not conversation:
        return []
        
    return conversation.get("messages", [])[-limit:]

def save_message_to_history(conversation_id, user_id, message, bot_response):
    """Save both user message and bot response to conversation history"""
    timestamp = datetime.now().isoformat()
    
    conversation = conversations_collection.find_one({"conversation_id": conversation_id})
    
    if conversation:
        # Update existing conversation
        conversations_collection.update_one(
            {"conversation_id": conversation_id},
            {
                "$push": {
                    "messages": {
                        "$each": [
                            {"role": "user", "content": message, "timestamp": timestamp},
                            {"role": "assistant", "content": bot_response, "timestamp": timestamp}
                        ]
                    }
                },
                "$set": {"last_updated": timestamp}
            }
        )
    else:
        # Create new conversation
        conversations_collection.insert_one({
            "conversation_id": conversation_id,
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": message, "timestamp": timestamp},
                {"role": "assistant", "content": bot_response, "timestamp": timestamp}
            ],
            "created_at": timestamp,
            "last_updated": timestamp
        })
    
    return conversation_id

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

def get_job_listings(query, user_id=None):
    # First try to get personalized jobs based on user's resume if we have user_id
    user_jobs = []
    if user_id:
        # Find the most recent resume for this user
        resume = resumes_collection.find_one({"user_id": user_id}, sort=[("uploaded_at", -1)])
        if resume:
            # Match jobs based on skills in the resume
            skills = resume.get("skills_detected", [])
            if skills:
                # Search for jobs in the database that match these skills
                skill_pattern = '|'.join([re.escape(skill) for skill in skills])
                try:
                    skill_regex = re.compile(skill_pattern, re.IGNORECASE)
                    matching_jobs = jobs_collection.find(
                        {"$or": [
                            {"job_title": {"$regex": skill_regex}},
                            {"job_description": {"$regex": skill_regex}}
                        ]}
                    ).limit(3)
                    user_jobs = list(matching_jobs)
                except Exception as e:
                    print(f"Error in job matching: {e}")

    # Fallback to JSearch API
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
        
        # Combine with personalized jobs
        if user_jobs:
            all_jobs = user_jobs + jobs
        else:
            all_jobs = jobs
            
        if not all_jobs:
            return "⚠ No jobs found for your query."
            
        return "\n\n".join([
            f"✅ {job.get('job_title', job.get('title', 'Unknown Position'))} at {job.get('employer_name', job.get('company', 'Unknown Company'))} ({job.get('location', job.get('job_location', 'Location not specified'))})"
            for job in all_jobs[:5]
        ])
    except Exception as e:
        return f"❌ Error fetching jobs: {str(e)}"

def get_events():
    # First try to get events from our database
    try:
        db_events = list(events_collection.find().limit(5))
        if db_events:
            return "\n\n".join([
                f"🎉 {event.get('event_name', 'Event')} - {event.get('event_date', 'Date TBD')}" 
                for event in db_events
            ])
    except Exception as e:
        print(f"Error fetching events from database: {e}")
    
    # Fallback to Eventbrite API
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

def get_mentorship_info():
    """Get mentorship information from the database"""
    try:
        mentors = list(mentorship_collection.find().limit(3))
        if mentors:
            return "\n\n".join([
                f"👩‍💼 {mentor.get('name', 'Mentor')}: {mentor.get('expertise', 'Various fields')} - {mentor.get('experience', 'Experienced professional')}"
                for mentor in mentors
            ])
        return "We have mentorship programs available. Would you like me to connect you with a mentor in a specific field?"
    except Exception as e:
        return "We offer mentorship programs. Let me know which area you're interested in, and I can provide more information."

def generate_chatbot_response(user_input, history=None):
    """Generate a response using the chatbot pipeline with context from conversation history"""
    if not history:
        history = []
    
    # Format context from history
    context = ""
    if history:
        context = "Previous conversation:\n" + "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in history
        ])
        context += "\n\nCurrent user message: " + user_input
    else:
        context = user_input
    
    # Try using HuggingFace API for better responses if we have a key
    if HF_API_KEY:
        try:
            payload = {
                "inputs": f"Answer as a helpful career assistant for women: {context}",
                "parameters": {"max_new_tokens": 150}
            }
            response = query_huggingface(payload)
            if isinstance(response, list) and response:
                return response[0].get("generated_text", "")
        except Exception as e:
            print(f"HuggingFace API error: {e}")
    
    # Fallback to local model
    if chatbot_pipeline:
        try:
            response = chatbot_pipeline(context, max_length=150)
            return response[0]['generated_text']
        except Exception as e:
            print(f"Local model error: {e}")
    
    # Manual response if both methods fail
    return "I'm here to help with your career questions! Could you please provide more details about what you're looking for?"

def is_thank_you(message):
    thank_you_variants = ["thank you", "thanks", "thanks a lot", "ty", "thx", "thankyou"]
    return any(thank in message.lower() for thank in thank_you_variants)

def is_irrelevant(message):
    irrelevant_keywords = [
        "recipe", "cooking", "cook", "sambar", "food", "dish", "biryani", "movie", "film", "actor",
        "actress", "celebrity", "cricket", "football", "IPL", "TV show", "series", "gossip", "music"
    ]
    return any(word in message.lower() for word in irrelevant_keywords)

def is_relevant_topic(message):
    topics = ["job", "career", "event", "session", "mentorship", "networking", "growth", "women", "empowerment", "interview", "resume", "skill"]
    return any(topic in message.lower() for topic in topics)

def is_asking_about_previous(message):
    """Check if user is asking about something mentioned before"""
    follow_up_phrases = [
        "what about", "tell me more", "more details", "you mentioned", "earlier", "before",
        "previous", "the first one", "the second one", "you said", "more information"
    ]
    return any(phrase in message.lower() for phrase in follow_up_phrases)

def is_greeting(message):
    """Check if message is a greeting"""
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "what's up", "howdy"]
    return any(greeting == message.lower() or greeting + " " in message.lower() for greeting in greetings)

def is_how_are_you(message):
    how_phrases = ["how are you", "how r you", "how are u", "how r u"]
    return any(phrase in message.lower() for phrase in how_phrases)

@app.post("/chat", response_model=ChatResponse)
def chatbot_api(request: ChatRequest):
    user_message = request.message.strip()
    user_id = request.user_id
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    # Get conversation history
    history = get_conversation_history(conversation_id)
    
    # Detect specific intents
    if is_thank_you(user_message):
        response = "You're welcome! 😊 I'm here to support you with women careers, jobs, mentorship, and events!"
    elif is_how_are_you(user_message):
        response = "I'm good, thanks for asking! 😊 Let me know how I can help you with your career or job search today."
    elif is_greeting(user_message):
        response = "Hello! 👋 I'm Asha, your career assistant. How can I help you today with job search, resume advice, or career development?"
    elif is_irrelevant(user_message):
        response = "🙏 I specialize in career advice, jobs, mentorship, and events focused on women empowerment. How can I help with your professional goals?"
    elif "job" in user_message.lower():
        response = get_job_listings(user_message, user_id)
    elif any(term in user_message.lower() for term in ["event", "session", "workshop"]):
        response = get_events()
    elif any(term in user_message.lower() for term in ["mentor", "mentorship", "guidance"]):
        response = get_mentorship_info()
    elif is_asking_about_previous(user_message) and history:
        # Specially handle follow-up questions
        context = "Based on this conversation history:\n"
        for msg in history:
            context += f"{msg['role'].capitalize()}: {msg['content']}\n"
        context += f"\nUser follow-up: {user_message}\n\nProvide a helpful response:"
        response = generate_chatbot_response(context)
    elif is_relevant_topic(user_message):
        response = generate_chatbot_response(user_message, history)
    else:
        # If we reach here, it's a general conversation
        response = generate_chatbot_response(user_message, history)
        
        # If we got something very generic, add a suggestion
        if len(response) < 30 or "I'm Asha" in response:
            response += "\n\nI can help with job searches, resume tips, finding events, or connecting with mentors. What are you interested in?"
    
    # Save the conversation to the database
    save_message_to_history(conversation_id, user_id, user_message, response)
    
    return ChatResponse(reply=response, conversation_id=conversation_id)

@app.get("/")
def home():
    return {"message": "✅ Asha AI Chatbot Backend is running!"}

# -------------------- ✅ Resume Upload Endpoint -------------------- #
@app.post("/upload-resume/", response_model=ResumeResponse)
async def upload_resume(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        images = convert_from_bytes(pdf_bytes)

        extracted_text = ""
        for image in images:
            text = pytesseract.image_to_string(image)
            extracted_text += text + "\n"

        keywords = ["python", "java", "sql", "ml", "ai", "marketing", "data", "frontend", "backend", 
                   "javascript", "react", "node", "leadership", "project management", "agile", 
                   "scrum", "testing", "cloud", "aws", "azure", "devops", "communication", 
                   "teamwork", "problem solving"]
                   
        matches = [word for word in keywords if word.lower() in extracted_text.lower()]

        # Extract education
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
            matches_edu = re.findall(pattern, extracted_text)
            if matches_edu:
                education.extend(matches_edu)
        
        # Extract experience years
        experience_pattern = r'(?:(\d+)(?:\+)?\s*(?:years?|yrs?)(?:\s*of)?(?:\s*experience)?)'
        experience_matches = re.search(experience_pattern, extracted_text, re.IGNORECASE)
        experience_years = experience_matches.group(1) if experience_matches else "Not specified"
        
        # Store with user ID if available
        resume_data = {
            "file_name": file.filename,
            "extracted_text": extracted_text,
            "skills_detected": list(set(matches)),
            "education": education[:3] if education else ["Not detected"],
            "experience_years": experience_years,
            "uploaded_at": datetime.now().isoformat()
        }

        # Insert to MongoDB
        result = resumes_collection.insert_one(resume_data)
        
        # Generate a summary of the resume
        summary = f"Education: {', '.join(education[:2]) if education else 'Not detected'}\n"
        summary += f"Experience: {experience_years} years\n"
        summary += f"Skills: {', '.join(list(set(matches))[:5])}"
        
        if not summary:
            summary = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text

        return {
            "message": "✅ Resume processed and saved.",
            "skills_detected": list(set(matches)),
            "summary": summary,
            "resume_id": str(result.inserted_id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error processing resume: {str(e)}")

@app.get("/match-jobs/{resume_id}")
async def match_jobs(resume_id: str):
    try:
        # Get resume from MongoDB
        resume = resumes_collection.find_one({"_id": ObjectId(resume_id)})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        skills = resume.get("skills_detected", [])
        if not skills:
            return {"matched_jobs": [], "message": "No skills detected in resume"}
        
        # Search for jobs using JSearch API based on skills
        if JSEARCH_API_KEY:
            url = "https://jsearch.p.rapidapi.com/search"
            headers = {
                "X-RapidAPI-Key": JSEARCH_API_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            
            # Create query with top skills
            query = " ".join(skills[:3]) + " jobs"
            params = {"query": query, "page": "1"}
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            jobs = response.json().get("data", [])
            
            return {"matched_jobs": jobs[:5], "message": "Jobs matched based on your skills"}
        else:
            return {"matched_jobs": [], "message": "API key not available for job matching"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error matching jobs: {str(e)}")

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