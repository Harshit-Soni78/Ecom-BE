import os
from pathlib import Path

# Adjust path to point to root .env
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
# Assuming we load dotenv in app/main.py or app/db/session.py, 
# but redundant loading is safe.
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

class Config:
    JWT_SECRET = os.environ.get('JWT_SECRET', 'bharatbazaar-secret-key-2024')
    JWT_ALGORITHM = "HS256"
    
    DELHIVERY_TOKEN = os.environ.get('DELHIVERY_TOKEN', 'ac9b6a862cffeba552eeb07729e40e692b7a3fd8')
    
    # Add other config variables here
    UPLOAD_DIR = Path("uploads")

settings = Config()
