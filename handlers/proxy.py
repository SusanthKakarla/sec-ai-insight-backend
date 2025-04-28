from fastapi import APIRouter, Request, Response
from controllers.proxy import fetch_and_return_proxy

router = APIRouter()

@router.get("/proxy")
async def proxy_handler(request: Request):
    return await fetch_and_return_proxy(request)
