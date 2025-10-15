import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

_MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
_DB_NAME = os.getenv("MONGODB_DB", "agentflow")

client: AsyncIOMotorClient | None = None

async def get_db():
    global client
    if client is None:
        client = AsyncIOMotorClient(
            _MONGO_URI,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
            socketTimeoutMS=4000,
        )
    # force fast fail instead of hanging
    await client.admin.command("ping")
    return client[_DB_NAME]

