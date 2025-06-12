from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class Employee(BaseModel):
    id: str
    EmployeeName: str
    Band: str
    FinalBU: str
    PrismCustomerGroup: str
    AllocationFTECapped_M1: float
    AllocationFTECapped_M2: float
    AllocationFTECapped_M3: float
    AllocationFTECapped_QTR: float
    Offshore_Onsite: str
    BillableYN: bool

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