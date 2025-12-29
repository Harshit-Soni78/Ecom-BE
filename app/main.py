from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import logging
from dotenv import load_dotenv
import uvicorn

# Load env variables
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / '.env')

from app.api.v1.api import api_router
from app.db.base import Base
from app.db.session import engine

# Import all models to ensure they are registered with Base.metadata
from app.models import user, product, order, content, settings

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="BharatBazaar API")

# Mount static files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "BharatBazaar API (SQL)", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
