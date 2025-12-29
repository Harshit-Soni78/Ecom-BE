#!/usr/bin/env python3
"""
Migration script to add enhanced return and cancellation system fields
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def migrate_database():
    """Add new fields for enhanced return and cancellation system"""
    
    db_path = Path("local_db.sqlite")
    if not db_path.exists():
        print("❌ Database file not found!")
        return False
    
    print("🔧 Migrating database for enhanced return system...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add new fields to returns table
        print("📝 Adding new fields to returns table...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(returns)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        new_columns = [
            ("return_type", "VARCHAR(20) DEFAULT 'defective'"),
            ("evidence_images", "JSON DEFAULT '[]'"),
            ("evidence_videos", "JSON DEFAULT '[]'"),
            ("pickup_completed_date", "DATETIME"),
            ("received_date", "DATETIME"),
            ("admin_notes", "TEXT"),
            ("processed_by", "VARCHAR(36)")
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE returns ADD COLUMN {column_name} {column_def}")
                    print(f"   ✅ Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        print(f"   ⚠️  Warning adding {column_name}: {e}")
            else:
                print(f"   ⏭️  Column {column_name} already exists")
        
        # Create order_cancellations table
        print("📝 Creating order_cancellations table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_cancellations (
                id VARCHAR(36) PRIMARY KEY,
                order_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36),
                reason TEXT,
                cancellation_type VARCHAR(20) DEFAULT 'customer',
                cancelled_by VARCHAR(36),
                refund_amount FLOAT,
                refund_status VARCHAR(20) DEFAULT 'pending',
                shipment_cancelled BOOLEAN DEFAULT 0,
                shipment_cancel_response JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        print("   ✅ Created order_cancellations table")
        
        # Update existing return requests with default values
        print("📝 Updating existing return requests...")
        cursor.execute("""
            UPDATE returns 
            SET return_type = 'defective',
                evidence_images = '[]',
                evidence_videos = '[]'
            WHERE return_type IS NULL
        """)
        
        # Create indexes for better performance
        print("📝 Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_returns_status ON returns(status)",
            "CREATE INDEX IF NOT EXISTS idx_returns_user_id ON returns(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_returns_order_id ON returns(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_cancellations_order_id ON order_cancellations(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_cancellations_user_id ON order_cancellations(user_id)"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                print(f"   ✅ Created index")
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e).lower():
                    print(f"   ⚠️  Warning creating index: {e}")
        
        conn.commit()
        conn.close()
        
        print("🎉 Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        return False

def verify_migration():
    """Verify that the migration was successful"""
    print("\n🔍 Verifying migration...")
    
    try:
        conn = sqlite3.connect("local_db.sqlite")
        cursor = conn.cursor()
        
        # Check returns table structure
        cursor.execute("PRAGMA table_info(returns)")
        returns_columns = [column[1] for column in cursor.fetchall()]
        
        expected_columns = [
            'return_type', 'evidence_images', 'evidence_videos', 
            'pickup_completed_date', 'received_date', 'admin_notes', 'processed_by'
        ]
        
        missing_columns = [col for col in expected_columns if col not in returns_columns]
        if missing_columns:
            print(f"❌ Missing columns in returns table: {missing_columns}")
            return False
        
        # Check order_cancellations table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_cancellations'")
        if not cursor.fetchone():
            print("❌ order_cancellations table not found")
            return False
        
        # Check sample data
        cursor.execute("SELECT COUNT(*) FROM returns")
        returns_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM order_cancellations")
        cancellations_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"✅ Returns table: {returns_count} records")
        print(f"✅ Order cancellations table: {cancellations_count} records")
        print("✅ Migration verification successful!")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Enhanced Return & Cancellation System Migration")
    print("=" * 60)
    
    success = migrate_database()
    if success:
        verify_migration()
    else:
        print("❌ Migration failed!")
        exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Migration Complete!")
    print("=" * 60)