import uuid
import random
from datetime import datetime

def generate_id():
    return str(uuid.uuid4())

def generate_order_number():
    """Generate a unique order number"""
    import string
    timestamp = datetime.now().strftime("%y%m%d")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"ORD{timestamp}{random_part}"

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

def generate_invoice_number():
    return f"INV{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
