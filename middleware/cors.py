from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

def get_allowed_origins() -> List[str]:
    """
    Get allowed origins from environment variables.
    Falls back to default development origins if not set.
    """
    # Get origins from environment variable, split by comma
    origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://localhost:3000")
    origins = origins_env.split(",")
    
    # Strip whitespace from each origin
    origins = [origin.strip() for origin in origins]
    
    return origins

def setup_cors(app):
    """
    Setup CORS middleware with configuration from environment variables
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ) 