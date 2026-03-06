"""
Load technician tools and spare parts into MongoDB.
Creates realistic sample data for the Technician Helper feature.

Usage:
    python scripts/load_technician_data.py

Set CLEAR_TECHNICIAN_DATA=1 to clear collections before insert.
"""

import os
import random
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pymongo

# ---------- MongoDB setup ----------
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])

DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")

client = pymongo.MongoClient(MONGODB_URI)
db = client[DB_NAME]

TECHNICIAN_TOOLS_COLLECTION = "technician_tools"
SPARE_PARTS_COLLECTION = "spare_parts"
PREP_ORDERS_COLLECTION = "prep_orders"

# ---------- Sample Data ----------

TECHNICIAN_TOOLS = [
    # Hand Tools
    {"toolId": "TL-001", "name": "Torque Wrench 3/8\"", "category": "Hand Tools", "description": "Precision torque wrench for engine components, 10-80 ft-lb range", "quantity": 12, "location": "Tool Bay A-1", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-002", "name": "Torque Wrench 1/2\"", "category": "Hand Tools", "description": "Heavy-duty torque wrench, 30-250 ft-lb range", "quantity": 8, "location": "Tool Bay A-2", "engineModels": ["X15", "ISX15"]},
    {"toolId": "TL-003", "name": "Socket Set - Metric", "category": "Hand Tools", "description": "Complete metric socket set 8mm-32mm", "quantity": 15, "location": "Tool Bay A-3", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-004", "name": "Socket Set - SAE", "category": "Hand Tools", "description": "Complete SAE socket set 1/4\" to 1-1/4\"", "quantity": 15, "location": "Tool Bay A-4", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-005", "name": "Combination Wrench Set", "category": "Hand Tools", "description": "Metric and SAE combination wrenches", "quantity": 10, "location": "Tool Bay A-5", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-006", "name": "Screwdriver Set", "category": "Hand Tools", "description": "Phillips and flathead screwdriver set", "quantity": 20, "location": "Tool Bay A-6", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-007", "name": "Pliers Set", "category": "Hand Tools", "description": "Needle nose, slip joint, and locking pliers", "quantity": 18, "location": "Tool Bay A-7", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-008", "name": "Pry Bar Set", "category": "Hand Tools", "description": "Various length pry bars for component removal", "quantity": 6, "location": "Tool Bay A-8", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    
    # Power Tools
    {"toolId": "TL-020", "name": "Impact Wrench 1/2\"", "category": "Power Tools", "description": "Pneumatic impact wrench for heavy fasteners", "quantity": 6, "location": "Tool Bay B-1", "engineModels": ["X15", "ISX15"]},
    {"toolId": "TL-021", "name": "Impact Wrench 3/8\"", "category": "Power Tools", "description": "Pneumatic impact wrench for medium fasteners", "quantity": 8, "location": "Tool Bay B-2", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-022", "name": "Electric Drill", "category": "Power Tools", "description": "Variable speed electric drill", "quantity": 5, "location": "Tool Bay B-3", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-023", "name": "Die Grinder", "category": "Power Tools", "description": "Pneumatic die grinder for surface prep", "quantity": 4, "location": "Tool Bay B-4", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-024", "name": "Heat Gun", "category": "Power Tools", "description": "Industrial heat gun for hose and seal removal", "quantity": 3, "location": "Tool Bay B-5", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    
    # Diagnostic Tools
    {"toolId": "TL-040", "name": "INSITE Diagnostic Laptop", "category": "Diagnostic", "description": "Cummins INSITE diagnostic software and laptop", "quantity": 3, "location": "Diagnostic Bay C-1", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-041", "name": "Multimeter", "category": "Diagnostic", "description": "Digital multimeter for electrical diagnostics", "quantity": 10, "location": "Diagnostic Bay C-2", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-042", "name": "Pressure Gauge Set", "category": "Diagnostic", "description": "Fuel, oil, and coolant pressure gauges", "quantity": 5, "location": "Diagnostic Bay C-3", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-043", "name": "Compression Tester", "category": "Diagnostic", "description": "Engine compression testing kit", "quantity": 3, "location": "Diagnostic Bay C-4", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-044", "name": "Borescope", "category": "Diagnostic", "description": "Video borescope for internal engine inspection", "quantity": 2, "location": "Diagnostic Bay C-5", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-045", "name": "Infrared Thermometer", "category": "Diagnostic", "description": "Non-contact temperature measurement", "quantity": 8, "location": "Diagnostic Bay C-6", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    
    # Specialty Tools
    {"toolId": "TL-060", "name": "Injector Puller Set", "category": "Specialty", "description": "Cummins injector removal tool set", "quantity": 2, "location": "Specialty Bay D-1", "engineModels": ["X15", "ISX15"]},
    {"toolId": "TL-061", "name": "Camshaft Timing Tool", "category": "Specialty", "description": "Engine timing alignment tool", "quantity": 2, "location": "Specialty Bay D-2", "engineModels": ["X15", "ISX15"]},
    {"toolId": "TL-062", "name": "Bearing Puller Set", "category": "Specialty", "description": "Various bearing pullers", "quantity": 3, "location": "Specialty Bay D-3", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-063", "name": "Seal Driver Set", "category": "Specialty", "description": "Crankshaft and camshaft seal drivers", "quantity": 4, "location": "Specialty Bay D-4", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-064", "name": "EGR Valve Tool Kit", "category": "Specialty", "description": "Tools for EGR valve service", "quantity": 3, "location": "Specialty Bay D-5", "engineModels": ["X15", "ISX15", "B6.7"]},
    {"toolId": "TL-065", "name": "Turbo Service Kit", "category": "Specialty", "description": "Tools for turbocharger removal and installation", "quantity": 2, "location": "Specialty Bay D-6", "engineModels": ["X15", "ISX15", "B6.7"]},
    {"toolId": "TL-066", "name": "Coolant System Tester", "category": "Specialty", "description": "Pressure tester for cooling system", "quantity": 4, "location": "Specialty Bay D-7", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    
    # Safety Equipment
    {"toolId": "TL-080", "name": "Safety Glasses", "category": "Safety", "description": "Impact-resistant safety glasses", "quantity": 50, "location": "Safety Station E-1", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-081", "name": "Work Gloves", "category": "Safety", "description": "Cut-resistant mechanics gloves", "quantity": 40, "location": "Safety Station E-2", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-082", "name": "Hearing Protection", "category": "Safety", "description": "Ear plugs and muffs", "quantity": 100, "location": "Safety Station E-3", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-083", "name": "Face Shield", "category": "Safety", "description": "Full face protection shield", "quantity": 15, "location": "Safety Station E-4", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    
    # Lifting Equipment
    {"toolId": "TL-100", "name": "Engine Hoist", "category": "Lifting", "description": "2-ton capacity engine hoist", "quantity": 2, "location": "Lift Bay F-1", "engineModels": ["X15", "ISX15"]},
    {"toolId": "TL-101", "name": "Transmission Jack", "category": "Lifting", "description": "Heavy-duty transmission jack", "quantity": 2, "location": "Lift Bay F-2", "engineModels": ["X15", "ISX15", "B6.7"]},
    {"toolId": "TL-102", "name": "Engine Stand", "category": "Lifting", "description": "Rotating engine stand, 2000 lb capacity", "quantity": 3, "location": "Lift Bay F-3", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-103", "name": "Floor Jack", "category": "Lifting", "description": "3-ton floor jack", "quantity": 5, "location": "Lift Bay F-4", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
    {"toolId": "TL-104", "name": "Jack Stands", "category": "Lifting", "description": "6-ton jack stands (pair)", "quantity": 10, "location": "Lift Bay F-5", "engineModels": ["X15", "ISX15", "B6.7", "ISB"]},
]

SPARE_PARTS = [
    # Gaskets
    {"partId": "SP-001", "partNumber": "4935041", "name": "EGR Valve Gasket", "category": "Gaskets", "description": "EGR valve to manifold gasket", "engineModels": ["X15", "ISX15"], "quantity": 25, "unitPrice": 45.99, "location": "Parts Bay A-1", "leadTimeDays": 2},
    {"partId": "SP-002", "partNumber": "3104419", "name": "Turbo Mounting Gasket", "category": "Gaskets", "description": "Turbocharger to exhaust manifold gasket", "engineModels": ["X15", "ISX15"], "quantity": 18, "unitPrice": 78.50, "location": "Parts Bay A-2", "leadTimeDays": 3},
    {"partId": "SP-003", "partNumber": "3936420", "name": "Oil Pan Gasket", "category": "Gaskets", "description": "Oil pan to block gasket set", "engineModels": ["X15", "ISX15"], "quantity": 12, "unitPrice": 125.00, "location": "Parts Bay A-3", "leadTimeDays": 5},
    {"partId": "SP-004", "partNumber": "3955133", "name": "Valve Cover Gasket", "category": "Gaskets", "description": "Valve cover gasket set", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 30, "unitPrice": 89.99, "location": "Parts Bay A-4", "leadTimeDays": 2},
    {"partId": "SP-005", "partNumber": "4089479", "name": "Water Pump Gasket", "category": "Gaskets", "description": "Water pump mounting gasket", "engineModels": ["X15", "ISX15", "B6.7", "ISB"], "quantity": 20, "unitPrice": 34.50, "location": "Parts Bay A-5", "leadTimeDays": 2},
    {"partId": "SP-006", "partNumber": "3920693", "name": "Head Gasket Set", "category": "Gaskets", "description": "Complete cylinder head gasket set", "engineModels": ["X15", "ISX15"], "quantity": 5, "unitPrice": 450.00, "location": "Parts Bay A-6", "leadTimeDays": 7},
    
    # Filters
    {"partId": "SP-020", "partNumber": "LF9001", "name": "Oil Filter", "category": "Filters", "description": "Full-flow oil filter", "engineModels": ["X15", "ISX15"], "quantity": 100, "unitPrice": 45.00, "location": "Parts Bay B-1", "leadTimeDays": 1},
    {"partId": "SP-021", "partNumber": "FS1040", "name": "Fuel Filter/Water Separator", "category": "Filters", "description": "Primary fuel filter with water separator", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 75, "unitPrice": 65.00, "location": "Parts Bay B-2", "leadTimeDays": 1},
    {"partId": "SP-022", "partNumber": "FF5825", "name": "Secondary Fuel Filter", "category": "Filters", "description": "Secondary fuel filter element", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 60, "unitPrice": 52.00, "location": "Parts Bay B-3", "leadTimeDays": 1},
    {"partId": "SP-023", "partNumber": "AF25962", "name": "Air Filter", "category": "Filters", "description": "Primary air filter element", "engineModels": ["X15", "ISX15"], "quantity": 40, "unitPrice": 125.00, "location": "Parts Bay B-4", "leadTimeDays": 2},
    {"partId": "SP-024", "partNumber": "WF2071", "name": "Coolant Filter", "category": "Filters", "description": "Coolant filter with DCA additive", "engineModels": ["X15", "ISX15", "B6.7", "ISB"], "quantity": 50, "unitPrice": 28.00, "location": "Parts Bay B-5", "leadTimeDays": 1},
    {"partId": "SP-025", "partNumber": "CV52001", "name": "Crankcase Ventilation Filter", "category": "Filters", "description": "CCV filter element", "engineModels": ["X15", "ISX15"], "quantity": 25, "unitPrice": 95.00, "location": "Parts Bay B-6", "leadTimeDays": 3},
    
    # Sensors
    {"partId": "SP-040", "partNumber": "4921599", "name": "EGR Temperature Sensor", "category": "Sensors", "description": "EGR gas temperature sensor", "engineModels": ["X15", "ISX15"], "quantity": 15, "unitPrice": 185.00, "location": "Parts Bay C-1", "leadTimeDays": 3},
    {"partId": "SP-041", "partNumber": "4921684", "name": "Boost Pressure Sensor", "category": "Sensors", "description": "Intake manifold pressure sensor", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 12, "unitPrice": 165.00, "location": "Parts Bay C-2", "leadTimeDays": 3},
    {"partId": "SP-042", "partNumber": "4921493", "name": "Coolant Temperature Sensor", "category": "Sensors", "description": "ECM coolant temp sensor", "engineModels": ["X15", "ISX15", "B6.7", "ISB"], "quantity": 25, "unitPrice": 78.00, "location": "Parts Bay C-3", "leadTimeDays": 2},
    {"partId": "SP-043", "partNumber": "4921517", "name": "Oil Pressure Sensor", "category": "Sensors", "description": "Engine oil pressure sensor", "engineModels": ["X15", "ISX15", "B6.7", "ISB"], "quantity": 18, "unitPrice": 95.00, "location": "Parts Bay C-4", "leadTimeDays": 2},
    {"partId": "SP-044", "partNumber": "4921686", "name": "NOx Sensor", "category": "Sensors", "description": "Nitrogen oxide sensor", "engineModels": ["X15", "ISX15"], "quantity": 8, "unitPrice": 450.00, "location": "Parts Bay C-5", "leadTimeDays": 5},
    {"partId": "SP-045", "partNumber": "5260246", "name": "DEF Quality Sensor", "category": "Sensors", "description": "Diesel exhaust fluid quality sensor", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 10, "unitPrice": 380.00, "location": "Parts Bay C-6", "leadTimeDays": 5},
    
    # Belts
    {"partId": "SP-060", "partNumber": "3911587", "name": "Serpentine Belt", "category": "Belts", "description": "Accessory drive belt", "engineModels": ["X15", "ISX15"], "quantity": 20, "unitPrice": 85.00, "location": "Parts Bay D-1", "leadTimeDays": 2},
    {"partId": "SP-061", "partNumber": "3914086", "name": "Fan Belt", "category": "Belts", "description": "Engine cooling fan belt", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 15, "unitPrice": 65.00, "location": "Parts Bay D-2", "leadTimeDays": 2},
    {"partId": "SP-062", "partNumber": "3935452", "name": "A/C Compressor Belt", "category": "Belts", "description": "Air conditioning compressor belt", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 12, "unitPrice": 55.00, "location": "Parts Bay D-3", "leadTimeDays": 2},
    
    # Hoses
    {"partId": "SP-080", "partNumber": "3918290", "name": "Upper Radiator Hose", "category": "Hoses", "description": "Upper coolant hose to radiator", "engineModels": ["X15", "ISX15"], "quantity": 10, "unitPrice": 125.00, "location": "Parts Bay E-1", "leadTimeDays": 3},
    {"partId": "SP-081", "partNumber": "3918291", "name": "Lower Radiator Hose", "category": "Hoses", "description": "Lower coolant hose from radiator", "engineModels": ["X15", "ISX15"], "quantity": 10, "unitPrice": 135.00, "location": "Parts Bay E-2", "leadTimeDays": 3},
    {"partId": "SP-082", "partNumber": "4026788", "name": "Turbo Oil Supply Line", "category": "Hoses", "description": "Oil supply line to turbocharger", "engineModels": ["X15", "ISX15"], "quantity": 8, "unitPrice": 175.00, "location": "Parts Bay E-3", "leadTimeDays": 4},
    {"partId": "SP-083", "partNumber": "4026790", "name": "Turbo Oil Drain Line", "category": "Hoses", "description": "Oil drain line from turbocharger", "engineModels": ["X15", "ISX15"], "quantity": 8, "unitPrice": 145.00, "location": "Parts Bay E-4", "leadTimeDays": 4},
    {"partId": "SP-084", "partNumber": "3920691", "name": "Coolant Bypass Hose", "category": "Hoses", "description": "Thermostat bypass hose", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 15, "unitPrice": 45.00, "location": "Parts Bay E-5", "leadTimeDays": 2},
    
    # Electrical
    {"partId": "SP-100", "partNumber": "4945743", "name": "Starter Motor", "category": "Electrical", "description": "12V starter motor", "engineModels": ["X15", "ISX15"], "quantity": 4, "unitPrice": 650.00, "location": "Parts Bay F-1", "leadTimeDays": 5},
    {"partId": "SP-101", "partNumber": "4936879", "name": "Alternator", "category": "Electrical", "description": "160A alternator", "engineModels": ["X15", "ISX15"], "quantity": 3, "unitPrice": 550.00, "location": "Parts Bay F-2", "leadTimeDays": 5},
    {"partId": "SP-102", "partNumber": "4921728", "name": "ECM Unit", "category": "Electrical", "description": "Engine control module", "engineModels": ["X15", "ISX15"], "quantity": 2, "unitPrice": 2500.00, "location": "Parts Bay F-3", "leadTimeDays": 10},
    {"partId": "SP-103", "partNumber": "3954992", "name": "Glow Plug Set", "category": "Electrical", "description": "Set of 6 glow plugs", "engineModels": ["B6.7", "ISB"], "quantity": 12, "unitPrice": 180.00, "location": "Parts Bay F-4", "leadTimeDays": 3},
    
    # Seals
    {"partId": "SP-120", "partNumber": "3920695", "name": "Front Crankshaft Seal", "category": "Seals", "description": "Front crank oil seal", "engineModels": ["X15", "ISX15"], "quantity": 15, "unitPrice": 65.00, "location": "Parts Bay G-1", "leadTimeDays": 3},
    {"partId": "SP-121", "partNumber": "3920696", "name": "Rear Crankshaft Seal", "category": "Seals", "description": "Rear main oil seal", "engineModels": ["X15", "ISX15"], "quantity": 12, "unitPrice": 85.00, "location": "Parts Bay G-2", "leadTimeDays": 3},
    {"partId": "SP-122", "partNumber": "3935454", "name": "Valve Stem Seals", "category": "Seals", "description": "Set of valve stem seals", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 10, "unitPrice": 120.00, "location": "Parts Bay G-3", "leadTimeDays": 4},
    {"partId": "SP-123", "partNumber": "3920697", "name": "Camshaft Seal", "category": "Seals", "description": "Camshaft oil seal", "engineModels": ["X15", "ISX15"], "quantity": 18, "unitPrice": 55.00, "location": "Parts Bay G-4", "leadTimeDays": 3},
    
    # Valves
    {"partId": "SP-140", "partNumber": "4955054", "name": "EGR Valve", "category": "Valves", "description": "Exhaust gas recirculation valve", "engineModels": ["X15", "ISX15"], "quantity": 5, "unitPrice": 850.00, "location": "Parts Bay H-1", "leadTimeDays": 7},
    {"partId": "SP-141", "partNumber": "4089180", "name": "Thermostat", "category": "Valves", "description": "Engine thermostat 190°F", "engineModels": ["X15", "ISX15", "B6.7", "ISB"], "quantity": 20, "unitPrice": 75.00, "location": "Parts Bay H-2", "leadTimeDays": 2},
    {"partId": "SP-142", "partNumber": "4936094", "name": "Fuel Pressure Regulator", "category": "Valves", "description": "High pressure fuel regulator", "engineModels": ["X15", "ISX15"], "quantity": 6, "unitPrice": 425.00, "location": "Parts Bay H-3", "leadTimeDays": 5},
    {"partId": "SP-143", "partNumber": "4928594", "name": "Oil Pressure Relief Valve", "category": "Valves", "description": "Oil gallery pressure relief", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 10, "unitPrice": 145.00, "location": "Parts Bay H-4", "leadTimeDays": 3},
    
    # Pumps
    {"partId": "SP-160", "partNumber": "4089909", "name": "Water Pump", "category": "Pumps", "description": "Engine coolant water pump", "engineModels": ["X15", "ISX15"], "quantity": 4, "unitPrice": 550.00, "location": "Parts Bay I-1", "leadTimeDays": 5},
    {"partId": "SP-161", "partNumber": "4954200", "name": "Fuel Transfer Pump", "category": "Pumps", "description": "Low pressure fuel pump", "engineModels": ["X15", "ISX15"], "quantity": 5, "unitPrice": 385.00, "location": "Parts Bay I-2", "leadTimeDays": 5},
    {"partId": "SP-162", "partNumber": "4921431", "name": "Oil Pump", "category": "Pumps", "description": "Engine oil pump assembly", "engineModels": ["X15", "ISX15"], "quantity": 2, "unitPrice": 750.00, "location": "Parts Bay I-3", "leadTimeDays": 7},
    {"partId": "SP-163", "partNumber": "5260545", "name": "DEF Pump Module", "category": "Pumps", "description": "Diesel exhaust fluid delivery pump", "engineModels": ["X15", "ISX15", "B6.7"], "quantity": 3, "unitPrice": 1200.00, "location": "Parts Bay I-4", "leadTimeDays": 10},
    
    # Bearings
    {"partId": "SP-180", "partNumber": "3920698", "name": "Main Bearing Set", "category": "Bearings", "description": "Complete main bearing set", "engineModels": ["X15", "ISX15"], "quantity": 3, "unitPrice": 450.00, "location": "Parts Bay J-1", "leadTimeDays": 5},
    {"partId": "SP-181", "partNumber": "3920699", "name": "Rod Bearing Set", "category": "Bearings", "description": "Complete connecting rod bearing set", "engineModels": ["X15", "ISX15"], "quantity": 4, "unitPrice": 380.00, "location": "Parts Bay J-2", "leadTimeDays": 5},
    {"partId": "SP-182", "partNumber": "3935460", "name": "Cam Bearing Set", "category": "Bearings", "description": "Camshaft bearing set", "engineModels": ["X15", "ISX15"], "quantity": 3, "unitPrice": 290.00, "location": "Parts Bay J-3", "leadTimeDays": 5},
    {"partId": "SP-183", "partNumber": "3917369", "name": "Turbo Bearing Kit", "category": "Bearings", "description": "Turbocharger bearing repair kit", "engineModels": ["X15", "ISX15"], "quantity": 5, "unitPrice": 185.00, "location": "Parts Bay J-4", "leadTimeDays": 4},
]


def get_availability(quantity: int) -> str:
    """Determine availability status based on quantity."""
    if quantity == 0:
        return "out_of_stock"
    elif quantity <= 5:
        return "low_stock"
    else:
        return "in_stock"


def load_technician_tools():
    """Load technician tools into MongoDB."""
    coll = db[TECHNICIAN_TOOLS_COLLECTION]
    
    if os.environ.get("CLEAR_TECHNICIAN_DATA") == "1":
        coll.delete_many({})
        print(f"Cleared {TECHNICIAN_TOOLS_COLLECTION}")
    
    # Add availability and timestamps
    tools = []
    for tool in TECHNICIAN_TOOLS:
        tool_doc = tool.copy()
        # Randomly adjust some quantities to create variety
        if random.random() < 0.15:
            tool_doc["quantity"] = 0
        elif random.random() < 0.25:
            tool_doc["quantity"] = random.randint(1, 5)
        tool_doc["availability"] = get_availability(tool_doc["quantity"])
        tool_doc["createdAt"] = datetime.utcnow()
        tool_doc["updatedAt"] = datetime.utcnow()
        tools.append(tool_doc)
    
    # Upsert tools
    for tool in tools:
        coll.update_one(
            {"toolId": tool["toolId"]},
            {"$set": tool},
            upsert=True
        )
    
    print(f"Loaded {len(tools)} technician tools")
    
    # Summary by availability
    in_stock = sum(1 for t in tools if t["availability"] == "in_stock")
    low_stock = sum(1 for t in tools if t["availability"] == "low_stock")
    out_of_stock = sum(1 for t in tools if t["availability"] == "out_of_stock")
    print(f"  In Stock: {in_stock}, Low Stock: {low_stock}, Out of Stock: {out_of_stock}")


def load_spare_parts():
    """Load spare parts into MongoDB."""
    coll = db[SPARE_PARTS_COLLECTION]
    
    if os.environ.get("CLEAR_TECHNICIAN_DATA") == "1":
        coll.delete_many({})
        print(f"Cleared {SPARE_PARTS_COLLECTION}")
    
    # Add availability and timestamps
    parts = []
    for part in SPARE_PARTS:
        part_doc = part.copy()
        # Randomly adjust some quantities to create variety
        if random.random() < 0.1:
            part_doc["quantity"] = 0
        elif random.random() < 0.2:
            part_doc["quantity"] = random.randint(1, 5)
        part_doc["availability"] = get_availability(part_doc["quantity"])
        part_doc["createdAt"] = datetime.utcnow()
        part_doc["updatedAt"] = datetime.utcnow()
        parts.append(part_doc)
    
    # Upsert parts
    for part in parts:
        coll.update_one(
            {"partId": part["partId"]},
            {"$set": part},
            upsert=True
        )
    
    print(f"Loaded {len(parts)} spare parts")
    
    # Summary by availability
    in_stock = sum(1 for p in parts if p["availability"] == "in_stock")
    low_stock = sum(1 for p in parts if p["availability"] == "low_stock")
    out_of_stock = sum(1 for p in parts if p["availability"] == "out_of_stock")
    print(f"  In Stock: {in_stock}, Low Stock: {low_stock}, Out of Stock: {out_of_stock}")


def clear_prep_orders():
    """Clear prep orders collection."""
    if os.environ.get("CLEAR_TECHNICIAN_DATA") == "1":
        db[PREP_ORDERS_COLLECTION].delete_many({})
        print(f"Cleared {PREP_ORDERS_COLLECTION}")


def main():
    print("=" * 50)
    print("Loading Technician Helper Data")
    print("=" * 50)
    
    load_technician_tools()
    print()
    load_spare_parts()
    print()
    clear_prep_orders()
    
    print()
    print("=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
