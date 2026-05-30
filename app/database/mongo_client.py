import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "roadaid")


class MongoDB:
    """Holds the async MongoDB client and database reference."""
    client: AsyncIOMotorClient = None
    db = None


mongodb = MongoDB()


async def connect_to_mongo():
    """Called on app startup — creates the async connection."""
    mongodb.client = AsyncIOMotorClient(MONGODB_URL)
    mongodb.db = mongodb.client[DATABASE_NAME]
    print(f"✅ Connected to MongoDB: {DATABASE_NAME}")


async def close_mongo_connection():
    """Called on app shutdown — closes the async connection."""
    if mongodb.client:
        mongodb.client.close()
        print("🔌 MongoDB connection closed")


def get_db():
    """Returns the async database object for use in FastAPI routes."""
    return mongodb.db


def get_sync_db():
    """
    Returns a synchronous MongoDB database connection.
    Used by LangChain services that run outside async context.
    """
    client = MongoClient(MONGODB_URL)
    return client[DATABASE_NAME]
