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

