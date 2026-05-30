"""
create_test_user.py

Run once to seed a test user in the MongoDB `users` collection.

Usage:
    python create_test_user.py
    python create_test_user.py --email admin@roadaid.com --password secret123 --name "Admin User"
"""

import argparse
import asyncio
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_user(email: str, password: str, name: str):
    url  = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DATABASE_NAME", "roadaid")
    client = AsyncIOMotorClient(url)
    db = client[db_name]

    existing = await db["users"].find_one({"email": email.lower()})
    if existing:
        print(f"⚠️  User '{email}' already exists — skipping.")
        client.close()
        return

    await db["users"].insert_one({
        "email": email.lower(),
        "name": name,
        "password": pwd_context.hash(password),
    })
    print(f"✅ Created user: {email}  (name: {name})")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed a test user")
    parser.add_argument("--email",    default="admin@roadaid.com")
    parser.add_argument("--password", default="roadaid123")
    parser.add_argument("--name",     default="RoadAid Admin")
    args = parser.parse_args()

    asyncio.run(create_user(args.email, args.password, args.name))
