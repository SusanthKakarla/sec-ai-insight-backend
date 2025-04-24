import logging 
import requests
import os 
from dotenv import load_dotenv
from pymongo import MongoClient
from fastapi import HTTPException
import re
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    logging.error("MONGO_URI is not set in environment variables.")
    raise ValueError("MONGO_URI environment variable is not set.")

client = MongoClient(MONGO_URI)
async_client = AsyncIOMotorClient(MONGO_URI)
db = client.companies  # Replace with your database name
companies_collection = db.filings  # Replace with your collection name
async_companies_collection = async_client.companies.filings

async def setup_search_indexes():
    """Create necessary indexes for efficient company searching"""
    await async_companies_collection.create_index([("name", "text"), ("ticker", "text")])
    await async_companies_collection.create_index("name")
    await async_companies_collection.create_index("ticker")

async def search_companies_by_ticker(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search companies by ticker prefix"""
    pattern = re.compile(f"^{re.escape(query)}", re.IGNORECASE)
    return await async_companies_collection.find(
        {"ticker": pattern},
        {"cik": 1, "name": 1, "ticker": 1, "_id": 0}
    ).limit(limit).to_list(limit)

async def search_companies_by_name(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search companies by name prefix"""
    pattern = re.compile(f"^{re.escape(query)}", re.IGNORECASE)
    return await async_companies_collection.find(
        {"name": pattern},
        {"cik": 1, "name": 1, "ticker": 1, "_id": 0}
    ).limit(limit).to_list(limit)

async def search_companies_by_text(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Full text search across company fields"""
    return await async_companies_collection.find(
        {"$text": {"$search": query}},
        {"cik": 1, "name": 1, "ticker": 1, "_id": 0, "score": {"$meta": "textScore"}}
    ).sort([("score", {"$meta": "textScore"})]).limit(limit).to_list(limit)

async def get_filing(cik: str, accession_number: str):
    logging.info(f"Received request for CIK {cik} and accession number {accession_number}")
    try: 
        logging.info(f"Querying MongoDB for CIK {cik} and accession number {accession_number}")
        company = companies_collection.find_one(
            {"cik": cik.lstrip('0')},
            {"filings": {"$elemMatch": {"_id": accession_number}}}
        )

        if not company or not company.get('filings'):
            logging.warning(f"No filing found for CIK {cik} and accession number {accession_number}")
            raise HTTPException(
                status_code=404,
                detail=f"No filing found for CIK {cik} and accession number {accession_number}"
            )
        return {
            "cik": cik, 
            "accessionNumber": accession_number, 
            "url": company['filings'][0]['url'], 
            "form_type": company['filings'][0]['formType']
        }
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch document: {e}")