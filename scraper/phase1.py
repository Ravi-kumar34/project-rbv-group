import mysql.connector
import csv
import requests
from bson.binary import Binary
from pymongo import MongoClient

# Connect MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="MySQLpassword42",
    database="project"
)

cursor = conn.cursor()

# ---------- MongoDB ----------
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["project_db"]
collection = mongo_db["images"]

# ---------- MAIN ----------
with open('../batch/batch_data.csv', 'r') as file:
    reader = csv.reader(file)
    next(reader)

    for row in reader:
        uid = row[0]
        name = row[1]
        website = row[2]
 
        image_url = "https://" + website + "/images/pfp.jpg"

        try:
            response = requests.get(image_url, timeout=5)

            if response.status_code == 200:
                print(f"{uid} : {name} -> status : Image Found")
                cursor.execute(
                    "INSERT IGNORE INTO users (uid, name) VALUES (%s, %s)",
                    (uid, name)
                )
                # MongoDB UPSERT
                collection.update_one(
                    {"uid": uid},
                    {"$set": {
                        "uid": uid,
                        "name": name,
                        "image": Binary(response.content)
                    }},
                    upsert=True
                )
            else:
                print(f"{uid} : {name} -> status : No Image")

        except:
            print(f"{uid} : {name} -> status : Error")

conn.commit()
print("Data inserted successfully!")

conn.close()
mongo_client.close()