from pymongo import MongoClient
import pandas as pd
import os

client = MongoClient("mongodb+srv://asha:Harshanya1@asha.swvuq2z.mongodb.net/?retryWrites=true&w=majority&appName=Asha")
db = client["Asha"]

data_path = "data"

def upload_csv_to_collection(file_name, collection_name):
    try:
        path = os.path.join(data_path, file_name)
        if not os.path.exists(path):
            print(f"❌ File not found: {file_name}")
            return

        df = pd.read_csv(path)
        db[collection_name].delete_many({})  # Optional: clear existing data
        db[collection_name].insert_many(df.to_dict(orient='records'))

        print(f"✅ {file_name} uploaded to collection '{collection_name}'")
    except Exception as e:
        print(f"❌ Failed to upload {file_name}: {e}")

# Upload all
upload_csv_to_collection("banking77.csv", "resumes")
upload_csv_to_collection("clinc_oos_small.csv", "emotional_support")
upload_csv_to_collection("mentor.csv", "mentorship")
upload_csv_to_collection("UpdatedResumeDataSet.csv", "events")

print("✅ All uploads completed.")
