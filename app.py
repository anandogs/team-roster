from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from datetime import datetime
from models import (
    FilterState,
    generate_sample_direct_costs,
    bu_to_customers, revenue_data
)
import pandas as pd

load_dotenv()

app = Flask(__name__)

_cached_rac_data = None
_cache_timestamp = None

def get_cached_rac_data():
    global _cached_rac_data, _cache_timestamp

    current_time = datetime.now()
    if (_cached_rac_data is None or _cache_timestamp is None or (current_time - _cache_timestamp).seconds > 3600):
        print("Loading freshRAC data...")
        _cached_rac_data = get_df()
        _cache_timestamp = current_time

    return _cached_rac_data

direct_costs = generate_sample_direct_costs()

# update revenue numbers
# at the app entry we want to get the users email and accordingly display the data. each user has certain customers they can access.

customer_list = [{'FinalCustomer': 'Sony India Software Centre Pvt Ltd', 'FinalBU': 'US TMTE'}, {'FinalCustomer': 'Aquent LLC', 'FinalBU': 'US TMTE'}]
customer_df = pd.DataFrame(customer_list)

def get_df():
    df = pd.read_csv('Q1FY2026.csv', low_memory=False)
    return df


def load_employees(customer_list: list | None = None):
    try:
        df = get_cached_rac_data()
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
        if customer_list:
            filtered_df = grouped_df[grouped_df['FinalCustomer'].isin(customer_list)].reset_index(drop=True)
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
    _,_,df = load_employees(customer_df['FinalCustomer'].to_list())
    return jsonify(df.to_dict(orient='records'))


@app.route('/api/employees', methods=['GET'])
def get_employees():
    """Get all employees data"""
    _,df,_ = load_employees(customer_df['FinalCustomer'].to_list())
    month = request.args.get('month')
    location = request.args.get('location')

    print(month)
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

    print(df_reduced.columns)

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
    df = get_cached_rac_data()
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