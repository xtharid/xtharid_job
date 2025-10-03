# scraper.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from db import init_db, Product, ScrapperState

def scrape_and_save():
    """Scrape products and save to database using existing model"""
    # Initialize database
    init_db()
    
    # Get current offset from ScrapperState
    state, created = ScrapperState.get_or_create(id=1, defaults={'offset': 0})
    current_offset = state.offset
    
    URL = "https://api.xt-xarid.uz/rpc"
    response = requests.post(URL, json={
        "id": 1,
        "jsonrpc": "2.0",
        "method": "ref",
        "params": {
            "ref": "ref_online_shop_public",
            "op": "read",
            "limit": 100,
            "offset": current_offset,
            "filters": {
                "is_national": "false",
                "is_gos_shop": "true"
            }
        }
    })
    
    if response.status_code == 200:
        data = response.json()
        if 'result' in data and isinstance(data['result'], list):
            products = data['result']
            print(f"Found {len(products)} products (offset: {current_offset})")
            
            saved_count = 0
            skipped_count = 0
            for product_data in products:
                try:
                    # Extract product_id from nested product info, fallback to main id
                    product_info = product_data.get('product', {})
                    product_id = product_info.get('product_id', str(product_data.get('id', '')))
                    main_id = product_data.get('id', 0)
                    
                    # Check if product already exists by either product_id or id
                    existing_by_product_id = Product.select().where(Product.product_id == product_id).exists()
                    existing_by_id = Product.select().where(Product.id == main_id).exists()
                    
                    if existing_by_product_id or existing_by_id:
                        skipped_count += 1
                        print(f"- Product already exists: {product_data.get('product_name', 'Unknown')} (product_id: {product_id}, id: {main_id})")
                        continue
                    
                    # Create new product with full JSON data
                    product = Product.create(
                        id=main_id,
                        product_id=product_id,
                        json_data=json.dumps(product_data, ensure_ascii=False)
                    )
                    
                    saved_count += 1
                    print(f"✓ Saved new product: {product_data.get('product_name', 'Unknown')} (product_id: {product_id}, id: {main_id})")
                        
                except Exception as e:
                    print(f"Error saving product {product_data.get('id', 'unknown')}: {e}")
            
            # Update offset for next run
            new_offset = current_offset + len(products)
            state.offset = new_offset
            state.save()
            
            print(f"\nTotal new products saved: {saved_count}")
            print(f"Total products skipped (already exist): {skipped_count}")
            print(f"Next offset: {new_offset}")
        else:
            print("No products found in response")
    else:
        print(f"API request failed with status: {response.status_code}")

if __name__ == "__main__":
    scrape_and_save()