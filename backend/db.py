from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# You can also set this in a .env file
MONGO_URI = os.getenv("MONGO_URI") or "mongodb+srv://asha:Harshanya1@asha.swvuq2z.mongodb.net/?retryWrites=true&w=majority&appName=Asha"

def get_db():
    try:
        client = MongoClient(MONGO_URI)
        return client["Asha"]  # ✅ Use correct DB name from your main.py
    except Exception as e:
        print("❌ MongoDB connection error:", e)
        return None

def get_collection(collection_name):
    db = get_db()
    return db[collection_name] if db is not None else None

# Optional: helpers to support your /chat or resume logic

def save_message(user_id, conversation_id, role, message, timestamp):
    coll = get_collection("conversations")
    if not coll: return

    coll.update_one(
        {"conversation_id": conversation_id},
        {
            "$push": {
                "messages": {
                    "role": role,
                    "content": message,
                    "timestamp": timestamp
                }
            }
        }
    )

def get_last_messages(conversation_id, limit=5):
    coll = get_collection("conversations")
    if not coll: return []

    convo = coll.find_one({"conversation_id": conversation_id})
    return convo.get("messages", [])[-limit:] if convo else []

def save_resume_analysis(user_id, data):
    coll = get_collection("resumes")
    data["user_id"] = user_id
    return coll.insert_one(data)

