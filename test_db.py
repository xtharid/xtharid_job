#!/usr/bin/env python3
"""
Test script to verify database structure and basic functionality
"""
import sys
import os

# Add the scapper directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scapper'))

try:
    from db import init_db, Product, ProductDetail
    print("✓ Database imports successful")
    
    # Initialize database
    init_db()
    print("✓ Database initialized")
    
    # Test creating a sample product
    sample_product = Product.create(
        id=999999,
        product_name="Test Product",
        unit="шт",
        price="1000000",
        currency="UZS",
        amount=1.0,
        min_amount=1.0,
        status="test",
        remain_time=86400,
        close_at="2025-12-31T23:59:59Z",
        owner_legal_area_id="test_area",
        green=False,
        product_id="TEST_001",
        product_uid="test-uid-123",
        category_uid="test-category-uid",
        category_title="Test Category",
        category_code="TEST.001",
        images='["test-image-id"]',
        product_properties='[]',
        debug_info='{}'
    )
    print(f"✓ Sample product created with ID: {sample_product.id}")
    
    # Test querying
    products = Product.select()
    print(f"✓ Found {len(products)} products in database")
    
    # Clean up test data
    sample_product.delete_instance()
    print("✓ Test data cleaned up")
    
    print("\n🎉 Database structure test completed successfully!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure to install required packages: pip install peewee requests")
except Exception as e:
    print(f"❌ Error: {e}")
