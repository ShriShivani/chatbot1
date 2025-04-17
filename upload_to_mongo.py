from pymongo import MongoClient
import pandas as pd

client = MongoClient("mongodb+srv://asha:Harshanya1@asha.swvuq2z.mongodb.net/?retryWrites=true&w=majority&appName=Asha")

# Replace below with the database name you want to use
db = client["asha_database"]  

# Collection for resumes.csv
resumes_df = pd.read_csv("data/banking77.csv")
db["resumes"].insert_many(resumes_df.to_dict(orient='records'))

# Collection for emotional_support.csv
support_df = pd.read_csv("data/clinc_oos_small.csv")
db["emotional_support"].insert_many(support_df.to_dict(orient='records'))


# Collection for mentorship.csv
mentor_df = pd.read_csv("data/mentor.csv")
db["mentorship"].insert_many(mentor_df.to_dict(orient='records'))

# Collection for events.csv
events_df = pd.read_csv("data/UpdatedResumeDataSet.csv")
db["events"].insert_many(events_df.to_dict(orient='records'))

print("All CSV files inserted successfully!")
