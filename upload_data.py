import pandas as pd
from pymongo import MongoClient
import os

# MongoDB connection
client = MongoClient("mongodb+srv://asha:Harshanya1@asha.swvuq2z.mongodb.net/?retryWrites=true&w=majority&appName=Asha")

# Replace with your actual DB name
db = client["Asha"]

# Map CSV filenames to collection names
csv_collection_map = {
    'resumes.csv': 'resumes_collection',
    'emotional_support.csv': 'emotional_support_collection',
    'events.csv': 'events_collection',
    'mentorship.csv': 'mentorship_collection'
}

# Path to your data folder
data_folder = 'data'

# Loop through each file and insert into respective collection
for filename, collection_name in csv_collection_map.items():
    file_path = os.path.join(data_folder, filename)
    
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        data_dict = df.to_dict(orient='records')
        collection = db[collection_name]
        collection.insert_many(data_dict)
        print(f"✅ Inserted data from '{filename}' into collection '{collection_name}'.")
    else:
        print(f"❌ File '{filename}' not found.")
