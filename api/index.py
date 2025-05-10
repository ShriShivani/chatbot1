from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add the parent directory to the path to import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.main import app as backend_app

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Forward all requests to the backend application
@app.get("/{path:path}")
async def catch_all(path: str, request: Request):
    return await backend_app.handle_request(request)

# Import all routes from the backend app
app.routes.extend(backend_app.routes)