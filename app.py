from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from models import (
    Employee, DirectCost, GMState, FilterState,
    generate_sample_employees, generate_sample_direct_costs,
    bu_to_customers, revenue_data
)
import json
from datetime import datetime
import pandas as pd

load_dotenv()

app = Flask(__name__)

# Initialize sample data
employees = generate_sample_employees()
direct_costs = generate_sample_direct_costs()


def load_total_employees():
    try:
        df = pd.read_csv('storage/total_employees.csv')
        return df
    except Exception as e:
        print(f"Error loading total employees: {str(e)}")
        return pd.DataFrame()

# Load employee data from JSON file
def load_employees():
    try:
        with open('data/employees.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Save employee data to JSON file
def save_employees(employees):
    with open('data/employees.json', 'w') as f:
        json.dump(employees, f, indent=4)

def calculate_gm(filter_state: FilterState):
    # Filter employees based on current filters
    filtered_employees = employees.copy()
    
    if filter_state.businessUnit:
        filtered_employees = [e for e in filtered_employees if e.businessUnit == filter_state.businessUnit]
        if filter_state.customer:
            filtered_employees = [e for e in filtered_employees if e.customer == filter_state.customer]
    
    if filter_state.location != "All":
        filtered_employees = [e for e in filtered_employees if e.location == filter_state.location]
    
    if filter_state.billableStatus == "Billable":
        filtered_employees = [e for e in filtered_employees if e.billable]
    elif filter_state.billableStatus == "Non-Billable":
        filtered_employees = [e for e in filtered_employees if not e.billable]
    
    # Calculate FTE based on selected month
    def get_current_fte(employee: Employee) -> float:
        if filter_state.month == "April":
            return employee.fteApril
        elif filter_state.month == "May":
            return employee.fteMay
        elif filter_state.month == "June":
            return employee.fteJune
        else:  # Quarter
            return employee.fteQuarter
    
    # Calculate weighted FTE
    band_weights = {
        "Junior": 1,
        "Mid-level": 0.9,
        "Senior": 0.8,
        "Principal": 0.7
    }
    
    total_fte = sum(get_current_fte(e) for e in filtered_employees)
    weighted_fte = sum(get_current_fte(e) * band_weights.get(e.band, 1) for e in filtered_employees)
    
    # Calculate revenue based on filters
    filtered_revenue = revenue_data["overall"]
    if filter_state.customer:
        filtered_revenue = revenue_data.get(filter_state.customer, 0)
    elif filter_state.businessUnit:
        filtered_revenue = revenue_data.get(filter_state.businessUnit, 0)
    
    # Calculate applicable direct costs
    applicable_direct_costs = 0
    for cost in direct_costs:
        if cost.level == "Overall":
            applicable_direct_costs += cost.amount
        elif cost.level == "Business Unit" and cost.businessUnit:
            if (filter_state.businessUnit == cost.businessUnit or
                (filter_state.customer and filter_state.customer in bu_to_customers.get(cost.businessUnit, []))):
                applicable_direct_costs += cost.amount
        elif cost.level == "Customer" and cost.customer:
            if filter_state.customer == cost.customer:
                applicable_direct_costs += cost.amount
    
    # Calculate GM percentage
    base_gm = 60
    fte_impact = (weighted_fte / total_fte * 5) if total_fte > 0 else 0
    direct_cost_impact = (applicable_direct_costs / filtered_revenue * 100) if filtered_revenue > 0 else 0
    
    current_gm = base_gm + fte_impact - direct_cost_impact
    
    return {
        "currentGM": current_gm,
        "revenue": filtered_revenue,
        "directCosts": applicable_direct_costs
    }

def load_employee_data():
    """Load employee data from storage and convert to DataFrame"""
    try:
        # This can be modified to load from your actual storage location
        df = pd.read_csv('storage/employees.csv')
        
        # Ensure all required columns exist
        required_columns = [
            'id', 'name', 'band', 'businessUnit', 'customer', 
            'location', 'billable', 'fteApril', 'fteMay', 
            'fteJune', 'fteQuarter'
        ]
        
        for col in required_columns:
            if col not in df.columns:
                if col.startswith('fte'):
                    df[col] = 0.0
                elif col == 'billable':
                    df[col] = False
                else:
                    df[col] = ''
        
        return df
    except Exception as e:
        print(f"Error loading employee data: {str(e)}")
        return pd.DataFrame(columns=required_columns)

def save_employee_data(df):
    """Save employee data back to storage"""
    try:
        # This can be modified to save to your actual storage location
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
    df = load_total_employees()
    return jsonify(df.to_dict(orient='records'))


@app.route('/api/employees')
def get_employees():
    """Get all employees data"""
    df = load_employee_data()
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/employees/<employee_id>', methods=['PATCH'])
def update_employee(employee_id):
    """Update employee FTE values"""
    try:
        df = load_employee_data()
        data = request.get_json()
        
        # Find the employee
        if employee_id not in df['id'].values:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Update FTE values
        mask = df['id'] == employee_id
        for key, value in data.items():
            if key.startswith('fte'):
                df.loc[mask, key] = float(value)
        
        # Recalculate quarter average
        df.loc[mask, 'fteQuarter'] = df.loc[mask, ['fteApril', 'fteMay', 'fteJune']].mean(axis=1).round(2)
        
        # Save updated data
        if save_employee_data(df):
            return jsonify(df[mask].to_dict(orient='records')[0])
        else:
            return jsonify({'error': 'Failed to save changes'}), 500
            
    except Exception as e:
        print(f"Error updating employee: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/direct-costs')
def get_direct_costs():
    return jsonify([c.dict() for c in direct_costs])

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