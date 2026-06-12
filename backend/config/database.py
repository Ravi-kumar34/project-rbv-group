import os
from dotenv import load_dotenv ,find_dotenv
import mysql.connector
from mysql.connector import pooling
from pymongo import MongoClient

load_dotenv(find_dotenv())

# Build connection arguments dynamically
connection_args = {
    "pool_name": "game_pool",
    "pool_size": 10,
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)), # <-- Added port support!
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "project")
}

# --- ADD SSL FOR CLOUD DEPLOYMENTS (AIVEN) ---
# If a CA certificate path is defined in .env, enforce SSL connection
ssl_ca_path = os.getenv("MYSQL_SSL_CA")
if ssl_ca_path:
    connection_args["ssl_ca"] = ssl_ca_path
    connection_args["ssl_verify_cert"] = True

# Initialize the pool using our safe dictionary unpacker
mysql_pool = mysql.connector.pooling.MySQLConnectionPool(**connection_args)

# Initialize MongoDB Client
mongo_client = MongoClient(os.getenv("MONGO_URI"))
mongo_db_name = os.getenv("MONGO_DATABASE")
mongo_db = mongo_client[mongo_db_name]
image_collection = mongo_db["images"]

def get_mysql_connection():
    return mysql_pool.get_connection()