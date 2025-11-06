# scraper.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import time
from db import init_db, Product, ScrapperState

def scrape_and_save():
    """Scrape products and save to database using existing model"""
    # Initialize database
    init_db()
    
    # List of main_id prefixes to exclude (first part before the first dot)
    excluded_prefixes = []
    
    # Get current offset from ScrapperState
    state, created = ScrapperState.get_or_create(id=1, defaults={'offset': 0})
    current_offset = state.offset
    
    URL = "https://api.xt-xarid.uz/rpc"
    
    # First RPC call: Get proc_ids from contract_ref
    print(f"Making first RPC call to get proc_ids (offset: {current_offset})...")
    contract_response = requests.post(URL, json={
        "id": 1,
        "jsonrpc": "2.0",
        "method": "contract_ref",
        "params": {
            "ref": "online_shop_contract_public_registry",
            "op": "read",
            "limit": 50,
            "offset": current_offset,
            "filters": {
                "nad": False
            },
            "fields": ["contragent"]
        }
    })
    
    proc_ids = []
    contract_data = None
    if contract_response.status_code == 200:
        contract_data = contract_response.json()
        if 'result' in contract_data and isinstance(contract_data['result'], list):
            for item in contract_data['result']:
                contragent = item.get('contragent', {})
                proc_id = contragent.get('proc_id')
                if proc_id:
                    proc_ids.append(proc_id)
            print(f"Found {len(proc_ids)} proc_ids from contract_ref")
        else:
            print("No results found in contract_ref response")
    else:
        print(f"Contract_ref API request failed with status: {contract_response.status_code}")
        return
    
    if not proc_ids:
        print("No proc_ids found, skipping second RPC call")
        return
    
    # Wait 15 seconds between RPC calls
    print("Waiting 15 seconds before second RPC call...")
    time.sleep(15)
    
    # Second RPC call: Get products using proc_ids
    print(f"Making second RPC call with {len(proc_ids)} proc_ids...")
    response = requests.post(URL, json={
        "id": 1,
        "jsonrpc": "2.0",
        "method": "ref",
        "params": {
            "ref": "ref_online_shop_public",
            "op": "read",
            "limit": 50,
            "offset": 0,
            "filters": {
                "is_national": False,
                "is_gos_shop": True,
                "id": proc_ids
            }
        }
    })
    
    saved_count = 0
    skipped_count = 0
    excluded_count = 0
    second_call_success = False
    
    if response.status_code == 200:
        data = response.json()
        if 'result' in data and isinstance(data['result'], list):
            products = data['result']
            print(f"Found {len(products)} products")
            second_call_success = True
            
            for product_data in products:
                try:
                    # Extract product_id from nested product info, fallback to main id
                    product_info = product_data.get('product', {})
                    product_id = product_info.get('product_id', str(product_data.get('id', '')))
                    main_id = product_data.get('id', 0)
                    
                    # Check if main_id should be excluded based on prefix
                    main_id_str = str(main_id)
                    if '.' in main_id_str:
                        first_part = main_id_str.split('.')[0]
                        if first_part in excluded_prefixes:
                            excluded_count += 1
                            print(f"✗ Excluded product (prefix {first_part}): {product_data.get('product_name', 'Unknown')} (main_id: {main_id})")
                            continue
                    
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
        else:
            print("No products found in response")
    else:
        print(f"API request failed with status: {response.status_code}")
    
    # Update offset for next run only if both RPC calls were successful
    first_call_success = contract_data is not None and 'result' in contract_data and isinstance(contract_data['result'], list)
    
    if first_call_success and second_call_success:
        contract_results = contract_data.get('result', [])
        new_offset = current_offset + len(contract_results)
        state.offset = new_offset
        state.save()
        
        print(f"\nTotal new products saved: {saved_count}")
        print(f"Total products skipped (already exist): {skipped_count}")
        print(f"Total products excluded: {excluded_count}")
        print(f"Next offset: {new_offset}")
    else:
        print(f"\nTotal new products saved: {saved_count}")
        print(f"Total products skipped (already exist): {skipped_count}")
        print(f"Total products excluded: {excluded_count}")
        if not first_call_success:
            print("Offset not updated - first RPC call failed or had no results")
        elif not second_call_success:
            print("Offset not updated - second RPC call failed")

if __name__ == "__main__":
    scrape_and_save()