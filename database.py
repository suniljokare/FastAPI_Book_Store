# database.py

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

def connect_to_mongo():
    try:
        client = MongoClient("mongodb://localhost:27017/")
        client.admin.command('ismaster')
        return client
    except ConnectionFailure:
        print("MongoDB server not available")
        return None

mongo_client = connect_to_mongo()
