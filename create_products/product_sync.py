import json
import time
import sys
import os
from typing import List, Dict, Any
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Product, SyncedProduct, init_db
from create_products.api_client import APIClient

class SyncTracker:
    """Track synced products by username using database."""
    
    def __init__(self, username: str):
        self.username = username
    
    def is_synced(self, product_id: str) -> bool:
        """Check if a product has already been synced by this user."""
        try:
            SyncedProduct.get(
                (SyncedProduct.username == self.username) & 
                (SyncedProduct.product_id == product_id)
            )
            return True
        except SyncedProduct.DoesNotExist:
            return False
    
    def mark_as_synced(self, product_id: str, proc_id: int):
        """Mark a product as synced for this user."""
        try:
            SyncedProduct.create(
                username=self.username,
                product_id=product_id,
                proc_id=proc_id,
                synced_at=datetime.now()
            )
        except Exception as e:
            # Handle case where record already exists (unique constraint)
            if "UNIQUE constraint failed" in str(e):
                print(f"ℹ️  Product {product_id} already marked as synced for {self.username}")
            else:
                print(f"⚠️  Error marking product as synced: {e}")
    
class ProductSync:
    def __init__(self, api_base_url: str, login: str, password: str, client_id: str, 
                 headers: Dict[str, str] = None, products_per_batch: int = 10):
        """
        Initialize ProductSync with API client and database connection.
        
        Args:
            api_base_url: Base URL for the API
            login: API login credentials
            password: API password
            client_id: API client ID
            headers: Optional headers for API requests
            products_per_batch: Number of products to fetch and sync per batch
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
        
        # Initialize sync tracking
        self.sync_tracker = SyncTracker(login)
        
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

    def fetch_products_from_db(self) -> List[Dict[str, Any]]:
        """
        Fetch non-synced products from SQLite database.
        
        Returns:
            List of product dictionaries for non-synced products (max products_per_batch)
        """
        print(f"📦 Fetching {self.products_per_batch} non-synced products from database...")
        
        products = []
        skipped_count = 0
        processed_count = 0
        
        for product in Product.select():
            processed_count += 1
            
            try:
                # Parse JSON data from database
                json_data = json.loads(product.json_data)
                product_data = json_data.get('product')
                
                if not product_data:
                    print(f"⚠️  No 'product' key found in JSON for product {product.product_id}")
                    continue
                
                product_id = product_data.get('product_id')
                if not product_id:
                    print(f"⚠️  No product_id found in product data for {product.product_id}")
                    continue
                
                # Skip if already synced by this user
                if self.sync_tracker.is_synced(product_id):
                    skipped_count += 1
                    continue
                    
                # Store product data
                products.append(product_data)
                
                # Stop when we have the configured number of non-synced products
                if len(products) >= self.products_per_batch:
                    break
                    
            except json.JSONDecodeError as e:
                print(f"⚠️  Error parsing JSON for product {product.product_id}: {e}")
                continue
                
        print(f"✅ Fetched {len(products)} non-synced products from database")
        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} already synced products")
        print(f"📊 Processed {processed_count} total products from database")
        return products

    def create_product_via_api(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a single product via API.
        
        Args:
            product_data: Product data dictionary
            
        Returns:
            API response dictionary
        """
        product_id = product_data.get('product_id', 'Unknown')
        product_name = product_data.get('product_name', 'Unknown')
        
        try:
            result = self.api_client.create_product(product_data)
            print(f"✅ Product created successfully: {product_name}")
            
            return result
        except Exception as e:
            print(f"❌ Error creating product {product_name}: {e}")
            return {"error": str(e)}



    def sync_products(self, delay_between_requests: float = 1.0) -> Dict[str, Any]:
        """
        Sync non-synced products from database to API.
        
        Args:
            delay_between_requests: Delay in seconds between API requests
            
        Returns:
            Summary of sync operation
        """
        print("🚀 Starting product sync...")
        
        # Fetch non-synced products from database
        products = self.fetch_products_from_db()
        
        if not products:
            print("ℹ️  No new products to sync (all products already synced by this user)")
            return {"total": 0, "successful": 0, "failed": 0, "errors": []}
        
        # Track results
        results = {
            "total": len(products),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        # Process each product
        for i, product_data in enumerate(products, 1):
            product_id = product_data.get('product_id', 'Unknown')
            product_name = product_data.get('product_name', 'Unknown')
            print(f"\n📤 Processing product {i}/{len(products)}: {product_id} - {product_name}")
            
            # Create product via API
            api_result = self.create_product_via_api(product_data)
            
            if "error" in api_result:
                results["failed"] += 1
                results["errors"].append({
                    "product_id": product_id,
                    "product_name": product_name,
                    "error": api_result["error"]
                })
            else:
                results["successful"] += 1
                # Extract proc_id from successful API response
                proc_id = None
                if "result" in api_result and "proc_id" in api_result["result"]:
                    proc_id = api_result["result"]["proc_id"]
                    print(f"📋 Received proc_id: {proc_id}")
                
                # Mark as synced only if successful and proc_id is available
                if proc_id is not None:
                    self.sync_tracker.mark_as_synced(product_id, proc_id)
                    print(f"📝 Marked {product_id} as synced for {self.login} (proc_id: {proc_id})")
                else:
                    print(f"⚠️  No proc_id received for {product_id}, not marking as synced")
                    results["successful"] -= 1
                    results["failed"] += 1
                    results["errors"].append({
                        "product_id": product_id,
                        "product_name": product_name,
                        "error": "No proc_id in API response"
                    })
            
            # Add delay between requests to avoid overwhelming the API
            if i < len(products) and delay_between_requests > 0:
                print(f"⏳ Waiting {delay_between_requests}s before next request...")
                time.sleep(delay_between_requests)
        
        # Print summary
        print(f"\n📊 Sync Summary:")
        print(f"   Total products processed: {results['total']}")
        print(f"   Successful: {results['successful']}")
        print(f"   Failed: {results['failed']}")
        
        if results['errors']:
            print(f"   Errors:")
            for error in results['errors']:
                print(f"     - {error['product_id']} ({error['product_name']}): {error['error']}")
        
        return results

# Application entry point
def start_sync():
    # Get credentials from environment variables (GitHub secrets)
    login = os.getenv('XT_XARID_LOGIN')
    password = os.getenv('XT_XARID_PASSWORD')
    
    if not all([login, password]):
        raise ValueError("Missing required environment variables: XT_XARID_LOGIN, XT_XARID_PASSWORD")
    
    sync = ProductSync(
        api_base_url="https://api.xt-xarid.uz",
        login=login,
        password=password,
        client_id="af36f6cbc",  # Hardcoded client_id
        products_per_batch=1
    )
    results = sync.sync_products(delay_between_requests=10.0)
    print("Sync completed:", results)
    
if __name__ == "__main__":
    start_sync()
