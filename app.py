import os
import io
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient

import logging
import json
from flask import Flask, render_template, jsonify, request, send_file
from dotenv import load_dotenv
from datetime import datetime
import pandas as pd

load_dotenv()

logging.basicConfig(level=logging.INFO)
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.WARNING)

app = Flask(__name__)

_cached_rac_data = None
_cache_timestamp = None

def get_credential():
    '''Get the credential based on the environment'''
    # Check if running in Azure (presence of IDENTITY_ENDPOINT environment variable)
    if "IDENTITY_ENDPOINT" in os.environ:
        return ManagedIdentityCredential()
    else:
        return AzureCliCredential()

def get_cached_data():
    global _cached_rac_data, _cache_timestamp

    current_time = datetime.now()
    if (_cached_rac_data is None or _cache_timestamp is None  or (current_time - _cache_timestamp).seconds > 3600):
        _cached_rac_data = get_data()
        _cache_timestamp = current_time

    return _cached_rac_data

_cached_permissions_data = None
_permissions_cache_timestamp = None

def get_cached_permissions():
    global _cached_permissions_data, _permissions_cache_timestamp

    current_time = datetime.now()
    if (_cached_permissions_data is None or _permissions_cache_timestamp is None or 
        (current_time - _permissions_cache_timestamp).seconds > 3600):
        _cached_permissions_data = load_user_permissions()
        _permissions_cache_timestamp = current_time

    return _cached_permissions_data

def get_user_bus():
    """Get the BUs accessible to current user based on permissions.csv"""
    user = get_current_user()
    user_email = user['email']
    
    if user_email == 'Unknown':
        return []  # Return empty list = no data shown
    
    try:
        permissions_df = get_cached_permissions()
        
        if permissions_df.empty:
            app.logger.warning("Permissions data is empty, no data will be shown")
            return []  # No data shown if permissions file unavailable
        
        # Find user's row (assuming columns are 'Email' and 'BU')
        user_row = permissions_df[permissions_df['Email'].str.lower() == user_email.lower()]
        
        if user_row.empty:
            app.logger.info(f"User {user_email} not found in permissions file, no data will be shown")
            return []  # User not in permissions = no data shown
        
        bu_value = user_row['BU'].iloc[0]
        
        # Handle 'All' case
        if bu_value == 'All':
            return None  # No filtering needed = show all data
        
        # Handle multiple BUs separated by commas
        if ',' in str(bu_value):
            bus = [bu.strip() for bu in str(bu_value).split(',')]
            return bus
        else:
            # Single BU
            return [str(bu_value).strip()]
            
    except Exception as e:
        app.logger.error(f"Error getting user BUs for {user_email}: {e}")
        return []  # Return empty list on error = no data shown

max_quarter = 'Q1FY2026'

def load_user_permissions():
    """Load user permissions from Azure storage"""
    try:
        account_url = "https://sonataonefpa.blob.core.windows.net/"
        container_name = "testpoccontainer"
        credential = get_credential()
        blob_service_client = BlobServiceClient(account_url, credential=credential)
        container_client = blob_service_client.get_container_client(container_name)
        
        # Download permissions.csv
        permissions_blob_client = container_client.get_blob_client("permissions.csv")
        permissions_download_stream = permissions_blob_client.download_blob()
        permissions_content = io.BytesIO(permissions_download_stream.readall())
        permissions_df = pd.read_csv(permissions_content, low_memory=False)
        
        return permissions_df
    except Exception as e:
        app.logger.error(f"Error loading permissions: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error


def get_current_user():
    if "IDENTITY_ENDPOINT" in os.environ:
        return {
            'email': request.headers.get('X-MS-CLIENT-PRINCIPAL-NAME', 'Unknown'),
        }

    else:
        return {
            'email': 'Anando.Ghose@sonata-software.com'
        }
    
    

def get_data():
    account_url = "https://sonataonefpa.blob.core.windows.net/"
    container_name = "rac-gm"
    credential = get_credential()
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    container_client = blob_service_client.get_container_client(container_name)
    
    # Download Q1FY2026.csv
    cost_blob_client = container_client.get_blob_client("cost/Q1FY2026.csv")
    cost_download_stream = cost_blob_client.download_blob()
    cost_content = io.BytesIO(cost_download_stream.readall())
    cost_df = pd.read_csv(cost_content, low_memory=False)
    
    return cost_df

def load_employees(bu_filter: list | None = None):
    try:
        df = get_cached_data()
        relevant_columns = [
            'EmployeeCode', 
            'EmployeeName',
            'Band',
            'Offshore_Onsite',
            'FinalBU', 
            'FinalCustomer',
            'PrismCustomerGroup',
            'ProjectRole',
            'Sub-Practice', 
            'Practice',
            'BillableYN',
            'AllocationFTECapped_M1',
            'AllocationFTECapped_M2',
            'AllocationFTECapped_M3',
            'AllocationFTECapped_QTR',
            'TotalFTECapped_M1',
            'TotalFTECapped_M2',
            'TotalFTECapped_M3',
            'TotalFTECapped_QTR',
            'TotalCost_M1',
            'TotalCost_M2',
            'TotalCost_M3',
            'TotalCost_QTR',
        ]
        df = df[relevant_columns]
        columns_to_concat = ['EmployeeCode', 'EmployeeName', 'Band', 'Offshore_Onsite', 
                     'FinalBU', 'FinalCustomer', 'PrismCustomerGroup', 
                     'ProjectRole', 'Sub-Practice', 'Practice', 'BillableYN']
        df.loc[:, 'BillableYN'] = df['BillableYN'].map({'Y': True, 'N': False})
        grouped_df = df.groupby(columns_to_concat).sum(numeric_only=True).reset_index()
        grouped_df['id'] = grouped_df[columns_to_concat].astype(str).agg(''.join, axis=1)
        grouped_df['CPC_M1'] = grouped_df['TotalCost_M1'] / grouped_df['TotalFTECapped_M1']
        grouped_df['CPC_M2'] = grouped_df['TotalCost_M2'] / grouped_df['TotalFTECapped_M2']
        grouped_df['CPC_M3'] = grouped_df['TotalCost_M3'] / grouped_df['TotalFTECapped_M3']
        grouped_df['CPC_QTR'] = grouped_df['TotalCost_QTR'] / grouped_df['TotalFTECapped_QTR'] / 3
        
        if bu_filter is None:
            filtered_df = grouped_df.copy()
        elif len(bu_filter) == 0:
            filtered_df = pd.DataFrame(columns=grouped_df.columns)
        else:
            filtered_df = grouped_df[grouped_df['FinalBU'].isin(bu_filter)].reset_index(drop=True)

        total_fte_idx = filtered_df.columns.get_loc('TotalFTECapped_M1')
        columns_to_drop = filtered_df.columns[total_fte_idx:]
        columns_to_drop = columns_to_drop.drop('id')
        filtered_df.drop(columns=columns_to_drop, inplace=True)
        without_ctc = grouped_df.drop(columns=columns_to_drop, inplace=False)
        return grouped_df, filtered_df, without_ctc
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()




@app.route('/api/download-roster-analysis', methods=['POST'])
def download_roster_analysis():
    import io
    from datetime import datetime
    
    # Get audit log and filters from POST data
    audit_log_data = request.form.get('audit_log', '[]')
    filters_data = request.form.get('filters', '{}')
    
    try:
        audit_log = json.loads(audit_log_data)
        filters = json.loads(filters_data)
    except:
        audit_log = []
        filters = {}
    
    # Get current roster data with filters applied
    user_bus = get_user_bus()
    _, df, _ = load_employees(user_bus)
    
    if df.empty:
        # Create empty file if no data
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame([{'Message': 'No data available'}]).to_excel(writer, sheet_name='Info', index=False)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name='roster-analysis-empty.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    # Apply filters to the data
    filtered_df = apply_filters_to_dataframe(df, filters)
    
    # Apply audit log to get current state
    roster_data = apply_audit_log_to_dataframe(filtered_df, audit_log)
    
    # Create Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Current Allocations - use actual column names
        allocations_df = roster_data[['EmployeeName', 'Band', 'FinalBU', 'PrismCustomerGroup', 
                                    'Offshore_Onsite', 'BillableYN']].copy()
        
        # Add FTE column (might be missing)
        if 'FTE' not in roster_data.columns:
            allocations_df['FTE'] = roster_data.get('AllocationFTECapped_QTR', 0)
        else:
            allocations_df['FTE'] = roster_data['FTE']
            
        allocations_df.columns = ['Employee Name', 'Band', 'Business Unit', 'Customer', 
                                'Location', 'Billable', 'Current FTE']
        allocations_df.to_excel(writer, sheet_name='Current Allocations', index=False)
        
        # Sheet 2: Changes Log (only if there are changes)
        if audit_log:
            changes_data = []
            for entry in audit_log:
                changes_data.append({
                    'Timestamp': entry.get('timestamp', ''),
                    'Action': entry.get('action', ''),
                    'Employee Name': entry.get('employeeName', ''),
                    'Old Value': entry.get('oldValue', ''),
                    'New Value': entry.get('newValue', ''),
                    'Description': entry.get('description', ''),
                    'GM Impact': entry.get('gmImpact', {}).get('costImpact', 0) if entry.get('gmImpact') else 0
                })
            changes_df = pd.DataFrame(changes_data)
            changes_df.to_excel(writer, sheet_name='Changes Log', index=False)
        else:
            # Create empty changes sheet
            pd.DataFrame([{'Message': 'No changes recorded'}]).to_excel(writer, sheet_name='Changes Log', index=False)
    
    output.seek(0)
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f'roster-analysis-{timestamp}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

def apply_filters_to_dataframe(df, filters):
    """Apply frontend filters to the dataframe"""
    filtered_df = df.copy()
    
    # Apply month filter
    month = filters.get('month', 'Quarter')
    if month != 'Quarter':
        # Set FTE column based on selected month
        month_col = f'AllocationFTECapped_{month}'
        if month_col in filtered_df.columns:
            filtered_df['FTE'] = filtered_df[month_col]
        else:
            filtered_df['FTE'] = filtered_df.get('AllocationFTECapped_QTR', 0)
    else:
        filtered_df['FTE'] = filtered_df.get('AllocationFTECapped_QTR', 0)
    
    # Apply business unit filter
    selected_bus = filters.get('selectedBusinessUnits', [])
    if selected_bus:
        filtered_df = filtered_df[filtered_df['FinalBU'].isin(selected_bus)]
    
    # Apply customer filter
    selected_customers = filters.get('selectedCustomers', [])
    if selected_customers:
        filtered_df = filtered_df[filtered_df['PrismCustomerGroup'].isin(selected_customers)]
    
    # Apply location filter
    selected_locations = filters.get('selectedLocations', [])
    if selected_locations:
        filtered_df = filtered_df[filtered_df['Offshore_Onsite'].isin(selected_locations)]
    
    # Apply billable status filter
    selected_billable = filters.get('selectedBillableStatus', [])
    if selected_billable:
        # Convert boolean to Y/N for comparison
        if 'Y' in selected_billable and 'N' not in selected_billable:
            filtered_df = filtered_df[filtered_df['BillableYN'] == True]
        elif 'N' in selected_billable and 'Y' not in selected_billable:
            filtered_df = filtered_df[filtered_df['BillableYN'] == False]
        # If both Y and N are selected, don't filter
    
    return filtered_df.reset_index(drop=True)

def apply_audit_log_to_dataframe(df, audit_log):
    # Convert to list of dicts for easier manipulation
    result = df.to_dict('records')
    
    for entry in audit_log:
        if entry['action'] == 'EDIT_FTE':
            for row in result:
                if row['id'] == entry['employeeId']:
                    row['FTE'] = float(entry['newValue'])
        elif entry['action'] == 'REMOVE_EMPLOYEE':
            result = [row for row in result if row['id'] != entry['employeeId']]
        elif entry['action'] == 'ADD_EMPLOYEE' and 'employeeData' in entry:
            result.append(entry['employeeData'])
    
    return pd.DataFrame(result)

@app.route('/')
def home():
    user = get_current_user()
    app.logger.info(f"USER ACCESS - Name: {user['email']}")
    return render_template('index.html')

@app.route('/api/total-employees')
def get_total_employees():
    """Get all possible employees (the pool)"""
    user_bus = get_user_bus()
    _,_,df = load_employees(user_bus)
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/gm-details')
def get_gm_details():
    """Get GM details for the portfolio of the user"""
    # Download from Azure Blob Storage
    account_url = "https://sonataonefpa.blob.core.windows.net/"
    container_name = "testpoccontainer"
    credential = get_credential()
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    container_client = blob_service_client.get_container_client(container_name)

    # Download prism.csv
    prism_blob_client = container_client.get_blob_client("prism.csv")
    prism_download_stream = prism_blob_client.download_blob()
    prism_content = io.BytesIO(prism_download_stream.readall())
    revenue = pd.read_csv(prism_content, low_memory=False)

    # Download plan.csv
    plan_blob_client = container_client.get_blob_client("plan.csv")
    plan_download_stream = plan_blob_client.download_blob()
    plan_content = io.BytesIO(plan_download_stream.readall())
    plan = pd.read_csv(plan_content, low_memory=False)

    # Download odc.csv
    odc_blob_client = container_client.get_blob_client("odc.csv")
    odc_download_stream = odc_blob_client.download_blob()
    odc_content = io.BytesIO(odc_download_stream.readall())
    odc = pd.read_csv(odc_content, low_memory=False)
    cost = get_cached_data()


    quarter_formatted = max_quarter[:2]
    filtered_revenue = revenue[revenue['Quarter'] == quarter_formatted].reset_index(drop=True)
    filtered_plan = plan[plan['Quarter'] == quarter_formatted].reset_index(drop=True)
    filtered_plan.drop(columns=['Customer'], inplace=True)
    filtered_plan.rename(columns={'Prism': 'Customer'}, inplace=True)
    grouped_filtered_plan = filtered_plan.groupby(['BU', 'Customer']).sum().reset_index()
    grouped_filtered_plan['PlanGM%'] = (grouped_filtered_plan['PlanRevenue'] - grouped_filtered_plan['PlanCost']) / grouped_filtered_plan['PlanRevenue']
    grouped_filtered_plan['PlanGM%'] = grouped_filtered_plan['PlanGM%'].fillna(0)
    grouped_filtered_plan.drop(columns=['PlanCost', 'Quarter', 'RAC'], inplace=True)
    filtered_revenue.rename(columns={'Title': 'Customer'}, inplace=True)
    merged_with_plan_gm = pd.merge(filtered_revenue, grouped_filtered_plan, on='Customer', how='left')
    user_bus = get_user_bus()

    if user_bus is None:
        # User has 'All' access - no filtering
        filtered_plan_gm = merged_with_plan_gm.copy()
    elif len(user_bus) == 0:
        # User not in permissions - show no data
        filtered_plan_gm = pd.DataFrame(columns=merged_with_plan_gm.columns)
    else:
        # User has specific BU access
        filtered_plan_gm = merged_with_plan_gm[merged_with_plan_gm['BU'].isin(user_bus)].reset_index(drop=True)

    filtered_plan_gm.drop(columns=['FinancialYear'], inplace=True)

    grouped_gm = cost.groupby(['FinalBU', 'PrismCustomerGroup'])[
        [
            'AllocationCost_M1',
            'AllocationCost_M2',
            'AllocationCost_M3',
        ]
    ].sum().reset_index()

    melted_gm = grouped_gm.melt(
        id_vars=['FinalBU', 'PrismCustomerGroup'],
        value_vars=['AllocationCost_M1', 'AllocationCost_M2', 'AllocationCost_M3'],
        var_name='Month',
        value_name='AllocationCost'
    )
    # Convert 'Month' from 'AllocationCost_M1' to 'M1', etc.
    melted_gm['Month'] = melted_gm['Month'].str.extract(r'AllocationCost_(M\d)')
    month_map = get_quarter_months(max_quarter)
    melted_gm['MonthName'] = melted_gm['Month'].map(month_map)
    melted_gm['Month'] = melted_gm['MonthName'].str.split(' ').str[0]
    melted_gm.drop(columns=['MonthName'], inplace=True)
    melted_gm.rename(columns={'PrismCustomerGroup': 'Customer', 'FinalBU': 'BU'}, inplace=True)
    with_allocation_cost = pd.merge(
        filtered_plan_gm, melted_gm, on=['BU', 'Customer', 'Month'], how='left'
    )
    with_odc = pd.merge(
        with_allocation_cost, odc, on='BU', how='left'
    )
    with_odc['OtherDirectCosts'] = with_odc['Total_Revenue'] * with_odc['ODC']
    with_odc.drop(columns=['ODC'], inplace=True)
    with_odc = with_odc.fillna(0)
    with_odc = with_odc.replace([float('inf'), float('-inf')], 0)

    return jsonify(with_odc.to_dict(orient='records'))

@app.route('/api/gm-impact', methods=['POST'])
def calculate_gm_impact():
    """Calculate GM impact for audit log entries"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        df = get_cached_data()
        
        if df.empty:
            return jsonify({'error': 'No data available in CSV file'}), 500
        
        employee_cpc_lookup = {}
        band_location_cpc_lookup = {}
        
        relevant_columns = [
            'EmployeeCode', 'EmployeeName', 'Band', 'Offshore_Onsite', 
            'FinalBU', 'FinalCustomer', 'PrismCustomerGroup',
            'ProjectRole', 'Sub-Practice', 'Practice', 'BillableYN',
            'AllocationFTECapped_M1', 'AllocationFTECapped_M2', 'AllocationFTECapped_M3', 'AllocationFTECapped_QTR',
            'TotalFTECapped_M1', 'TotalFTECapped_M2', 'TotalFTECapped_M3', 'TotalFTECapped_QTR',
            'TotalCost_M1', 'TotalCost_M2', 'TotalCost_M3', 'TotalCost_QTR'
        ]
        
        missing_cols = [col for col in relevant_columns if col not in df.columns]
        if missing_cols:
            return jsonify({'error': f'Missing required columns: {missing_cols}'}), 500
        
        df_subset = df[relevant_columns].copy()
        
        grouping_columns = ['EmployeeCode', 'EmployeeName', 'Band', 'Offshore_Onsite', 
                           'FinalBU', 'FinalCustomer', 'PrismCustomerGroup', 
                           'ProjectRole', 'Sub-Practice', 'Practice', 'BillableYN']
        
        grouped_df = df_subset.groupby(grouping_columns).agg({
            'AllocationFTECapped_M1': 'sum',
            'AllocationFTECapped_M2': 'sum', 
            'AllocationFTECapped_M3': 'sum',
            'AllocationFTECapped_QTR': 'sum',
            'TotalFTECapped_M1': 'sum',
            'TotalFTECapped_M2': 'sum',
            'TotalFTECapped_M3': 'sum', 
            'TotalFTECapped_QTR': 'sum',
            'TotalCost_M1': 'sum',
            'TotalCost_M2': 'sum',
            'TotalCost_M3': 'sum',
            'TotalCost_QTR': 'sum'
        }).reset_index()
        
        grouped_df['CPC_M1'] = grouped_df['TotalCost_M1'] / grouped_df['TotalFTECapped_M1'].replace(0, 1)
        grouped_df['CPC_M2'] = grouped_df['TotalCost_M2'] / grouped_df['TotalFTECapped_M2'].replace(0, 1)
        grouped_df['CPC_M3'] = grouped_df['TotalCost_M3'] / grouped_df['TotalFTECapped_M3'].replace(0, 1)
        grouped_df['CPC_QTR'] = grouped_df['TotalCost_QTR'] / grouped_df['TotalFTECapped_QTR'].replace(0, 1) / 3
        
        grouped_df = grouped_df.replace([float('inf'), float('-inf')], 0)
        
        for _, row in grouped_df.iterrows():
            employee_code = str(int(row['EmployeeCode']))  # Convert to string for consistency
            cpc_qtr = row['CPC_QTR']
            employee_cpc_lookup[employee_code] = cpc_qtr
        
        band_location_groups = grouped_df.groupby(['Band', 'Offshore_Onsite']).agg({
            'TotalCost_QTR': 'sum',
            'TotalFTECapped_QTR': 'sum'
        }).reset_index()
        
        for _, row in band_location_groups.iterrows():
            band = row['Band']
            location = row['Offshore_Onsite']
            total_cost = row['TotalCost_QTR']
            total_fte = row['TotalFTECapped_QTR']
            
            avg_cpc = (total_cost / total_fte / 3) if total_fte > 0 else 0
            key = f"{band}_{location}"
            band_location_cpc_lookup[key] = avg_cpc
        
        entry = None  # Ensure entry is always defined
        if 'latestEntry' in data:
            entry = data['latestEntry']
            gmData = entry.get('gmData', {})
            
            # Calculate GM impact
            cpc_used = 0
            lookup_method = ""
            
            if gmData.get('isNewHire', False):
                # For new hires, use band + location average CPC
                band = gmData.get('band', '')
                location = gmData.get('location', '')
                lookup_key = f"{band}_{location}"
                
                
                if lookup_key in band_location_cpc_lookup:
                    cpc_used = band_location_cpc_lookup[lookup_key]
                    lookup_method = f"band_location_avg ({lookup_key})"
                else:
                    # Use overall average as fallback
                    if band_location_cpc_lookup:
                        cpc_used = sum(band_location_cpc_lookup.values()) / len(band_location_cpc_lookup)
                        lookup_method = "fallback_avg"
                    
            else:
                # For existing employees, use individual CPC
                employee_code = str(gmData.get('employeeCode', ''))
                
                if employee_code in employee_cpc_lookup:
                    cpc_used = employee_cpc_lookup[employee_code]
                    lookup_method = f"employee_specific ({employee_code})"
                else:
                    try:
                        employee_code_int = int(employee_code)
                        matching_rows = grouped_df.loc[grouped_df['EmployeeCode'] == employee_code_int]
                        if not matching_rows.empty:
                            cpc_used = matching_rows.iloc[0]['CPC_QTR']
                            lookup_method = f"direct_lookup ({employee_code})"
                        else:
                            cpc_used = 0
                            lookup_method = "not_found"
                    except ValueError:
                        cpc_used = 0
                        lookup_method = "conversion_error"
            
            # Calculate the GM impact
            fte_change = gmData.get('fteChange', 0)
            gm_impact = fte_change * cpc_used
            
            # Add GM impact to the entry
            entry['gmImpact'] = {
                'cpcUsed': round(cpc_used, 2),
                'fteChange': round(fte_change, 2),
                'costImpact': round(gm_impact, 2),
                'calculationMethod': lookup_method
            }
        
        # Update the audit log with GM impact data
        updated_audit_log = data.get('auditLog', [])

        if entry is not None:
            for log_entry in updated_audit_log:
                if log_entry.get('id') == entry.get('id'):
                    log_entry['gmImpact'] = entry['gmImpact']
                    break
        
        return jsonify({
            'success': True,
            'auditLog': updated_audit_log,
            'message': 'GM impact calculation completed',
            'debug': {
                'employee_cpc_count': len(employee_cpc_lookup),
                'band_location_cpc_count': len(band_location_cpc_lookup)
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/employees', methods=['GET'])
def get_employees():
    """Get all employees data"""
    user_bus = get_user_bus()
    _,df,_ = load_employees(user_bus)
    month = request.args.get('month')
    location = request.args.get('location')

    fte_cols = ['AllocationFTECapped_M1', 'AllocationFTECapped_M2', 'AllocationFTECapped_M3',  'AllocationFTECapped_QTR'] 
    if month == None or month == 'Quarter': # the page just loaded, and it defaults to quarter FTE
        fte_cols_without_month = [col for col in fte_cols if col != 'AllocationFTECapped_QTR']
        df_reduced = df.drop(columns=fte_cols_without_month)
        df_reduced.rename(columns={'AllocationFTECapped_QTR': 'FTE'}, inplace=True)
        df_reduced['FTE'] = df_reduced['FTE'].round(2)
    else:
        month_col = f'AllocationFTECapped_{month}'
        df_reduced = df.drop(columns=[col for col in fte_cols if col != month_col])
        df_reduced.rename(columns={month_col: 'FTE'}, inplace=True)
        df_reduced['FTE'] = df_reduced['FTE'].round(2)
    
    if location == None or location == 'All':
        pass
    else:
        df_reduced = df_reduced[df_reduced['Offshore_Onsite'] == location].reset_index(drop=True)

    return jsonify(df_reduced.to_dict(orient='records'))


def get_quarter_months(fiscal_quarter):
   """Convert 'Q1FY2026' to {'M1': 'Apr 25', 'M2': 'May 25', 'M3': 'Jun 25', 'QTR': 'Q1FY2026'}"""
   
   quarter = fiscal_quarter[:2]
   fy_year = int(fiscal_quarter[4:])
   
   quarters = {
       'Q1': [4, 5, 6], 'Q2': [7, 8, 9], 
       'Q3': [10, 11, 12], 'Q4': [1, 2, 3]
   }
   
   months = quarters[quarter]
   cal_year = fy_year if quarter == 'Q4' else fy_year - 1
   
   result = {f'M{i+1}': datetime(cal_year, month, 1).strftime("%b %y") 
             for i, month in enumerate(months)}
   result['QTR'] = fiscal_quarter
   
   return result

@app.route('/api/customers')
def get_customers():
    """Get customers for the user based on their BU access"""
    user_bus = get_user_bus()
    df = get_cached_data()
    
    if user_bus is None:
        # User has 'All' access
        filtered_df = df.copy()
    elif len(user_bus) == 0:
        # User not in permissions - return empty
        return jsonify([])
    else:
        # User has specific BU access
        filtered_df = df[df['FinalBU'].isin(user_bus)]
    
    # Get unique customers for the accessible BUs
    unique_customers = filtered_df[['PrismCustomerGroup', 'FinalBU']].drop_duplicates()
    return jsonify(unique_customers.to_dict(orient='records'))

@app.route('/api/period')
def get_period():
    """Get Quarter and Month names and numbers for filtering"""
    df = get_cached_data()
    current_quarter = df['Quarter'].unique()[0]
    period_dict = get_quarter_months(current_quarter)
    return period_dict

if __name__ == '__main__':
    app.run(debug=True) 