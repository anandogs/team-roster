from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from datetime import datetime
from models import (
    FilterState,
    generate_sample_direct_costs,
    bu_to_customers, 
)
import pandas as pd

load_dotenv()

app = Flask(__name__)

_cached_rac_data = None
_cached_revenue_data = None
_cached_plan_data = None
_cache_timestamp = None

def get_cached_data():
    global _cached_rac_data, _cache_timestamp

    current_time = datetime.now()
    if (_cached_rac_data is None or _cache_timestamp is None  or (current_time - _cache_timestamp).seconds > 3600):
        print("Loading fresh data...")
        _cached_rac_data = get_data()
        _cache_timestamp = current_time

    return _cached_rac_data

direct_costs = generate_sample_direct_costs()

customer_list = [{'PrismCustomerGroup': 'Sony', 'FinalBU': 'US TMTE'}, {'PrismCustomerGroup': 'Aquent', 'FinalBU': 'US TMTE'}]
customer_df = pd.DataFrame(customer_list)
max_quarter = 'Q1FY2026'

def get_data():
    cost = pd.read_csv('Q1FY2026.csv', low_memory=False)
    
    return cost

def load_employees(customer_list: list | None = None):
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
        print(df.head())
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
        
        print(customer_list)
        if customer_list:
            filtered_df = grouped_df[grouped_df['PrismCustomerGroup'].isin(customer_list)].reset_index(drop=True)
        else:
            filtered_df = grouped_df
        total_fte_idx = filtered_df.columns.get_loc('TotalFTECapped_M1')
        columns_to_drop = filtered_df.columns[total_fte_idx:]
        columns_to_drop = columns_to_drop.drop('id')
        filtered_df.drop(columns=columns_to_drop, inplace=True)
        without_ctc = grouped_df.drop(columns=columns_to_drop, inplace=False)
        return grouped_df, filtered_df, without_ctc
    except Exception as e:
        print(f"Error loading total employees: {str(e)}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def calculate_gm(filter_state: FilterState):
    current_gm = 60
    filtered_revenue = 100
    applicable_direct_costs = 0

    return {
        "currentGM": current_gm,
        "revenue": filtered_revenue,
        "directCosts": applicable_direct_costs
    }

def save_employee_data(df):
    """Save employee data back to storage"""
    try:
        df.to_csv('storage/employees.csv', index=False)
        return True
    except Exception as e:
        print(f"Error saving employee data: {str(e)}")
        return False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/total-employees')
def get_total_employees():
    """Get all possible employees (the pool)"""
    _,_,df = load_employees(customer_df['PrismCustomerGroup'].to_list())
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/gm-details')
def get_gm_details():
    """Get GM details for the portfolio of the user"""
    revenue = pd.read_csv('prism.csv', low_memory=False)
    plan = pd.read_csv('plan.csv', low_memory=False)
    odc = pd.read_csv('odc.csv', low_memory=False)
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
    filtered_plan_gm = merged_with_plan_gm[merged_with_plan_gm['Customer'].isin(customer_df['PrismCustomerGroup'].to_list())].reset_index(drop=True)
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

    return jsonify(with_odc.to_dict(orient='records'))

@app.route('/api/gm-impact', methods=['POST'])
def calculate_gm_impact():
    """Calculate GM impact for audit log entries"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        print("=== GM Impact Calculation ===")
        
        # Get the raw dataframe directly and process it ourselves
        df = get_cached_data()
        print(f"Raw dataframe shape: {df.shape}")
        
        if df.empty:
            return jsonify({'error': 'No data available in CSV file'}), 500
        
        # Initialize our lookup dictionaries
        employee_cpc_lookup = {}
        band_location_cpc_lookup = {}
        
        # Filter for the relevant columns we need
        relevant_columns = [
            'EmployeeCode', 'EmployeeName', 'Band', 'Offshore_Onsite', 
            'FinalBU', 'FinalCustomer', 'PrismCustomerGroup',
            'ProjectRole', 'Sub-Practice', 'Practice', 'BillableYN',
            'AllocationFTECapped_M1', 'AllocationFTECapped_M2', 'AllocationFTECapped_M3', 'AllocationFTECapped_QTR',
            'TotalFTECapped_M1', 'TotalFTECapped_M2', 'TotalFTECapped_M3', 'TotalFTECapped_QTR',
            'TotalCost_M1', 'TotalCost_M2', 'TotalCost_M3', 'TotalCost_QTR'
        ]
        
        # Check if all required columns exist
        missing_cols = [col for col in relevant_columns if col not in df.columns]
        if missing_cols:
            print(f"Missing columns: {missing_cols}")
            return jsonify({'error': f'Missing required columns: {missing_cols}'}), 500
        
        df_subset = df[relevant_columns].copy()
        
        # Group by employee-level columns to get aggregated data per employee
        grouping_columns = ['EmployeeCode', 'EmployeeName', 'Band', 'Offshore_Onsite', 
                           'FinalBU', 'FinalCustomer', 'PrismCustomerGroup', 
                           'ProjectRole', 'Sub-Practice', 'Practice', 'BillableYN']
        
        print("Grouping data by employee...")
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
        
        print(f"Grouped dataframe shape: {grouped_df.shape}")
        
        # Calculate CPC (Cost Per Capita) for each employee
        print("Calculating CPCs...")
        grouped_df['CPC_M1'] = grouped_df['TotalCost_M1'] / grouped_df['TotalFTECapped_M1'].replace(0, 1)
        grouped_df['CPC_M2'] = grouped_df['TotalCost_M2'] / grouped_df['TotalFTECapped_M2'].replace(0, 1)
        grouped_df['CPC_M3'] = grouped_df['TotalCost_M3'] / grouped_df['TotalFTECapped_M3'].replace(0, 1)
        grouped_df['CPC_QTR'] = grouped_df['TotalCost_QTR'] / grouped_df['TotalFTECapped_QTR'].replace(0, 1) / 3
        
        # Replace any infinite values with 0
        grouped_df = grouped_df.replace([float('inf'), float('-inf')], 0)
        
        # Build employee CPC lookup using EmployeeCode
        print("Building employee CPC lookup...")
        for _, row in grouped_df.iterrows():
            employee_code = str(int(row['EmployeeCode']))  # Convert to string for consistency
            cpc_qtr = row['CPC_QTR']
            employee_cpc_lookup[employee_code] = cpc_qtr
        
        # Build band + location CPC lookup for new hires
        print("Building band+location CPC lookup...")
        band_location_groups = grouped_df.groupby(['Band', 'Offshore_Onsite']).agg({
            'TotalCost_QTR': 'sum',
            'TotalFTECapped_QTR': 'sum'
        }).reset_index()
        
        for _, row in band_location_groups.iterrows():
            band = row['Band']
            location = row['Offshore_Onsite']
            total_cost = row['TotalCost_QTR']
            total_fte = row['TotalFTECapped_QTR']
            
            # Calculate average CPC for this band + location combination
            avg_cpc = (total_cost / total_fte / 3) if total_fte > 0 else 0
            key = f"{band}_{location}"
            band_location_cpc_lookup[key] = avg_cpc
        
        print(f"Employee CPC lookup entries: {len(employee_cpc_lookup)}")
        print(f"Band+Location CPC lookup entries: {len(band_location_cpc_lookup)}")
        
        # Sample some data for verification
        sample_employees = list(employee_cpc_lookup.items())[:5]
        print(f"Sample employee CPCs: {sample_employees}")
        
        sample_band_location = list(band_location_cpc_lookup.items())[:5]
        print(f"Sample band+location CPCs: {sample_band_location}")
        
        # Process the latest entry
        if 'latestEntry' in data:
            entry = data['latestEntry']
            gmData = entry.get('gmData', {})
            
            print(f"\n=== Processing Entry ===")
            print(f"Action: {entry.get('action')}")
            print(f"Employee: {entry.get('employeeName')}")
            print(f"FTE Change: {gmData.get('fteChange', 0)}")
            
            # Calculate GM impact
            cpc_used = 0
            lookup_method = ""
            
            if gmData.get('isNewHire', False):
                # For new hires, use band + location average CPC
                band = gmData.get('band', '')
                location = gmData.get('location', '')
                lookup_key = f"{band}_{location}"
                
                print(f"Looking up new hire CPC for: {lookup_key}")
                
                if lookup_key in band_location_cpc_lookup:
                    cpc_used = band_location_cpc_lookup[lookup_key]
                    lookup_method = f"band_location_avg ({lookup_key})"
                    print(f"Found Band+Location CPC: {cpc_used}")
                else:
                    print(f"No CPC found for {lookup_key}")
                    print(f"Available band+location keys: {list(band_location_cpc_lookup.keys())}")
                    # Use overall average as fallback
                    if band_location_cpc_lookup:
                        cpc_used = sum(band_location_cpc_lookup.values()) / len(band_location_cpc_lookup)
                        lookup_method = "fallback_avg"
                        print(f"Using fallback average CPC: {cpc_used}")
                    
            else:
                # For existing employees, use individual CPC
                employee_code = str(gmData.get('employeeCode', ''))
                print(f"Looking up employee CPC for: {employee_code}")
                
                if employee_code in employee_cpc_lookup:
                    cpc_used = employee_cpc_lookup[employee_code]
                    lookup_method = f"employee_specific ({employee_code})"
                    print(f"Found Employee CPC: {cpc_used}")
                else:
                    print(f"Employee code {employee_code} not found in lookup")
                    print(f"Sample lookup keys: {list(employee_cpc_lookup.keys())[:10]}")
                    
                    # Try to find the employee in the dataframe using .loc
                    try:
                        employee_code_int = int(employee_code)
                        matching_rows = grouped_df.loc[grouped_df['EmployeeCode'] == employee_code_int]
                        if not matching_rows.empty:
                            cpc_used = matching_rows.iloc[0]['CPC_QTR']
                            lookup_method = f"direct_lookup ({employee_code})"
                            print(f"Found CPC via direct lookup: {cpc_used}")
                        else:
                            print(f"No matching rows found for EmployeeCode {employee_code_int}")
                            cpc_used = 0
                            lookup_method = "not_found"
                    except ValueError:
                        print(f"Could not convert {employee_code} to integer")
                        cpc_used = 0
                        lookup_method = "conversion_error"
            
            # Calculate the GM impact
            fte_change = gmData.get('fteChange', 0)
            gm_impact = fte_change * cpc_used
            
            print(f"Final calculation: {fte_change} FTE * {cpc_used} CPC = {gm_impact}")
            print(f"Lookup method: {lookup_method}")
            
            # Add GM impact to the entry
            entry['gmImpact'] = {
                'cpcUsed': round(cpc_used, 2),
                'fteChange': round(fte_change, 2),
                'costImpact': round(gm_impact, 2),
                'calculationMethod': lookup_method
            }
        
        # Update the audit log with GM impact data
        updated_audit_log = data.get('auditLog', [])
        
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
        print(f"Error in GM impact calculation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/employees', methods=['GET'])
def get_employees():
    """Get all employees data"""
    _,df,_ = load_employees(customer_df['PrismCustomerGroup'].to_list())
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
    """Get customers for the user"""
    return jsonify(customer_df.to_dict(orient='records'))

@app.route('/api/period')
def get_period():
    """Get Quarter and Month names and numbers for filtering"""
    df = get_cached_data()
    current_quarter = df['Quarter'].unique()[0]
    period_dict = get_quarter_months(current_quarter)
    return period_dict



@app.route('/api/employees/<employee_id>', methods=['PATCH'])
def update_employee(employee_id):
    """Update employee FTE values"""
    try:
        _,df,_ = load_employees(customer_list)
        data = request.get_json()
        
        if employee_id not in df['EmployeeCode'].values:
            return jsonify({'error': 'Employee not found'}), 404
        
        mask = df['EmployeeCode'] == employee_id
        for key, value in data.items():
            if key.startswith('fte'):
                df.loc[mask, key] = float(value)
        
        df.loc[mask, 'fteQuarter'] = df.loc[mask, ['fteApril', 'fteMay', 'fteJune']].mean(axis=1).round(2)
        
        if save_employee_data(df):
            return jsonify(df[mask].to_dict(orient='records')[0])
        else:
            return jsonify({'error': 'Failed to save changes'}), 500
            
    except Exception as e:
        print(f"Error updating employee: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/direct-costs')
def get_direct_costs():
    return jsonify([c.model_dump() for c in direct_costs])

@app.route('/api/gm-state')
def get_gm_state():
    filter_state = FilterState(
        month=request.args.get('month', 'Quarter'),
        businessUnit=request.args.get('businessUnit', ''),
        customer=request.args.get('customer', ''),
        location=request.args.get('location', 'All'),
        billableStatus=request.args.get('billableStatus', 'All'),
        businessUnits=list(bu_to_customers.keys())
    )
    
    gm_data = calculate_gm(filter_state)
    
    return jsonify({
        "startingGM": 60,
        "currentGM": gm_data["currentGM"],
        "planGM": 65,
        "revenue": gm_data["revenue"],
        "directCosts": [c.dict() for c in direct_costs]
    })

@app.route('/api/filter-state')
def get_filter_state():
    return jsonify({
        "month": request.args.get('month', 'Quarter'),
        "businessUnit": request.args.get('businessUnit', ''),
        "customer": request.args.get('customer', ''),
        "location": request.args.get('location', 'All'),
        "billableStatus": request.args.get('billableStatus', 'All'),
        "businessUnits": list(bu_to_customers.keys())
    })

@app.route('/api/customers/<business_unit>')
def get_customers_by_bu(business_unit):
    return jsonify(bu_to_customers.get(business_unit, []))

@app.route('/templates/components/<template_name>.html')
def component_template(template_name):
    return render_template(f'components/{template_name}.html')

if __name__ == '__main__':
    app.run(debug=True) 