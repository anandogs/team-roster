from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class Employee(BaseModel):
    id: str
    name: str
    band: str
    businessUnit: str
    customer: str
    fteApril: float
    fteMay: float
    fteJune: float
    fteQuarter: float
    location: str
    billable: bool

class DirectCost(BaseModel):
    id: str
    name: str
    percentage: float
    amount: float
    level: str
    businessUnit: Optional[str] = None
    customer: Optional[str] = None
    createdAt: datetime

class GMState(BaseModel):
    startingGM: float
    currentGM: float
    planGM: float
    revenue: float
    directCosts: List[DirectCost]

class FilterState(BaseModel):
    month: str
    businessUnit: str
    customer: str
    location: str
    billableStatus: str
    businessUnits: List[str]

# Sample data
bu_to_customers = {
    "BU A": ["Customer A", "Customer B"],
    "BU B": ["Customer C", "Customer D"],
}

revenue_data = {
    "overall": 5000,
    "BU A": 3000,
    "BU B": 2000,
    "Customer A": 1800,
    "Customer B": 1200,
    "Customer C": 1300,
    "Customer D": 700,
}

def generate_sample_employees():
    bands = ["Junior", "Mid-level", "Senior", "Principal"]
    first_names = ["Alex", "Jamie", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Quinn", "Avery", "Dakota", "Skyler", "Reese", "Parker", "Hayden", "Drew"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson"]
    
    employees = []
    for i in range(1, 31):
        first_name = first_names[i % len(first_names)]
        last_name = last_names[i % len(last_names)]
        band = bands[i % len(bands)]
        
        fte_april = round(i % 10 / 10, 1)
        fte_may = round((i + 1) % 10 / 10, 1)
        fte_june = 0 if i % 2 == 0 else round((i + 2) % 10 / 10, 1)
        fte_quarter = round((fte_april + fte_may + fte_june) / 3, 2)
        
        business_unit = "BU A" if i % 2 == 0 else "BU B"
        customer_options = bu_to_customers[business_unit]
        customer = customer_options[i % len(customer_options)]
        
        location = "Offshore" if i % 3 != 0 else "Onsite"
        billable = i % 5 != 0
        
        employees.append(Employee(
            id=str(i),
            name=f"{first_name} {last_name}",
            band=band,
            businessUnit=business_unit,
            customer=customer,
            fteApril=fte_april,
            fteMay=fte_may,
            fteJune=fte_june,
            fteQuarter=fte_quarter,
            location=location,
            billable=billable
        ))
    
    return employees

def generate_sample_direct_costs():
    return [
        DirectCost(
            id="cost1",
            name="Hardware Costs",
            percentage=5,
            amount=250,
            level="Overall",
            createdAt=datetime(2023, 4, 15)
        ),
        DirectCost(
            id="cost2",
            name="Software Licenses",
            percentage=3,
            amount=90,
            level="Business Unit",
            businessUnit="BU A",
            createdAt=datetime(2023, 4, 20)
        ),
        DirectCost(
            id="cost3",
            name="Contractor Fees",
            percentage=8,
            amount=144,
            level="Customer",
            businessUnit="BU A",
            customer="Customer A",
            createdAt=datetime(2023, 4, 25)
        )
    ] 