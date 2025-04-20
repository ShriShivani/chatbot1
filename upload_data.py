import pandas as pd
from pymongo import MongoClient
import os

# MongoDB connection
client = MongoClient("mongodb+srv://asha:Harshanya1@asha.swvuq2z.mongodb.net/?retryWrites=true&w=majority&appName=Asha")
db = client["Asha"]

# CSV-to-collection map (match to your files)
csv_collection_map = {
    'banking77.csv': 'resumes',
    'clinc_oos_small.csv': 'emotional_support',
    'mentor.csv': 'mentorship',
    'UpdatedResumeDataSet.csv': 'events'
}

data_folder = 'data'

# Loop to read and insert data
for filename, collection_name in csv_collection_map.items():
    file_path = os.path.join(data_folder, filename)

    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            data_dict = df.to_dict(orient='records')
            collection = db[collection_name]

            # Optional: Drop existing data before inserting
            collection.delete_many({})
            collection.insert_many(data_dict)

            print(f"✅ Successfully uploaded: {filename} → {collection_name}")
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
    else:
        print(f"❌ File not found: {file_path}")

