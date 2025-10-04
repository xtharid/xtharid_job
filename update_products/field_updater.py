import json
import time
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

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
        Get products that need field updates.
        
        Returns:
            List of dictionaries containing synced product info and product JSON data
        """
        print(f"📦 Fetching products that need field updates for user: {self.login}")
        
        # Get synced products that need updates
        synced_products = list(SyncedProduct.select().where(
            (SyncedProduct.username == self.login) & 
            (SyncedProduct.is_fields_updated == False)
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

    def update_product_field(self, proc_id: int, field_id: str, field_value: str) -> bool:
        """
        Update a specific field of a product.
        
        Args:
            proc_id: Product procedure ID
            field_id: Field identifier
            field_value: New field value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.api_client.update_product_field(proc_id, field_id, field_value)
            if "error" not in result:
                print(f"✅ Updated field '{field_id}' to '{field_value}' for proc_id {proc_id}")
                return True
            else:
                print(f"❌ Error updating field '{field_id}' for proc_id {proc_id}: {result.get('error')}")
                return False
        except Exception as e:
            print(f"❌ Exception updating field '{field_id}' for proc_id {proc_id}: {e}")
            return False

    def mark_as_updated(self, synced_product: SyncedProduct):
        """Mark a product as having its fields updated."""
        try:
            synced_product.is_fields_updated = True
            synced_product.save()
            print(f"📝 Marked product {synced_product.product_id} as updated")
        except Exception as e:
            print(f"⚠️  Error marking product as updated: {e}")

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
            
            # Get product data from local JSON
            local_product_data = product_data
            
            # Find fields that need updating
            field_updates = []
            
            for field_name, field_info in api_fields.items():
                # Skip system fields and fields that don't have __field__ = true
                if not field_info.get('__field__', False):
                    continue
                
                # Get current value from API
                api_value = field_info.get('value')
                
                # Get corresponding value from local data
                local_value = local_product_data.get(field_name)
                
                # Check if API field is null but local data has a value
                if api_value is None and local_value is not None:
                    # Convert local value to string for API
                    field_value = str(local_value)
                    field_updates.append({
                        "field_id": field_name,
                        "field_value": field_value
                    })
                    print(f"📝 Found field to update: {field_name} (null -> {field_value})")
            
            if not field_updates:
                print(f"ℹ️  No fields need updating for {product_id}")
                self.mark_as_updated(synced_product)
                results["successful"] += 1
                continue
            
            # Apply field updates
            update_success = True
            for field_update in field_updates:
                field_id = field_update["field_id"]
                field_value = field_update["field_value"]
                
                success = self.update_product_field(proc_id, field_id, field_value)
                if not success:
                    update_success = False
                    break
                
                # Add delay between field updates
                if delay_between_fields > 0:
                    time.sleep(delay_between_fields)
            
            if update_success:
                results["successful"] += 1
                self.mark_as_updated(synced_product)
                print(f"✅ Successfully updated {len(field_updates)} fields for {product_id}")
            else:
                results["failed"] += 1
                results["errors"].append({
                    "product_id": product_id,
                    "proc_id": proc_id,
                    "error": "Failed to update one or more fields"
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
    results = updater.process_product_updates(delay_between_requests=2.0, delay_between_fields=0.5)
    print("Field updates completed:", results)
    
if __name__ == "__main__":
    start_field_updates()