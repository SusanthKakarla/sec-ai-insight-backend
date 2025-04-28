from fastapi import FastAPI
from database.mongo_db import setup_search_indexes
from handlers.search import router as search_router
from handlers.company import router as company_router
from handlers.proxy import router as proxy_router
from middleware.cors import setup_cors

app = FastAPI(title="SEC Company Search API")

# Setup CORS middleware
setup_cors(app)

# Include the search router
app.include_router(search_router)
app.include_router(company_router)
app.include_router(proxy_router)

@app.on_event("startup")
async def startup_event():
    """Create necessary indexes on startup"""
    await setup_search_indexes()
