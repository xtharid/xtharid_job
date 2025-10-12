import json
from math import log
import time
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SyncedProduct, Product, init_db
from create_products.api_client import APIClient

class FieldUpdater:
    """Update product fields for synced products."""
    
    def __init__(self, api_base_url: str, login: str, password: str, client_id: str, 
                 headers: Dict[str, str] = None, products_per_batch: int = 5):
        """
        Initialize FieldUpdater with API client and database connection.
        
        Args:
            api_base_url: Base URL for the API
            login: API login credentials
            password: API password
            client_id: API client ID
            headers: Optional headers for API requests
            products_per_batch: Number of products to process per batch
        """
        self.api_client = APIClient(
            base_url=api_base_url,
            headers=headers or {"origin": "https://xt-xarid.uz"},
            verify_ssl=False
        )
        self.login = login
        self.password = password
        self.client_id = client_id
        self.products_per_batch = products_per_batch
        
        # Field mapping configurations
        self.field_mappings = {
            # Direct mappings (API field -> Local field)
            'desc': 'properties',
            'photo': 'images',  # Will be handled specially below,
            'year': 'release_year',
            'producer': 'vendor',
            'brand': 'mark'
            
            # Add more mappings as needed
            # 'api_field': 'local_field',
        }
        
        # Static value mappings (API field -> Static value)
        self.static_values = {
            'regions': ['33'],  # Static region value (string in array)
            'delivery_period': 10,  # Static delivery period value
            'delivery_unit': 1,  # Static delivery unit value
            'license': False,  # Static license value (boolean)
            'guarantee': 1,
            'guarantee_unit': 30,
            # 'api_field': 'static_value',
            # Example: 'currency': 'UZS',
        }
        
        # Value transformation mappings (API field -> transformation function)
        self.value_transformations = {
            'price': lambda x: float(x) * 2,  # Double the price value (convert to float first)
            'best_before': lambda: (datetime.today() + relativedelta(years=1)).strftime("%Y-%m-%d"),
            # 'api_field': lambda x: x * 2,  # Double the value
            # Example: 'amount': lambda x: x * 2,
        }
        
        # Initialize database connection
        init_db()
        
        # Authenticate with API
        self._authenticate()
        
    def _authenticate(self):
        """Authenticate with the API."""
        print("🔐 Authenticating with API...")
        auth_result = self.api_client.auth_token(
            login=self.login,
            password=self.password,
            client_id=self.client_id
        )
        print("✅ Authentication successful")

    def get_products_needing_updates(self) -> List[Dict[str, Any]]:
        """
        Get products that need field updates, prioritizing products that haven't failed recently.
        
        Returns:
            List of dictionaries containing synced product info and product JSON data
        """
        print(f"📦 Fetching products that need field updates for user: {self.login}")
        
        # Get synced products that need updates, ordered by last_attempt_time (NULL first, then oldest first)
        # This ensures products that haven't been attempted or failed long ago get priority
        synced_products = list(SyncedProduct.select().where(
            (SyncedProduct.username == self.login) & 
            (SyncedProduct.is_fields_updated == False)
        ).order_by(
            SyncedProduct.last_attempt_time.asc(nulls='first')
        ).limit(self.products_per_batch))
        
        print(f"✅ Found {len(synced_products)} synced products needing updates")
        
        # Fetch corresponding product JSON data
        products_with_data = []
        for synced_product in synced_products:
            try:
                # Get product JSON data from Product table
                product = Product.get(Product.product_id == synced_product.product_id)
                
                # Parse JSON data
                product_json = json.loads(product.json_data)
                
                products_with_data.append({
                    'synced_product': synced_product,
                    'product_id': synced_product.product_id,
                    'proc_id': synced_product.proc_id,
                    'product_json': product_json,
                    'product_data': product_json.get('product', {})
                })
                
                print(f"📋 Loaded product: {synced_product.product_id} (proc_id: {synced_product.proc_id})")
                
            except Product.DoesNotExist:
                print(f"⚠️  Product {synced_product.product_id} not found in Product table")
            except json.JSONDecodeError as e:
                print(f"⚠️  Error parsing JSON for product {synced_product.product_id}: {e}")
            except Exception as e:
                print(f"❌ Error loading product {synced_product.product_id}: {e}")
        
        print(f"✅ Successfully loaded {len(products_with_data)} products with JSON data")
        return products_with_data

    def fetch_product_details_from_api(self, proc_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch current product details from API.
        
        Args:
            proc_id: Product procedure ID
            
        Returns:
            Product details dictionary or None if failed
        """
        try:
            result = self.api_client.fetch_product(str(proc_id))
            if "result" in result:
                print(f"📡 Fetched current product details from API for proc_id {proc_id}")
                return result["result"]
            else:
                print(f"⚠️  No result in API response for proc_id {proc_id}")
                return None
        except Exception as e:
            print(f"❌ Error fetching product {proc_id} from API: {e}")
            return None

    def update_product_field(self, proc_id: int, field_id: str, field_value) -> bool:
        """
        Update a specific field of a product.
        
        Args:
            proc_id: Product procedure ID
            field_id: Field identifier
            field_value: New field value
            
        Returns:
            True if successful (HTTP 200), False otherwise
        """
        try:
            result = self.api_client.update_product_field(proc_id, field_id, field_value)
            
            # Check if the API call was successful (HTTP 200)
            # The API client should return the HTTP status or indicate success
            if hasattr(result, 'status_code'):
                # If result has status_code attribute (HTTP response)
                if result.status_code == 200:
                    print(f"✅ Updated field '{field_id}' to '{field_value}' for proc_id {proc_id}")
                    return True
                else:
                    print(f"❌ HTTP {result.status_code} error updating field '{field_id}' for proc_id {proc_id}")
                    return False
            elif isinstance(result, dict):
                # If result is a dictionary, check for error field
                if "error" not in result:
                    print(f"✅ Updated field '{field_id}' to '{field_value}' for proc_id {proc_id}")
                    return True
                else:
                    print(f"❌ Error updating field '{field_id}' for proc_id {proc_id}: {result.get('error')}")
                    return False
            else:
                # If result is not dict and no status_code, assume success
                print(f"✅ Updated field '{field_id}' to '{field_value}' for proc_id {proc_id}")
                return True
                
        except Exception as e:
            print(f"❌ Exception updating field '{field_id}' for proc_id {proc_id}: {e}")
            return False

    def _map_field_value(self, api_field_name, local_data, field_info):
        """
        Map and transform field values from local data to API format.
        
        Args:
            api_field_name: Name of the field in API
            local_data: Local product data dictionary
            field_info: API field information containing type information
            
        Returns:
            Mapped and converted value for API, or None if no mapping found
        """
        # Use class-level field mapping configurations
        
        # Check for static values first
        if api_field_name in self.static_values:
            value = self.static_values[api_field_name]
            print(f"🔧 Using static value for {api_field_name}: {value}")
            return self._convert_value_for_api(value, field_info)
        
        # Check for field mappings
        local_field_name = self.field_mappings.get(api_field_name, api_field_name)
        
        # Special handling for specific fields
        if api_field_name == 'photo' and local_field_name == 'images':
            # Take first image from images array
            images = local_data.get('images', [])
            if images and len(images) > 0:
                value = images[0]  # Take first image
                print(f"🔧 Mapped {api_field_name} from images[0]: {value}")
                return self._convert_value_for_api(value, field_info)
            else:
                print(f"⚠️  No images found for {api_field_name}")
                return None
        
        # Get value from local data
        if local_field_name in local_data:
            value = local_data[local_field_name]
            
            # Apply value transformation if configured
            if api_field_name in self.value_transformations:
                try:
                    original_value = value
                    value = self.value_transformations[api_field_name](value)
                    print(f"🔧 Transformed {api_field_name}: {original_value} -> {value}")
                except Exception as e:
                    print(f"⚠️  Error transforming {api_field_name}: {e}")
                    return None
            
            return self._convert_value_for_api(value, field_info)
        
        return None

    def _convert_value_for_api(self, local_value, field_info):
        """
        Convert local value to appropriate type for API based on field type.
        
        Args:
            local_value: Value from local data
            field_info: API field information containing type information
            
        Returns:
            Converted value in appropriate format for API
        """
        field_type = field_info.get('type', '')
        
        # Handle numeric fields
        if field_type in ['number', 'float', 'int']:
            try:
                # Convert to float first, then to int if it's a whole number
                float_val = float(local_value)
                if float_val.is_integer():
                    return int(float_val)
                return float_val
            except (ValueError, TypeError):
                print(f"⚠️  Could not convert '{local_value}' to number for field type '{field_type}'")
                return str(local_value)
        
        # Handle boolean fields
        elif field_type == 'bool':
            if isinstance(local_value, bool):
                return local_value
            elif isinstance(local_value, str):
                return local_value.lower() in ['true', '1', 'yes', 'on']
            else:
                return bool(local_value)
        
        # Handle date fields
        elif field_type == 'date':
            # Keep as string for date fields
            return str(local_value)
        
        # Handle text/string fields
        else:
            # Don't convert arrays, dicts, or booleans to strings - keep them as-is
            if isinstance(local_value, (list, dict, bool)):
                return local_value
            return str(local_value)

    def mark_as_updated(self, synced_product: SyncedProduct):
        """Mark a product as having its fields updated."""
        try:
            synced_product.is_fields_updated = True
            synced_product.last_attempt_time = None  # Clear attempt time since it's now successful
            synced_product.save()
            print(f"📝 Marked product {synced_product.product_id} as updated")
        except Exception as e:
            print(f"⚠️  Error marking product as updated: {e}")

    def mark_as_failed(self, synced_product: SyncedProduct):
        """Mark a product as failed and update the last attempt time to push it back in queue."""
        try:
            synced_product.last_attempt_time = datetime.now()
            synced_product.save()
            print(f"📝 Marked product {synced_product.product_id} as failed - pushed back in queue")
        except Exception as e:
            print(f"⚠️  Error marking product as failed: {e}")

    def process_product_updates(self, delay_between_requests: float = 2.0, delay_between_fields: float = 0.5) -> Dict[str, Any]:
        """
        Process field updates for products that need them.
        
        Args:
            delay_between_requests: Delay in seconds between product processing
            delay_between_fields: Delay in seconds between field updates
            
        Returns:
            Summary of update operation
        """
        print("🚀 Starting product field updates...")
        
        # Get products that need updates
        products = self.get_products_needing_updates()
        
        if not products:
            print("ℹ️  No products need field updates")
            return {"total": 0, "successful": 0, "failed": 0, "errors": []}
        
        # Track results
        results = {
            "total": len(products),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        # Process each product
        for i, product_info in enumerate(products, 1):
            synced_product = product_info['synced_product']
            product_id = product_info['product_id']
            proc_id = product_info['proc_id']
            product_json = product_info['product_json']
            product_data = product_info['product_data']
            
            print(f"\n📤 Processing product {i}/{len(products)}: {product_id} (proc_id: {proc_id})")
            print(f"📋 Product name: {product_data.get('product_name', 'Unknown')}")
            
            # Fetch current product details from API
            current_api_data = self.fetch_product_details_from_api(proc_id)
            if not current_api_data:
                results["failed"] += 1
                self.mark_as_failed(synced_product)  # Push failed product back in queue
                results["errors"].append({
                    "product_id": product_id,
                    "proc_id": proc_id,
                    "error": "Failed to fetch product details from API"
                })
                continue
            
            # Compare API data with local JSON data and update null fields
            print(f"🔍 Analyzing product data for updates...")
            
            # Get fields from API response
            api_fields = current_api_data.get('fields', {})
            print(f"📊 API has {len(api_fields)} fields")
            
            # Get product data from local JSON (use full JSON, not just 'product' section)
            local_product_data = product_json
            print(f"📊 Local data has {len(local_product_data)} fields")
            
            # Debug: Show some sample fields
            print(f"🔍 Sample API fields: {list(api_fields.keys())[:10]}")
            print(f"🔍 Sample local fields: {list(local_product_data.keys())[:10]}")
            
            # Debug: Show all null API fields
            print(f"🔍 All null API fields:")
            for field_name, field_info in api_fields.items():
                if field_info.get('__field__', False) and field_info.get('value') is None:
                    print(f"   - {field_name}")
            
            # Special debug for license field
            if 'license' in api_fields:
                license_info = api_fields['license']
                license_value = license_info.get('value')
                print(f"🔍 LICENSE FIELD DEBUG:")
                print(f"   - license value: {license_value} (type: {type(license_value)})")
                print(f"   - license __field__: {license_info.get('__field__', False)}")
                print(f"   - license is None: {license_value is None}")
                print(f"   - license == '': {license_value == ''}")
                print(f"   - license == False: {license_value == False}")
            
            # Find fields that need updating
            field_updates = []
            null_fields_count = 0
            matching_fields_count = 0
            
            for field_name, field_info in api_fields.items():
                # Skip system fields and fields that don't have __field__ = true
                # Exception: process fields that are in our static values or field mappings
                if not field_info.get('__field__', False) and field_name not in self.static_values and field_name not in self.field_mappings:
                    continue
                
                # Get current value from API
                api_value = field_info.get('value')
                
                # Check if field needs updating (null, empty array, or empty string)
                needs_update = False
                if api_value is None:
                    needs_update = True
                    null_fields_count += 1
                    print(f"🔍 API field '{field_name}' is null")
                elif field_name in ['photo', 'regions'] and isinstance(api_value, list) and len(api_value) == 0:
                    needs_update = True
                    null_fields_count += 1
                    print(f"🔍 API field '{field_name}' is empty array")
                elif field_name == 'producer' and api_value == "":
                    needs_update = True
                    null_fields_count += 1
                    print(f"🔍 API field '{field_name}' is empty string")
                
                # Get corresponding value from local data using mapper
                mapped_value = self._map_field_value(field_name, local_product_data, field_info)
                
                # Special debug for license field mapping
                if field_name == 'license':
                    print(f"🔍 LICENSE MAPPING DEBUG:")
                    print(f"   - mapped_value: {mapped_value} (type: {type(mapped_value)})")
                    print(f"   - mapped_value is not None: {mapped_value is not None}")
                
                # Count matching fields (check if we found a value through mapping)
                if mapped_value is not None:
                    matching_fields_count += 1
                    print(f"🔍 Field '{field_name}' mapped successfully: API={api_value}, Mapped={mapped_value}")
                
                # Check if field needs updating and we have a mapped value
                if needs_update and mapped_value is not None:
                    field_updates.append({
                        "field_id": field_name,
                        "field_value": mapped_value
                    })
                    print(f"📝 Found field to update: {field_name} (empty -> {mapped_value})")
            
            print(f"📊 Summary: {null_fields_count} null API fields, {matching_fields_count} matching fields, {len(field_updates)} fields to update")
            
            if not field_updates:
                print(f"ℹ️  No fields need updating for {product_id} - marking as updated")
                self.mark_as_updated(synced_product)
                results["successful"] += 1
                continue
            
            # Apply field updates
            successful_updates = 0
            failed_updates = 0
            field_errors = []
            
            for field_update in field_updates:
                field_id = field_update["field_id"]
                field_value = field_update["field_value"]
                
                success = self.update_product_field(proc_id, field_id, field_value)
                if success:
                    successful_updates += 1
                else:
                    failed_updates += 1
                    field_errors.append(f"{field_id}: {field_value}")
                
                # Add delay between field updates
                if delay_between_fields > 0:
                    time.sleep(delay_between_fields)
            
            # Mark as successful only if ALL field updates were successful (no failures)
            if failed_updates == 0:
                results["successful"] += 1
                self.mark_as_updated(synced_product)
                print(f"✅ Successfully updated ALL {successful_updates}/{len(field_updates)} fields for {product_id}")
            else:
                results["failed"] += 1
                self.mark_as_failed(synced_product)  # Push failed product back in queue
                print(f"❌ Failed to update {failed_updates}/{len(field_updates)} fields for {product_id}: {', '.join(field_errors)}")
                results["errors"].append({
                    "product_id": product_id,
                    "proc_id": proc_id,
                    "error": f"Failed to update {failed_updates} out of {len(field_updates)} fields: {', '.join(field_errors)}"
                })
            
            # Add delay between products
            if i < len(products) and delay_between_requests > 0:
                print(f"⏳ Waiting {delay_between_requests}s before next product...")
                time.sleep(delay_between_requests)
        
        # Print summary
        print(f"\n📊 Update Summary:")
        print(f"   Total products processed: {results['total']}")
        print(f"   Successful: {results['successful']}")
        print(f"   Failed: {results['failed']}")
        
        if results['errors']:
            print(f"   Errors:")
            for error in results['errors']:
                print(f"     - {error['product_id']} (proc_id: {error['proc_id']}): {error['error']}")
        
        return results

# Application entry point
def start_field_updates():
    # Get credentials from environment variables (GitHub secrets)
    login = os.getenv('XT_XARID_LOGIN')
    password = os.getenv('XT_XARID_PASSWORD')
    
    if not all([login, password]):
        raise ValueError("Missing required environment variables: XT_XARID_LOGIN, XT_XARID_PASSWORD")
    
    updater = FieldUpdater(
        api_base_url="https://api.xt-xarid.uz",
        login=login,
        password=password,
        client_id="af36f6cbc",  # Hardcoded client_id
        products_per_batch=1  # Fetch only 5 products as requested
    )
    results = updater.process_product_updates(delay_between_requests=10.0, delay_between_fields=0.5)
    print("Field updates completed:", results)
    
if __name__ == "__main__":
    start_field_updates()