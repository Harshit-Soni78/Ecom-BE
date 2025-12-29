#!/usr/bin/env python3
"""
Simple script to create the wishlist table if it doesn't exist.
Run this after adding the Wishlist model to ensure the table is created.
"""

from database import engine
import models

def create_wishlist_table():
    """Create the wishlist table if it doesn't exist"""
    try:
        # This will create all tables defined in models.py that don't exist yet
        models.Base.metadata.create_all(bind=engine)
        print("✅ Wishlist table created successfully (or already exists)")
    except Exception as e:
        print(f"❌ Error creating wishlist table: {e}")

if __name__ == "__main__":
    create_wishlist_table()