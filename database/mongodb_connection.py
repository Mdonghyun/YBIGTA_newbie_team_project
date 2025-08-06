from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

mongo_url = os.getenv("MONGO_URL")
mongo_db_name = os.getenv("MONGO_DB_NAME", "tododb")

mongo_client = MongoClient(mongo_url)

mongo_db = mongo_client[mongo_db_name]
