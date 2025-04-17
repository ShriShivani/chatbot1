from pymongo import MongoClient
import os

# MongoDB URI (You can directly paste your MongoDB URI here or load it from environment variables)
MONGO_URI = "mongodb+srv://asha:Harshanya1@asha.swvuq2z.mongodb.net/?retryWrites=true&w=majority&appName=Asha"

# Function to get the database client
def get_db():
    try:
        # Create a MongoClient instance
        client = MongoClient(MONGO_URI)
        
        # Connect to the database (replace 'your_database_name' with your actual database name)
        db = client["your_database_name"]
        
        # Return the database instance
        return db
    except Exception as e:
        print("Error connecting to MongoDB:", e)
        return None

# Example of how to get the collection (replace 'your_collection_name' with the collection name)
def get_collection(collection_name):
    db = get_db()
    if db is not None:
        collection = db[collection_name]
        return collection
    else:
        print("Failed to connect to the database.")
        return None
