import requests
import urllib3
import time
from typing import Dict, Any, Optional

# Suppress SSL warnings when verify_ssl=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class APIClient:
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {}
        self.verify_ssl = verify_ssl
        self.access_token = None
        self.refresh_token_value = None
        self.token_expires_at = None
        self.client_id = None
        
        # Set default headers for JSON-RPC
        if 'Content-Type' not in self.headers:
            self.headers['Content-Type'] = 'application/json'

    def _is_token_expired(self) -> bool:
        """Check if the current access token is expired."""
        if not self.token_expires_at:
            return True
        return time.time() >= self.token_expires_at

    def _auto_refresh_token(self):
        """Automatically refresh token if it's expired."""
        if self._is_token_expired() and self.refresh_token_value and self.client_id:
            print("🔄 Token expired, auto-refreshing...")
            self.refresh_token(self.refresh_token_value, self.client_id)

    def send_request(self, endpoint: str, payload: Dict[str, Any], use_auth: bool = False) -> Dict[str, Any]:
        """Send JSON-RPC request and return response."""
        # Auto-refresh token if needed for authenticated requests
        if use_auth:
            self._auto_refresh_token()
            
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Prepare headers
        headers = self.headers.copy()
        if use_auth and self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        
        try:
            response = requests.post(
                url, 
                json=payload, 
                headers=headers, 
                verify=self.verify_ssl
            )
            
            print(f"📤 Sent to {url}:", payload)
            print(f"📥 Received ({response.status_code}):", response.text)
            
            if response.status_code >= 400:
                raise Exception(f"API Error {response.status_code}: {response.text}")
                
            return response.json()
                    
        except requests.RequestException as e:
            print(f"❌ Request failed: {e}")
            raise

    def auth_token(self, login: str, password: str, client_id: str) -> Dict[str, Any]:
        """Authenticate and get token."""
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "token",
            "params": {
                "grant_type": "password",
                "login": login,
                "password": password,
                "client_id": client_id
            }
        }
        response = self.send_request("/auth", payload)
        
        # Store tokens and expiration info for automatic refresh
        if 'result' in response and 'access_token' in response['result']:
            self.access_token = response['result']['access_token']
            self.refresh_token_value = response['result']['refresh_token']
            self.client_id = client_id
            
            # Calculate expiration time (expires_in is in seconds)
            expires_in = response['result'].get('expires_in', 10)
            self.token_expires_at = time.time() + expires_in - 5  # Refresh 5 seconds early
            
            print(f"✅ Access token stored (expires in {expires_in}s)")
        
        return response

    def refresh_token(self, refresh_token: str, client_id: str) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "token",
            "params": {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id
            }
        }
        response = self.send_request("/auth", payload)
        
        # Store the new tokens and expiration info
        if 'result' in response and 'access_token' in response['result']:
            self.access_token = response['result']['access_token']
            self.refresh_token_value = response['result']['refresh_token']
            self.client_id = client_id
            
            # Calculate new expiration time
            expires_in = response['result'].get('expires_in', 10)
            self.token_expires_at = time.time() + expires_in - 5  # Refresh 5 seconds early
            
            print(f"✅ Access token refreshed (expires in {expires_in}s)")
        
        return response

    def get_face_users(self) -> Dict[str, Any]:
        """Get face users (requires authentication)."""
        if not self.access_token and not self.refresh_token_value:
            raise Exception("No access token available. Call auth_token() first.")
            
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "get_face_users",
            "params": {}
        }
        return self.send_request("/rpc", payload, use_auth=True)

    def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new product (requires authentication)."""
        if not self.access_token and not self.refresh_token_value:
            raise Exception("No access token available. Call auth_token() first.")
            
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "create_procedure",
            "params": {
                "type": "ad",
                "product": product_data
            }
        }
        return self.send_request("/urpc", payload, use_auth=True)