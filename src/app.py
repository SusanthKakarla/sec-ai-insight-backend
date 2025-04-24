from fastapi import FastAPI
from database.mongo_db import setup_search_indexes
from handlers.search import router as search_router
from middleware.cors import setup_cors

app = FastAPI(title="SEC Company Search API")

# Setup CORS middleware
setup_cors(app)

# Include the search router
app.include_router(search_router)

@app.on_event("startup")
async def startup_event():
    """Create necessary indexes on startup"""
    await setup_search_indexes()
