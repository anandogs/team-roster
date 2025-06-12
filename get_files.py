import msal
import requests
import pandas as pd
import time
import json

def main():
    # Azure AD details
    tenant_id = "7571a489-bd29-4f38-b9a6-7c880f8cddf0"
    client_id = "6d9e48da-c659-4f2a-891c-75f943a8dca9"
    authority = f"https://login.microsoftonline.com/{tenant_id}"

    # SharePoint site and list details
    site_url = "o365sonata.sharepoint.com:/sites/PrismRebuild"
    list_id = "4dcd6680-b9a1-444f-9519-3d8f5011e6e7"

    # Initialize MSAL client
    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority
    )

    # Required scopes for SharePoint list access
    scopes = [
        'Sites.Read.All',
        'Sites.ReadWrite.All'  # Include if you need write access
    ]

    # Use device code flow with timeout
    flow = app.initiate_device_flow(scopes)
    if "user_code" in flow:
        print('\n\n=== AUTHENTICATION REQUIRED ===')
        print('To sign in, use a web browser to open the page https://microsoft.com/devicelogin')
        print('and enter the code', flow['user_code'])
        print('Waiting for you to complete the authentication...')
        
        # Add timeout and polling
        max_time = 300  # 5 minutes timeout
        start_time = time.time()
        
        while time.time() - start_time < max_time:
            try:
                result = app.acquire_token_by_device_flow(flow, timeout=5)  # 5 seconds timeout per attempt
                if result and "access_token" in result:
                    break
            except Exception as e:
                print(f"Polling error: {e}")
            print("Still waiting for authentication... Please complete the device code flow in your browser.")
            time.sleep(5)  # Wait 5 seconds before trying again
        
        if "access_token" in result:
            print("✓ Successfully acquired token!")
            access_token = result["access_token"]
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # Verify access to the site
            print(f"\n=== Verifying access to site {site_url} ===")
            site_response = requests.get(
                f'https://graph.microsoft.com/v1.0/sites/{site_url}',
                headers=headers
            )
            
            if site_response.status_code == 200:
                site_data = site_response.json()
                site_id = site_data['id']
                print(f"✓ Successfully connected to site: {site_data.get('displayName')}")
                print(f"  Site ID: {site_id}")
                
                # Get list data
                print(f"\n=== Retrieving data from list {list_id} ===")
                list_response = requests.get(
                    f'https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?$expand=fields',
                    headers=headers
                )
                
                if list_response.status_code == 200:
                    list_data = list_response.json()
                    items = list_data.get('value', [])
                    
                    # Handle pagination if there are more items
                    while '@odata.nextLink' in list_data:
                        next_page_url = list_data['@odata.nextLink']
                        print(f"  Retrieving next page of items...")
                        next_page_response = requests.get(next_page_url, headers=headers)
                        
                        if next_page_response.status_code == 200:
                            next_page_data = next_page_response.json()
                            items.extend(next_page_data.get('value', []))
                            list_data = next_page_data
                        else:
                            print(f"  Error retrieving next page: {next_page_response.status_code}")
                            print(f"  {next_page_response.text}")
                            break
                    
                    print(f"✓ Retrieved {len(items)} items from the list")
                    
                    # Process the items - extract fields
                    processed_items = []
                    for item in items:
                        fields = item.get('fields', {})
                        # Remove @odata type information from field names
                        cleaned_fields = {
                            k.split('@')[0]: v for k, v in fields.items()
                        }
                        processed_items.append(cleaned_fields)
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(processed_items)
                    
                    # Display sample of data
                    print("\n=== Data Sample (First 5 rows) ===")
                    print(df.head())
                    
                    # Save to Excel
                    output_file = "sharepoint_list_data.xlsx"
                    df.to_excel(output_file, index=False)
                    print(f"\n✓ Data saved to {output_file}")
                    
                    # Return info about retrieved data
                    print("\n=== Data Information ===")
                    print(f"  Number of rows: {len(df)}")
                    print(f"  Number of columns: {len(df.columns)}")
                    print("\n  Columns:")
                    for col in df.columns:
                        print(f"    - {col}")
                    
                    # Optional: Save to CSV as well
                    df.to_csv("sharepoint_list_data.csv", index=False)
                    print(f"✓ Data also saved to sharepoint_list_data.csv")
                    
                else:
                    print(f"✗ Error retrieving list data: {list_response.status_code}")
                    print(f"  Response: {list_response.text}")
            else:
                print(f"✗ Error accessing site: {site_response.status_code}")
                print(f"  Response: {site_response.text}")
        else:
            print("✗ Failed to get token within timeout period")
            print(f"  Error getting token: {result.get('error')}")
            print(f"  Error description: {result.get('error_description')}")
    else:
        print("✗ Error initiating device flow")
        print(f"  Error: {flow.get('error')}")
        print(f"  Error description: {flow.get('error_description')}")

if __name__ == "__main__":
    main()