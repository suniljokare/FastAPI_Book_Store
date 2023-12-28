# create_admin_user.py

import asyncio
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from main import create_user, User

app = FastAPI()

# MongoDB Settings
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "book-store"

# Connect to MongoDB
async def get_database():
    client = AsyncIOMotorClient(MONGO_URI)
    database = client[MONGO_DB]
    return database

async def create_admin_user():
    database = await get_database()
    # async with get_database() as db:
    admin_user = User(
        email="dj1@gmail.com",
        first_name="admin",
        last_name="admin",
        password="dj",
        is_admin=True,
    )
    await create_user(admin_user, admin_user.password, is_admin=admin_user.is_admin)

if __name__ == "__main__":
    # Run the script to create the admin user
    asyncio.run(create_admin_user())
