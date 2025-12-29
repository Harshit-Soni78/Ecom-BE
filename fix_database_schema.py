#!/usr/bin/env python3
"""
Fix database schema by adding missing columns
"""

import sqlite3
import os
from pathlib import Path

def fix_database_schema():
    """Add missing columns to the database"""
    
    # Get database path
    db_path = Path("local_db.sqlite")
    if not db_path.exists():
        print("❌ Database file not found!")
        return False
    
    print("🔧 Fixing database schema...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings';")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("📝 Creating settings table...")
            cursor.execute("""
                CREATE TABLE settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type VARCHAR(20) UNIQUE,
                    business_name VARCHAR(100),
                    company_name VARCHAR(100),
                    gst_number VARCHAR(20),
                    address JSON,
                    phone VARCHAR(15),
                    email VARCHAR(100),
                    logo_url TEXT,
                    favicon_url TEXT,
                    social_links JSON,
                    configs JSON,
                    updated_at DATETIME
                );
            """)
            print("✅ Settings table created")
        else:
            print("📝 Settings table exists, checking columns...")
            
            # Get existing columns
            cursor.execute("PRAGMA table_info(settings);")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"   Existing columns: {columns}")
            
            # Add missing columns
            missing_columns = {
                'company_name': 'VARCHAR(100)',
                'gst_number': 'VARCHAR(20)',
                'address': 'JSON',
                'phone': 'VARCHAR(15)',
                'email': 'VARCHAR(100)',
                'logo_url': 'TEXT',
                'favicon_url': 'TEXT',
                'social_links': 'JSON',
                'configs': 'JSON',
                'updated_at': 'DATETIME'
            }
            
            for column_name, column_type in missing_columns.items():
                if column_name not in columns:
                    print(f"   Adding column: {column_name}")
                    cursor.execute(f"ALTER TABLE settings ADD COLUMN {column_name} {column_type};")
            
            print("✅ Settings table schema updated")
        
        # Insert default settings if none exist
        cursor.execute("SELECT COUNT(*) FROM settings WHERE type = 'business';")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("📝 Creating default business settings...")
            cursor.execute("""
                INSERT INTO settings (
                    type, business_name, company_name, phone, email, 
                    configs, updated_at
                ) VALUES (
                    'business', 'Amorlias', 'Amorlias International Pvt Ltd', 
                    '9999999999', 'support@amorlias.com',
                    '{"enable_gst_billing": true, "default_gst_rate": 18.0, "invoice_prefix": "INV", "order_prefix": "ORD"}',
                    datetime('now')
                );
            """)
            print("✅ Default settings created")
        
        conn.commit()
        conn.close()
        
        print("🎉 Database schema fixed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing database schema: {str(e)}")
        return False

if __name__ == "__main__":
    success = fix_database_schema()
    exit(0 if success else 1)