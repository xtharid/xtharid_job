#!/usr/bin/env python3
"""
Test script to verify MySQL database connection and basic functionality
"""
import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from db import init_db, Product, ScrapperState, SyncedProduct
    print("✓ Database imports successful")
    
    # Initialize database
    init_db()
    print("✓ Database initialized and tables created")
    
    # Test creating a sample product
    sample_product = Product.create(
        id=999999,
        product_id="TEST_MYSQL_001",
        json_data='{"test": "data", "product": {"product_name": "Test MySQL Product"}}'
    )
    print(f"✓ Sample product created with ID: {sample_product.id}")
    
    # Test creating a sample scraper state
    state, created = ScrapperState.get_or_create(id=1, defaults={'offset': 0})
    print(f"✓ ScrapperState created/retrieved: offset={state.offset}")
    
    # Test creating a sample synced product
    from datetime import datetime
    synced_product = SyncedProduct.create(
        username="test_user",
        product_id="TEST_MYSQL_001",
        proc_id=12345,
        is_fields_updated=False,
        synced_at=datetime.now()
    )
    print(f"✓ SyncedProduct created: {synced_product.product_id}")
    
    # Test querying
    products = Product.select()
    print(f"✓ Found {len(products)} products in database")
    
    # Clean up test data
    sample_product.delete_instance()
    synced_product.delete_instance()
    print("✓ Test data cleaned up")
    
    print("\n🎉 MySQL database test completed successfully!")
    print("Your project is ready to use MySQL!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure to install required packages: pip install -r requirements.txt")
except Exception as e:
    print(f"❌ Error: {e}")
    print("Make sure your MySQL database is running and accessible with the configured credentials.")
