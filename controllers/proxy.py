from fastapi import Response
import requests
from urllib.parse import unquote
headers = {
    "User-Agent": "YourCompanyName YourAppName (your-email@example.com)"
}

async def fetch_and_return_proxy(request):
    url = request.query_params.get("url")
    if not url:
        return Response("Missing 'url' parameter", status_code=400)
    
    try:
        decoded_url = unquote(url)
        external_response = requests.get(decoded_url, headers=headers)
        return Response(
            content=external_response.content,
            media_type=external_response.headers.get('Content-Type', 'application/octet-stream')
        )
    except Exception as e:
        return Response(f"Failed to fetch: {str(e)}", status_code=500)
