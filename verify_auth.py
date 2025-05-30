import requests
import msal
import json
from dotenv import load_dotenv
import os


def get_access_token(tenant_id, client_id, client_secret):
    """
    Get an access token for Microsoft Graph API using MSAL with detailed debugging
    """
    print("\n=== Getting Access Token ===")
    print(f"Tenant ID: {tenant_id}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {'*' * 5}")  # Never print actual secrets
    
    # Authority URL for authentication
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    print(f"Authority URL: {authority}")
    
    # Create a confidential client application
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )
    
    # The scope ".default" means "all the permissions the app has been granted"
    scopes = ["https://graph.microsoft.com/.default"]
    print(f"Requesting scopes: {scopes}")
    
    result = app.acquire_token_for_client(scopes=scopes)
    
    if "access_token" in result:
        print("✓ Successfully acquired access token")
        token_preview = result["access_token"][:10] + "..." if result["access_token"] else "None"
        print(f"Token starts with: {token_preview}")
        
        return result["access_token"]
    else:
        error = result.get("error", "unknown error")
        error_description = result.get("error_description", "No error description")
        print(f"✗ Error: {error}")
        print(f"Error description: {error_description}")
        
        return None

def test_endpoints(access_token):
    """
    Test various endpoints to diagnose permission issues
    """
    if not access_token:
        print("No access token available for testing")
        return
    
    print("\n=== Testing Various Endpoints ===")
    
    # Microsoft Graph API endpoint
    graph_url = "https://graph.microsoft.com/v1.0"
    
    # Headers for all requests
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    # Test 1: Get /me - This should fail with app-only permissions
    print("\nTest 1: Testing /me endpoint (should fail with app permissions)")
    me_url = f"{graph_url}/me"
    me_response = requests.get(me_url, headers=headers)
    print(f"Status code: {me_response.status_code}")
    print(f"Response: {me_response.text[:200]}...")  # Print first 200 chars
    
    # Test 2: List sites (should work with Sites.Read.All permission)
    print("\nTest 2: Testing /sites endpoint")
    sites_url = f"{graph_url}/sites?$top=5"
    sites_response = requests.get(sites_url, headers=headers)
    print(f"Status code: {sites_response.status_code}")
    if sites_response.status_code == 200:
        sites_data = sites_response.json()
        sites_count = len(sites_data.get("value", []))
        print(f"Found {sites_count} sites")
        if sites_count > 0:
            print("First site name:", sites_data["value"][0].get("displayName", "Unknown"))
    else:
        print(f"Response: {sites_response.text[:200]}...")  # Print first 200 chars
    
    # Test 3: Get specific site by domain and relative path
    print("\nTest 3: Testing specific site (FinanceITTeam)")
    site_domain = "o365sonata.sharepoint.com"
    site_path = "sites/FinanceITTeam"
    site_url = f"{graph_url}/sites/{site_domain}:/{site_path}"
    print(f"Requesting URL: {site_url}")
    
    site_response = requests.get(site_url, headers=headers)
    print(f"Status code: {site_response.status_code}")
    if site_response.status_code == 200:
        site_data = site_response.json()
        print(f"Site name: {site_data.get('displayName', 'Unknown')}")
        print(f"Site ID: {site_data.get('id', 'Unknown')}")
    else:
        print(f"Response: {site_response.text[:200]}...")  # Print first 200 chars
    
    # Test 4: Alternative method for site access
    print("\nTest 4: Testing alternative site access method")
    alt_site_url = f"{graph_url}/sites/{site_domain}/sites/{site_path.split('/')[-1]}"
    print(f"Requesting URL: {alt_site_url}")
    
    alt_site_response = requests.get(alt_site_url, headers=headers)
    print(f"Status code: {alt_site_response.status_code}")
    if alt_site_response.status_code == 200:
        alt_site_data = alt_site_response.json()
        print(f"Site name: {alt_site_data.get('displayName', 'Unknown')}")
        print(f"Site ID: {alt_site_data.get('id', 'Unknown')}")
    else:
        print(f"Response: {alt_site_response.text[:200]}...")  # Print first 200 chars

def main():
    print("=== SharePoint Authentication Verification ===")
    print("This script will test your app registration credentials with SharePoint\n")
    
    load_dotenv()
    client_id = os.getenv("CLIENT_ID")
    tenant_id = os.getenv("TENANT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    # Get access token
    access_token = get_access_token(tenant_id, client_id, client_secret)
    
    if access_token:
        # Test various endpoints
        test_endpoints(access_token)
        
        print("\n=== Troubleshooting Tips ===")
        print("1. If all tests failed with 401 errors: Your access token is invalid or expired.")
        print("   - Check your tenant ID, client ID, and client secret")
        print("   - Ensure your app registration is properly configured")
        
        print("\n2. If Test 1 failed but others worked: This is expected with app-only permissions")
        
        print("\n3. If Test 2 worked but Tests 3-4 failed: You have permission to list sites but not")
        print("   access the specific site. This could be because:")
        print("   - Your app may not have been granted access to that specific site")
        print("   - The site path might be incorrect")
        print("   - You might need additional permissions (e.g., Sites.ReadWrite.All)")
        
        print("\n4. Required permissions for SharePoint access:")
        print("   - Sites.Read.All: For reading all sites")
        print("   - Sites.ReadWrite.All: For reading and writing to sites")
        
        print("\nFor accessing site collections, ensure your app has Admin Consent for the permissions")
    else:
        print("\n=== Authentication Failed ===")
        print("Failed to obtain an access token. Please check your credentials and try again.")

if __name__ == "__main__":
    main()