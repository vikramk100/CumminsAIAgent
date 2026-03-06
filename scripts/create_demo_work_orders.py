"""
Create Demo Work Orders for Cummins AI Agent Presentation
Generates realistic work orders with full details:
- Machine logs with telemetry leading to failures
- Diagnostics for fault codes
- Operations with planned work
- Confirmations documenting the repair journey
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pymongo
from bson import ObjectId

# MongoDB Configuration
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])

DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")

# Connect to MongoDB
client = pymongo.MongoClient(MONGODB_URI)
db = client[DB_NAME]

# Base date for demo (recent past)
BASE_DATE = datetime(2026, 3, 1, 8, 0, 0)


# =============================================================================
# DEMO WORK ORDER 1: Class-8 Truck Highway Breakdown - Gasket Failure
# =============================================================================
DEMO_WO_1 = {
    "work_order": {
        "orderId": "WO-DEMO-001",
        "equipmentId": "TRUCK-X15-001",
        "status": "Completed",
        "priority": 1,
        "orderDate": BASE_DATE,
        "actualWork": 8.5,
        "daysToSolve": 1,
        "technician": "Marco Rodriguez",
        "faultCode": "P0300_S3",
        "issueDescription": """CRITICAL - HIGHWAY BREAKDOWN - CLASS-8 TRUCK

CUSTOMER COMPLAINT (Driver Call @ 06:42 AM):
"Hey, I'm stuck on the side of I-65 near mile marker 142. My dash just threw a fault code—looks like 'P0300_S3'. The engine temperature spiked to the red zone, and I'm losing power bad. Had to pull over before the engine seized up completely. I'm hauling a time-sensitive load of auto parts to the GM plant in Fort Wayne, and this downtime is costing my boss $1,200 a day in late delivery penalties. I need a tech out here ASAP—this is an emergency!"

TELEMATICS ALERT DETAILS:
- Fault Code Triggered: P0300_S3 (Engine Cylinder Misfire - Severity 3)
- Engine Model: Cummins X15
- VIN: 1FUJGBDV5DLFA1234
- GPS Location: I-65 Northbound, Mile Marker 142, Lafayette, IN
- Engine Hours at Failure: 12,847
- Last Service: 2,340 hours ago (oil change, filter replacement)

TELEMETRY SNAPSHOT AT FAILURE:
- Process Temperature: 248°F (CRITICAL - Normal: 180-210°F)
- Coolant Temperature: 235°F (HIGH)
- Oil Pressure: 28 PSI (LOW - Normal: 40-60 PSI)
- Rotational Speed: 1,450 RPM (Reduced from normal 1,800 RPM)
- Torque: 1,890 Nm (Fluctuating)
- Tool Wear Index: 87% (HIGH)

PRELIMINARY DIAGNOSIS:
Suspected cylinder head gasket leak causing coolant-to-oil contamination. Loss of compression in cylinders 3 and 5. Requires immediate inspection and likely gasket replacement.

FLEET INFORMATION:
- Fleet: Anderson Logistics Inc.
- Account Priority: Premium (SLA: 4-hour response)
- Contact: Jim Anderson (Fleet Manager) - (317) 555-0142
- Previous Issues: 2 similar thermal events in past 18 months

DISPATCH NOTES:
This is a high-priority roadside assistance call. Driver reports white smoke from exhaust before shutdown. Customer has tow truck on standby if engine cannot be restarted safely.""",
    },
    "machine_logs": [
        {
            "MachineID": "TRUCK-X15-001",
            "logTimestamp": BASE_DATE - timedelta(hours=4),
            "Process_Temperature": 205.0,
            "Air_Temperature": 72.0,
            "Rotational_Speed": 1800,
            "Torque": 1950.0,
            "Tool_Wear": 65,
            "failure_label": "No_Failure",
            "symptom": "Normal operation",
            "Failure_Type": "Normal",
        },
        {
            "MachineID": "TRUCK-X15-001",
            "logTimestamp": BASE_DATE - timedelta(hours=2),
            "Process_Temperature": 228.0,
            "Air_Temperature": 74.0,
            "Rotational_Speed": 1720,
            "Torque": 1920.0,
            "Tool_Wear": 78,
            "failure_label": "HDF_S2",
            "symptom": "Temperature rising, minor power loss",
            "Failure_Type": "Warning",
        },
        {
            "MachineID": "TRUCK-X15-001",
            "logTimestamp": BASE_DATE - timedelta(minutes=30),
            "Process_Temperature": 248.0,
            "Air_Temperature": 76.0,
            "Rotational_Speed": 1450,
            "Torque": 1890.0,
            "Tool_Wear": 87,
            "failure_label": "OSF_S3",
            "symptom": "Gasket leak, loss of pressure, white exhaust smoke",
            "Failure_Type": "Failure",
        },
    ],
    "diagnostics": {
        "fault_code": "P0300_S3",
        "engineModel": "X15",
        "system_affected": "Engine - Cylinder Head",
        "symptoms": "Cylinder misfire, engine temperature spike, white exhaust smoke, coolant loss, oil contamination, loss of power",
        "diagnostic_steps": "1. Connect diagnostic laptop and pull fault codes\n2. Perform compression test on all cylinders\n3. Check coolant reservoir level and condition\n4. Inspect oil for coolant contamination (milky appearance)\n5. Pressure test cooling system\n6. Visual inspection of cylinder head gasket area",
        "resolution": "Replace cylinder head gasket using heavy-duty puller tool and 10mm specialized socket. Install Gasket Kit #402 (Cummins P/N: 4955229). Torque head bolts to specification (see Service Manual Section 7.3). Flush cooling system and replace coolant. Change oil and filter.",
        "required_tools": ["Heavy-duty Puller", "10mm Specialized Socket", "Torque Wrench (50-250 ft-lb)", "Coolant Pressure Tester", "Compression Tester", "Diagnostic Laptop"],
        "required_parts": ["Gasket Kit #402", "5 Gallons Coolant", "Oil Filter", "15W-40 Engine Oil (12 quarts)"],
        "severity": 3,
        "estimated_repair_hours": 6.0,
    },
    "operations": [
        {
            "orderId": "WO-DEMO-001",
            "operationId": "OP-DEMO-001-10",
            "description": "Initial roadside diagnosis and assessment",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(hours=1),
            "plannedDuration": 1.0,
            "actualDuration": 1.5,
        },
        {
            "orderId": "WO-DEMO-001",
            "operationId": "OP-DEMO-001-20",
            "description": "Return to shop for specialized tools and parts",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(hours=2),
            "plannedDuration": 2.0,
            "actualDuration": 3.0,
        },
        {
            "orderId": "WO-DEMO-001",
            "operationId": "OP-DEMO-001-30",
            "description": "Cylinder head gasket replacement",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(hours=5),
            "plannedDuration": 4.0,
            "actualDuration": 3.5,
        },
        {
            "orderId": "WO-DEMO-001",
            "operationId": "OP-DEMO-001-40",
            "description": "System flush, refill, and test",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(hours=8),
            "plannedDuration": 1.0,
            "actualDuration": 0.5,
        },
    ],
    "confirmations": [
        {
            "orderId": "WO-DEMO-001",
            "confirmationId": "CNF-DEMO-001-A",
            "confirmationText": """ARRIVAL ON SITE - INITIAL ASSESSMENT (Visit 1)
Arrived at I-65 mile marker 142 at 08:15 AM. Driver Jim reported hearing a "knocking" sound before the temperature spike. 

Initial Findings:
- Engine will not restart (overheating protection engaged)
- Coolant reservoir nearly empty
- White residue visible around cylinder head gasket area
- Oil dipstick shows milky contamination (coolant mixing)

Diagnosis: Confirmed cylinder head gasket failure causing coolant intrusion into oil system and compression loss in cylinders 3 and 5.

PROBLEM: I arrived with standard tool kit but need the following specialized equipment:
- Heavy-duty puller (not in standard kit)
- 10mm specialized deep socket for head bolts
- Gasket Kit #402

Returning to warehouse to retrieve parts and tools. ETA return: 3 hours.
Driver will wait with vehicle.""",
            "confirmedAt": BASE_DATE + timedelta(hours=2),
            "actualWork": 1.5,
            "technician": "Marco Rodriguez",
        },
        {
            "orderId": "WO-DEMO-001",
            "confirmationId": "CNF-DEMO-001-B",
            "confirmationText": """RETURN TO SITE WITH PARTS (Visit 2)
Returned to job site at 01:30 PM with all required tools and parts:
✓ Heavy-duty puller
✓ 10mm specialized socket set
✓ Gasket Kit #402 (Cummins P/N: 4955229)
✓ 5 gallons Fleetguard ES Compleat coolant
✓ Fleetguard LF14000NN oil filter
✓ 12 quarts Shell Rotella 15W-40

Beginning cylinder head removal. Weather conditions: Clear, 68°F - good working conditions.

Note: The 4-hour "dead leg" trip cost approximately $850 in technician time and mileage. With proper AI-assisted dispatch, this second trip would have been unnecessary.""",
            "confirmedAt": BASE_DATE + timedelta(hours=5, minutes=30),
            "actualWork": 3.0,
            "technician": "Marco Rodriguez",
        },
        {
            "orderId": "WO-DEMO-001",
            "confirmationId": "CNF-DEMO-001-C",
            "confirmationText": """REPAIR COMPLETED - FINAL CONFIRMATION
Repair successfully completed at 05:45 PM.

Work Performed:
1. Removed cylinder head using heavy-duty puller
2. Cleaned all mating surfaces (block and head)
3. Inspected head for warpage - within spec (0.002")
4. Installed new Gasket Kit #402
5. Torqued head bolts to 150 ft-lb in proper sequence per Service Manual 7.3
6. Drained and flushed cooling system
7. Filled with 5 gallons fresh coolant
8. Drained oil and replaced filter
9. Added 12 quarts fresh 15W-40 oil
10. Started engine - no leaks, temperature stable at 195°F
11. Test drove 5 miles - all systems nominal

Customer Sign-off: Driver Jim confirmed vehicle operating normally. Cleared to continue route to Fort Wayne.

Total Repair Time: 8.5 hours (would have been 4.5 hours with single-trip dispatch)
Parts Used: Gasket Kit #402, Coolant, Oil, Filter
Root Cause: Thermal stress from extended high-load operation caused gasket failure

RECOMMENDATION: Schedule preventive gasket inspection at next service interval (500 hours).""",
            "confirmedAt": BASE_DATE + timedelta(hours=9, minutes=45),
            "actualWork": 4.0,
            "technician": "Marco Rodriguez",
        },
    ],
}


# =============================================================================
# DEMO WORK ORDER 2: Data Center Generator Emergency
# =============================================================================
DEMO_WO_2 = {
    "work_order": {
        "orderId": "WO-DEMO-002",
        "equipmentId": "GEN-X15-DC01",
        "status": "Completed",
        "priority": 1,
        "orderDate": BASE_DATE + timedelta(days=1),
        "actualWork": 5.0,
        "daysToSolve": 0,
        "technician": "Sarah Chen",
        "faultCode": "TWF_S3",
        "issueDescription": """EMERGENCY - DATA CENTER BACKUP GENERATOR FAILURE

CUSTOMER COMPLAINT (Facilities Manager Call @ 02:15 AM):
"This is an EMERGENCY. Our backup Cummins X15 generator at the Midwest Regional Data Center just threw a 'High Tool Wear' and thermal failure alarm during our monthly load test. The generator shut itself down and won't restart. We have 45 minutes of UPS battery backup if grid power fails, and there's a severe thunderstorm moving through the area. An outage will cost us $2.3 million per hour in SLA penalties and customer compensation. I need your best technician here within 30 minutes with whatever parts they might need. Money is no object—just get this generator running!"

TELEMATICS ALERT DETAILS:
- Fault Code Triggered: TWF_S3 (Tool Wear Failure - Severity 3)
- Secondary Code: HDF_S2 (Heat Dissipation Failure)
- Engine Model: Cummins X15 (Generator Configuration)
- Serial: GEN-2024-X15-7891
- Location: DataVault Midwest Regional DC, 1500 Tech Park Dr, Columbus, OH
- Generator Hours: 4,256
- Last Service: 890 hours ago

TELEMETRY AT FAILURE:
- Process Temperature: 267°F (CRITICAL)
- Coolant Temperature: 252°F (CRITICAL)
- Oil Temperature: 285°F (CRITICAL)
- Rotational Speed: 0 RPM (Shutdown)
- Load at Failure: 1.8 MW (90% capacity)
- Tool Wear Index: 94% (CRITICAL)

PRELIMINARY DIAGNOSIS:
Fuel injector wear causing incomplete combustion and thermal runaway. Possible secondary damage to turbocharger seals from excessive heat.

FACILITY INFORMATION:
- Customer: DataVault Inc.
- Account Priority: Critical Infrastructure (SLA: 30-minute response)
- Contact: Robert Kim (Facilities Director) - (614) 555-0198
- Backup: Secondary generator available but untested
- Grid Status: Stable but storm approaching (70% chance of outage)

DISPATCH NOTES:
CRITICAL PRIORITY - Dispatch immediately with full diagnostic kit and common injector/turbo parts. Customer has authorized emergency parts procurement. Coordinate with DataVault security for immediate site access.""",
    },
    "machine_logs": [
        {
            "MachineID": "GEN-X15-DC01",
            "logTimestamp": BASE_DATE + timedelta(days=1) - timedelta(hours=1),
            "Process_Temperature": 210.0,
            "Air_Temperature": 78.0,
            "Rotational_Speed": 1800,
            "Torque": 2100.0,
            "Tool_Wear": 82,
            "failure_label": "No_Failure",
            "symptom": "Load test initiated",
            "Failure_Type": "Normal",
        },
        {
            "MachineID": "GEN-X15-DC01",
            "logTimestamp": BASE_DATE + timedelta(days=1) - timedelta(minutes=20),
            "Process_Temperature": 245.0,
            "Air_Temperature": 82.0,
            "Rotational_Speed": 1780,
            "Torque": 2050.0,
            "Tool_Wear": 91,
            "failure_label": "TWF_S2",
            "symptom": "Tool wear warning, temperature rising",
            "Failure_Type": "Warning",
        },
        {
            "MachineID": "GEN-X15-DC01",
            "logTimestamp": BASE_DATE + timedelta(days=1) - timedelta(minutes=5),
            "Process_Temperature": 267.0,
            "Air_Temperature": 85.0,
            "Rotational_Speed": 0,
            "Torque": 0.0,
            "Tool_Wear": 94,
            "failure_label": "TWF_S3",
            "symptom": "Emergency shutdown - thermal protection activated",
            "Failure_Type": "Failure",
        },
    ],
    "diagnostics": {
        "fault_code": "TWF_S3",
        "engineModel": "X15",
        "system_affected": "Fuel System - Injectors",
        "symptoms": "Tool wear critical, incomplete combustion, thermal runaway, black exhaust smoke, rough running before shutdown",
        "diagnostic_steps": "1. Allow engine to cool (minimum 30 minutes)\n2. Connect diagnostic system and review fault history\n3. Perform fuel injector balance test\n4. Inspect injector nozzles for wear patterns\n5. Check turbocharger for heat damage\n6. Inspect fuel filters and fuel quality",
        "resolution": "Replace worn fuel injectors (cylinders 2, 4, 6 showing excessive wear). Clean injector seats. Replace fuel filters. If turbo damage present, replace turbocharger seals or complete unit.",
        "required_tools": ["Injector Puller Set", "Torque Wrench", "Fuel System Pressure Gauge", "Borescope", "Injector Flow Tester"],
        "required_parts": ["Fuel Injector Set (6x)", "Fuel Filter Kit", "Injector Seat O-rings", "Turbo Seal Kit (if needed)"],
        "severity": 3,
        "estimated_repair_hours": 4.5,
    },
    "operations": [
        {
            "orderId": "WO-DEMO-002",
            "operationId": "OP-DEMO-002-10",
            "description": "Emergency response and initial diagnosis",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(days=1, minutes=30),
            "plannedDuration": 1.0,
            "actualDuration": 0.75,
        },
        {
            "orderId": "WO-DEMO-002",
            "operationId": "OP-DEMO-002-20",
            "description": "Fuel injector replacement (cylinders 2, 4, 6)",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(days=1, hours=1),
            "plannedDuration": 3.0,
            "actualDuration": 3.25,
        },
        {
            "orderId": "WO-DEMO-002",
            "operationId": "OP-DEMO-002-30",
            "description": "System test and load verification",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(days=1, hours=4),
            "plannedDuration": 1.0,
            "actualDuration": 1.0,
        },
    ],
    "confirmations": [
        {
            "orderId": "WO-DEMO-002",
            "confirmationId": "CNF-DEMO-002-A",
            "confirmationText": """EMERGENCY RESPONSE - ON SITE
Arrived at DataVault facility at 02:48 AM (33 minutes from dispatch - within SLA).

AI-ASSISTED DISPATCH SUCCESS: 
Thanks to the AI dispatch system, I was pre-equipped with:
✓ Complete fuel injector set (6x)
✓ Injector puller and installation tools
✓ Fuel filter kit
✓ Diagnostic laptop with generator-specific software

Initial diagnosis confirms TWF_S3 - Fuel injector wear. Cylinders 2, 4, and 6 showing 40%+ above acceptable wear tolerance. No turbocharger damage detected (avoided due to automatic shutdown).

Beginning injector replacement immediately. Generator room temperature has cooled to safe working level.

Customer Status: Robert Kim (Facilities Director) on site and observing. UPS showing 38 minutes remaining. Storm tracking shows severe weather 90 minutes away.""",
            "confirmedAt": BASE_DATE + timedelta(days=1, hours=1),
            "actualWork": 0.75,
            "technician": "Sarah Chen",
        },
        {
            "orderId": "WO-DEMO-002",
            "confirmationId": "CNF-DEMO-002-B",
            "confirmationText": """REPAIR COMPLETED - GENERATOR OPERATIONAL
Generator successfully restarted and load-tested at 05:52 AM.

Work Performed:
1. Replaced fuel injectors in cylinders 2, 4, and 6
2. Cleaned all injector seats and installed new O-rings
3. Replaced primary and secondary fuel filters
4. Performed injector balance test - all within spec
5. Completed 30-minute load test at 85% capacity (1.7 MW)
6. All temperatures nominal: Process 198°F, Oil 210°F, Coolant 192°F

Generator Status: FULLY OPERATIONAL
Customer cleared to rely on unit as primary backup

Time to Resolution: 3.5 hours from arrival (would have been 7+ hours without AI-assisted pre-staging of parts)

COST AVOIDANCE: Estimated $8.05 million in potential outage costs avoided (3.5 hours × $2.3M/hour)

Customer extremely satisfied. Robert Kim requesting information about AI dispatch system for other facilities.""",
            "confirmedAt": BASE_DATE + timedelta(days=1, hours=4),
            "actualWork": 4.25,
            "technician": "Sarah Chen",
        },
    ],
}


# =============================================================================
# DEMO WORK ORDER 3: Municipal Bus Fleet - Cooling System Failure
# =============================================================================
DEMO_WO_3 = {
    "work_order": {
        "orderId": "WO-DEMO-003",
        "equipmentId": "BUS-B67-015",
        "status": "In Progress",
        "priority": 2,
        "orderDate": BASE_DATE + timedelta(days=2),
        "actualWork": 3.5,
        "daysToSolve": None,
        "technician": "David Park",
        "faultCode": "HDF_S2",
        "issueDescription": """MUNICIPAL BUS - COOLING SYSTEM FAILURE - ROUTE 42

CUSTOMER COMPLAINT (Transit Operations @ 11:30 AM):
"We've got Bus #015 stranded at the downtown transit center with passengers still on board. The driver called in saying the temperature gauge went into the red during the morning rush, and now there's steam coming from under the hood. We had to evacuate 34 passengers to the platform. This is one of our busiest routes, and we need this bus back in service by the afternoon rush at 3 PM if at all possible. The B6.7 engine in this bus has had cooling issues before—check the service history."

TELEMATICS ALERT DETAILS:
- Fault Code Triggered: HDF_S2 (Heat Dissipation Failure - Severity 2)
- Engine Model: Cummins B6.7
- Bus Number: 015
- VIN: 2M93HMBA4PW654321
- Location: Metro Transit Center, Platform 7, Downtown Indianapolis
- Engine Hours: 28,456
- Odometer: 187,234 miles
- Last Service: 12,000 miles ago (routine)

TELEMETRY AT FAILURE:
- Process Temperature: 238°F (HIGH)
- Coolant Temperature: 241°F (CRITICAL)
- Coolant Level: LOW WARNING
- Rotational Speed: 650 RPM (Idle, will not rev)
- Torque: Reduced
- Tool Wear Index: 45% (Normal)

PRELIMINARY DIAGNOSIS:
Likely water pump failure or radiator blockage. Previous service records show thermostat replacement 6 months ago. Check for related failures.

FLEET INFORMATION:
- Fleet: Indianapolis Metro Transit Authority (IndyGo)
- Bus Type: 40-foot Low Floor Transit Bus
- Route: #42 (College Ave - Downtown)
- Daily Ridership: ~2,400 passengers
- Contact: Maria Santos (Fleet Maintenance Supervisor) - (317) 555-0156

DISPATCH NOTES:
Passengers have been transferred to backup bus. Bus #015 is blocking platform 7 and needs to be moved. Coordinate with transit police for traffic control. Driver reports hearing "grinding noise" from front of engine before overheat.""",
    },
    "machine_logs": [
        {
            "MachineID": "BUS-B67-015",
            "logTimestamp": BASE_DATE + timedelta(days=2) - timedelta(hours=3),
            "Process_Temperature": 195.0,
            "Air_Temperature": 82.0,
            "Rotational_Speed": 1400,
            "Torque": 680.0,
            "Tool_Wear": 44,
            "failure_label": "No_Failure",
            "symptom": "Normal operation",
            "Failure_Type": "Normal",
        },
        {
            "MachineID": "BUS-B67-015",
            "logTimestamp": BASE_DATE + timedelta(days=2) - timedelta(hours=1),
            "Process_Temperature": 218.0,
            "Air_Temperature": 85.0,
            "Rotational_Speed": 1350,
            "Torque": 660.0,
            "Tool_Wear": 45,
            "failure_label": "HDF_S1",
            "symptom": "Coolant temperature rising above normal",
            "Failure_Type": "Warning",
        },
        {
            "MachineID": "BUS-B67-015",
            "logTimestamp": BASE_DATE + timedelta(days=2) - timedelta(minutes=15),
            "Process_Temperature": 238.0,
            "Air_Temperature": 86.0,
            "Rotational_Speed": 650,
            "Torque": 0.0,
            "Tool_Wear": 45,
            "failure_label": "HDF_S2",
            "symptom": "Coolant system failure, overheating shutdown",
            "Failure_Type": "Failure",
        },
    ],
    "diagnostics": {
        "fault_code": "HDF_S2",
        "engineModel": "B6.7",
        "system_affected": "Cooling System - Water Pump",
        "symptoms": "Engine overheating, coolant loss, grinding noise from water pump area, steam from engine compartment",
        "diagnostic_steps": "1. Allow engine to cool completely\n2. Visual inspection of coolant hoses and connections\n3. Check water pump for play and leakage\n4. Inspect radiator for blockage or damage\n5. Pressure test cooling system\n6. Check thermostat operation",
        "resolution": "Replace water pump assembly. Inspect and replace coolant hoses if brittle or damaged. Flush cooling system. Refill with proper coolant mixture (50/50).",
        "required_tools": ["Cooling System Pressure Tester", "Water Pump Pulley Holder", "Serpentine Belt Tool", "Torque Wrench", "Coolant Refractometer"],
        "required_parts": ["Water Pump Assembly (B6.7)", "Serpentine Belt", "Coolant Hose Set", "Thermostat Gasket", "5 Gallons Coolant"],
        "severity": 2,
        "estimated_repair_hours": 3.5,
    },
    "operations": [
        {
            "orderId": "WO-DEMO-003",
            "operationId": "OP-DEMO-003-10",
            "description": "On-site diagnosis at transit center",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(days=2, hours=1),
            "plannedDuration": 0.5,
            "actualDuration": 0.5,
        },
        {
            "orderId": "WO-DEMO-003",
            "operationId": "OP-DEMO-003-20",
            "description": "Tow bus to maintenance facility",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(days=2, hours=1, minutes=30),
            "plannedDuration": 1.0,
            "actualDuration": 1.0,
        },
        {
            "orderId": "WO-DEMO-003",
            "operationId": "OP-DEMO-003-30",
            "description": "Water pump replacement and cooling system service",
            "status": "In Progress",
            "plannedStart": BASE_DATE + timedelta(days=2, hours=2, minutes=30),
            "plannedDuration": 2.5,
            "actualDuration": None,
        },
    ],
    "confirmations": [
        {
            "orderId": "WO-DEMO-003",
            "confirmationId": "CNF-DEMO-003-A",
            "confirmationText": """ON-SITE DIAGNOSIS - TRANSIT CENTER
Arrived at Metro Transit Center at 12:15 PM. Bus #015 is at Platform 7, steam has subsided.

Initial Assessment:
- Coolant reservoir completely empty
- Visible coolant puddle under engine (approximately 2 gallons lost)
- Water pump showing significant play when manually rotated
- Grinding noise confirmed - bearing failure in water pump
- Serpentine belt shows glazing and minor cracking

Diagnosis: Water pump bearing failure caused seal breach and rapid coolant loss. Pump must be replaced. Belt should be replaced preventively.

Decision: Bus cannot be safely driven. Coordinating with IndyGo tow service to transport to maintenance facility for repair.

ETA to maintenance bay: 1 hour.""",
            "confirmedAt": BASE_DATE + timedelta(days=2, hours=1),
            "actualWork": 0.5,
            "technician": "David Park",
        },
        {
            "orderId": "WO-DEMO-003",
            "confirmationId": "CNF-DEMO-003-B",
            "confirmationText": """IN PROGRESS - MAINTENANCE FACILITY
Bus #015 arrived at IndyGo maintenance facility at 01:30 PM. Currently in Bay 4.

Work In Progress:
- Engine has cooled to safe temperature
- Draining remaining coolant from system
- Serpentine belt removed
- Beginning water pump removal

Parts on hand (AI dispatch pre-staged):
✓ Water Pump Assembly for B6.7 (Cummins P/N: 5473238)
✓ Serpentine Belt
✓ Lower radiator hose (precautionary replacement)
✓ Coolant (6 gallons)

Estimated completion: 03:15 PM - should make afternoon rush deadline.

Note to Fleet Supervisor: Recommend scheduling Bus #012 and #018 for preventive water pump inspection - same model and similar mileage.""",
            "confirmedAt": BASE_DATE + timedelta(days=2, hours=2, minutes=30),
            "actualWork": 2.0,
            "technician": "David Park",
        },
    ],
}


# =============================================================================
# DEMO WORK ORDER 4: Agricultural Equipment - Harvest Season Emergency
# =============================================================================
DEMO_WO_4 = {
    "work_order": {
        "orderId": "WO-DEMO-004",
        "equipmentId": "HARVEST-ISB-007",
        "status": "In Progress",
        "priority": 1,
        "orderDate": BASE_DATE + timedelta(days=3),
        "actualWork": 2.0,
        "daysToSolve": None,
        "technician": "Mike Thompson",
        "faultCode": "PWF_S3",
        "issueDescription": """CRITICAL - COMBINE HARVESTER DOWN - HARVEST SEASON

CUSTOMER COMPLAINT (Farm Owner Call @ 05:45 AM):
"I've got a serious problem here. My John Deere S780 combine with the Cummins ISB engine just died in the middle of my north field. It threw some kind of power failure code and won't restart. I've got 800 acres of soybeans that need to be harvested in the next 5 days before the rain comes, and this is my only combine. Every hour this machine is down costs me money—we're talking $15,000 per day in crop loss if I miss the harvest window. I need someone out here at first light. The field is about 3 miles from my farmhouse down County Road 450."

TELEMATICS ALERT DETAILS:
- Fault Code Triggered: PWF_S3 (Power Failure - Severity 3)
- Secondary Code: OSF_S2 (Oil System Failure)
- Engine Model: Cummins ISB 6.7L
- Equipment: John Deere S780 Combine Harvester
- Serial: JD-S780-2024-1892
- Location: Hendricks County, IN - GPS: 39.7234, -86.5123
- Engine Hours: 3,892
- Last Service: 450 hours ago

TELEMETRY AT FAILURE:
- Process Temperature: 212°F (Normal)
- Oil Pressure: 12 PSI (CRITICAL LOW - Normal: 40-60 PSI)
- Oil Temperature: 245°F (HIGH)
- Rotational Speed: 0 RPM (Stalled)
- Torque: 0 Nm
- Tool Wear Index: 67% (Moderate)
- Fuel Pressure: Normal

PRELIMINARY DIAGNOSIS:
Sudden oil pressure loss with elevated oil temperature suggests oil pump failure or severe internal oil leak. Engine protection system triggered emergency shutdown to prevent catastrophic damage.

FARM INFORMATION:
- Customer: Henderson Family Farms
- Contact: Tom Henderson (Owner) - (317) 555-0187
- Farm Size: 2,400 acres (corn and soybeans)
- Equipment Age: 2 seasons
- Service History: Regular maintenance, no previous major issues

DISPATCH NOTES:
HARVEST CRITICAL - Agricultural equipment during harvest season is highest priority. Dispatch with full oil system diagnostic kit and common ISB oil pump/sensor parts. Field access via County Road 450 - 4WD vehicle recommended. Dawn arrival requested (6:30 AM).""",
    },
    "machine_logs": [
        {
            "MachineID": "HARVEST-ISB-007",
            "logTimestamp": BASE_DATE + timedelta(days=3) - timedelta(hours=2),
            "Process_Temperature": 198.0,
            "Air_Temperature": 68.0,
            "Rotational_Speed": 2100,
            "Torque": 890.0,
            "Tool_Wear": 65,
            "failure_label": "No_Failure",
            "symptom": "Normal harvesting operation",
            "Failure_Type": "Normal",
        },
        {
            "MachineID": "HARVEST-ISB-007",
            "logTimestamp": BASE_DATE + timedelta(days=3) - timedelta(minutes=45),
            "Process_Temperature": 205.0,
            "Air_Temperature": 70.0,
            "Rotational_Speed": 2050,
            "Torque": 870.0,
            "Tool_Wear": 66,
            "failure_label": "OSF_S1",
            "symptom": "Oil pressure fluctuation detected",
            "Failure_Type": "Warning",
        },
        {
            "MachineID": "HARVEST-ISB-007",
            "logTimestamp": BASE_DATE + timedelta(days=3) - timedelta(minutes=10),
            "Process_Temperature": 212.0,
            "Air_Temperature": 71.0,
            "Rotational_Speed": 0,
            "Torque": 0.0,
            "Tool_Wear": 67,
            "failure_label": "PWF_S3",
            "symptom": "Critical oil pressure loss - emergency shutdown",
            "Failure_Type": "Failure",
        },
    ],
    "diagnostics": {
        "fault_code": "PWF_S3",
        "engineModel": "ISB",
        "system_affected": "Lubrication System - Oil Pump",
        "symptoms": "Sudden oil pressure drop, oil pressure warning light, engine stall, possible metallic debris in oil",
        "diagnostic_steps": "1. Check oil level and condition\n2. Inspect for external oil leaks\n3. Remove oil pan and inspect pickup tube\n4. Check oil pump drive gear\n5. Inspect main bearings for damage\n6. Cut open oil filter and inspect for metal debris",
        "resolution": "Replace oil pump assembly if worn or damaged. Clean oil pickup screen. Replace oil filter. If bearing damage present, more extensive repair required. Flush oil system and refill with fresh oil.",
        "required_tools": ["Oil Pressure Test Kit", "Engine Hoist (if needed)", "Oil Pan Gasket Scraper", "Torque Wrench", "Magnetic Pickup Tool", "Borescope"],
        "required_parts": ["Oil Pump Assembly (ISB)", "Oil Pan Gasket", "Oil Pickup Tube O-ring", "Oil Filter", "10 Quarts 15W-40 Engine Oil"],
        "severity": 3,
        "estimated_repair_hours": 5.0,
    },
    "operations": [
        {
            "orderId": "WO-DEMO-004",
            "operationId": "OP-DEMO-004-10",
            "description": "Field diagnosis of oil system failure",
            "status": "Completed",
            "plannedStart": BASE_DATE + timedelta(days=3, hours=1),
            "plannedDuration": 1.0,
            "actualDuration": 1.0,
        },
        {
            "orderId": "WO-DEMO-004",
            "operationId": "OP-DEMO-004-20",
            "description": "Oil pump and pickup tube replacement",
            "status": "In Progress",
            "plannedStart": BASE_DATE + timedelta(days=3, hours=2),
            "plannedDuration": 3.5,
            "actualDuration": None,
        },
        {
            "orderId": "WO-DEMO-004",
            "operationId": "OP-DEMO-004-30",
            "description": "System test and harvest operation verification",
            "status": "Not Started",
            "plannedStart": BASE_DATE + timedelta(days=3, hours=5, minutes=30),
            "plannedDuration": 0.5,
            "actualDuration": None,
        },
    ],
    "confirmations": [
        {
            "orderId": "WO-DEMO-004",
            "confirmationId": "CNF-DEMO-004-A",
            "confirmationText": """FIELD ARRIVAL - INITIAL DIAGNOSIS
Arrived at Henderson Farm north field at 06:35 AM. Combine is approximately 3 miles from farmhouse, accessible via farm road.

AI Dispatch Pre-staging Success:
Thanks to the AI system analyzing the fault codes, I arrived with:
✓ Oil pump assembly for ISB engine
✓ Oil pan gasket and pickup tube O-ring
✓ Fresh oil and filters
✓ Complete diagnostic tools

Initial Findings:
- Oil level on dipstick: EMPTY (lost approximately 8 quarts)
- Large oil stain under combine (oil pooled in crop stubble)
- No external damage visible
- Oil filter cut-open test: Significant metallic debris present (brass colored - likely pump gear wear)

Diagnosis Confirmed: Oil pump failure. The pump's internal gears have worn, causing pressure loss and allowing rapid oil drain-back. Engine shutdown before bearing damage occurred (good news).

Beginning repair on-site. Farmer Tom is assisting with jack stands and lighting.
Weather holding - clear skies, temp 72°F.""",
            "confirmedAt": BASE_DATE + timedelta(days=3, hours=1),
            "actualWork": 1.0,
            "technician": "Mike Thompson",
        },
        {
            "orderId": "WO-DEMO-004",
            "confirmationId": "CNF-DEMO-004-B",
            "confirmationText": """REPAIR IN PROGRESS - OIL PUMP REPLACEMENT
Status Update at 09:30 AM

Work Completed:
✓ Oil pan removed (14 bolts, all in good condition)
✓ Oil pickup tube removed and cleaned
✓ Old oil pump removed - confirmed gear wear (Drive gear teeth worn 30% beyond spec)
✓ Oil passages inspected and flushed
✓ New oil pump installed and torqued to spec
✓ New pickup tube O-ring installed

Work In Progress:
- Reinstalling oil pan with new gasket
- Will add fresh oil and new filter next

Estimated Time to Completion: 1.5 hours

Farmer Update: Tom has postponed his morning farm errands to observe/assist. He's impressed with the speed of diagnosis and wants to discuss a preventive maintenance contract for all his Cummins equipment.

No bearing damage detected - engine should have full service life remaining.""",
            "confirmedAt": BASE_DATE + timedelta(days=3, hours=2, minutes=30),
            "actualWork": 1.0,
            "technician": "Mike Thompson",
        },
    ],
}


# =============================================================================
# DEMO WORK ORDER 5: Construction Equipment - Concrete Pour Deadline
# =============================================================================
DEMO_WO_5 = {
    "work_order": {
        "orderId": "WO-DEMO-005",
        "equipmentId": "PUMP-X15-003",
        "status": "Released",
        "priority": 2,
        "orderDate": BASE_DATE + timedelta(days=4),
        "actualWork": 0,
        "daysToSolve": None,
        "technician": "Jennifer Walsh",
        "faultCode": "RNF_S2",
        "issueDescription": """URGENT - CONCRETE PUMP TRUCK - PROJECT DEADLINE AT RISK

CUSTOMER COMPLAINT (Site Superintendent @ 07:15 AM):
"We've got a major problem at the Riverside Tower construction site. Our Putzmeister concrete pump truck with the X15 engine is showing some kind of random failure code and running rough. We've got 180 cubic yards of concrete scheduled for delivery starting at 9 AM for a critical foundation pour. If this pump goes down mid-pour, we'll have $50,000 worth of concrete setting up in the mixer trucks and a $200,000 delay on the project timeline. The engine is surging and sometimes hesitating—it hasn't shut down yet, but something is definitely wrong. Can you get someone here to check it out before we start the pour?"

TELEMATICS ALERT DETAILS:
- Fault Code Triggered: RNF_S2 (Random Failure - Severity 2)  
- Engine Model: Cummins X15
- Equipment: Putzmeister 47Z-Meter Concrete Pump
- Serial: PTZ-47Z-2023-4521
- Location: Riverside Tower Site, 500 Waterfront Blvd, Indianapolis
- Engine Hours: 6,234
- Last Service: 1,200 hours ago

TELEMETRY AT ALERT:
- Process Temperature: 195°F (Normal)
- Rotational Speed: Variable (1200-1650 RPM - should be steady 1500)
- Torque: Fluctuating
- Fuel Pressure: 38 PSI (Slightly low - spec: 42-48 PSI)
- Tool Wear Index: 52% (Normal)
- Engine Load: 65%

PRELIMINARY DIAGNOSIS:
Intermittent fuel delivery issue causing random misfires. Possible fuel filter restriction, injector issue, or fuel pump beginning to fail. Requires diagnosis before high-demand concrete pumping operation.

PROJECT INFORMATION:
- Customer: Turner Construction
- Project: Riverside Tower (12-story mixed-use)
- Site Super: Carlos Mendez - (317) 555-0167
- Pour Window: 9:00 AM - 4:00 PM (concrete trucks scheduled)
- Critical Path: Foundation must be poured today for project timeline

DISPATCH NOTES:
Time-sensitive diagnosis required. Need to determine if pump truck is safe for 7+ hours of continuous high-load operation. Bring fuel system diagnostic equipment and common fuel delivery parts. Site access through Gate 3 - hard hat required.""",
    },
    "machine_logs": [
        {
            "MachineID": "PUMP-X15-003",
            "logTimestamp": BASE_DATE + timedelta(days=4) - timedelta(hours=24),
            "Process_Temperature": 192.0,
            "Air_Temperature": 75.0,
            "Rotational_Speed": 1500,
            "Torque": 1850.0,
            "Tool_Wear": 51,
            "failure_label": "No_Failure",
            "symptom": "Normal operation",
            "Failure_Type": "Normal",
        },
        {
            "MachineID": "PUMP-X15-003",
            "logTimestamp": BASE_DATE + timedelta(days=4) - timedelta(hours=2),
            "Process_Temperature": 194.0,
            "Air_Temperature": 72.0,
            "Rotational_Speed": 1480,
            "Torque": 1820.0,
            "Tool_Wear": 52,
            "failure_label": "RNF_S1",
            "symptom": "Minor RPM fluctuation during warmup",
            "Failure_Type": "Warning",
        },
        {
            "MachineID": "PUMP-X15-003",
            "logTimestamp": BASE_DATE + timedelta(days=4) - timedelta(minutes=30),
            "Process_Temperature": 195.0,
            "Air_Temperature": 74.0,
            "Rotational_Speed": 1450,
            "Torque": 1780.0,
            "Tool_Wear": 52,
            "failure_label": "RNF_S2",
            "symptom": "Random misfires, fuel pressure low, engine surging",
            "Failure_Type": "Warning",
        },
    ],
    "diagnostics": {
        "fault_code": "RNF_S2",
        "engineModel": "X15",
        "system_affected": "Fuel System - Fuel Delivery",
        "symptoms": "Random misfires, engine surging, RPM fluctuation, hesitation under load, slightly low fuel pressure",
        "diagnostic_steps": "1. Check fuel tank for water/contamination\n2. Replace fuel filters (primary and secondary)\n3. Check fuel pressure at rail\n4. Inspect fuel lines for restrictions or air leaks\n5. Scan for additional stored codes\n6. Perform fuel injector balance test",
        "resolution": "Replace clogged fuel filters. Inspect and clean fuel tank if contamination found. Check fuel pump output pressure. Clear codes and road test under load.",
        "required_tools": ["Fuel Pressure Gauge Set", "Fuel Sample Kit", "Diagnostic Scanner", "Filter Wrench Set"],
        "required_parts": ["Primary Fuel Filter", "Secondary Fuel Filter", "Fuel Water Separator Element", "Fuel Line O-rings"],
        "severity": 2,
        "estimated_repair_hours": 1.5,
    },
    "operations": [
        {
            "orderId": "WO-DEMO-005",
            "operationId": "OP-DEMO-005-10",
            "description": "On-site fuel system diagnosis",
            "status": "Not Started",
            "plannedStart": BASE_DATE + timedelta(days=4, hours=1),
            "plannedDuration": 0.5,
            "actualDuration": None,
        },
        {
            "orderId": "WO-DEMO-005",
            "operationId": "OP-DEMO-005-20",
            "description": "Fuel filter replacement and system flush",
            "status": "Not Started",
            "plannedStart": BASE_DATE + timedelta(days=4, hours=1, minutes=30),
            "plannedDuration": 1.0,
            "actualDuration": None,
        },
        {
            "orderId": "WO-DEMO-005",
            "operationId": "OP-DEMO-005-30",
            "description": "Load test and release for operation",
            "status": "Not Started",
            "plannedStart": BASE_DATE + timedelta(days=4, hours=2, minutes=30),
            "plannedDuration": 0.5,
            "actualDuration": None,
        },
    ],
    "confirmations": [],  # Work order just released, no confirmations yet
}


# =============================================================================
# INSERT ALL DEMO DATA
# =============================================================================

def insert_demo_data():
    """Insert all demo work orders and related data into MongoDB."""
    
    all_demos = [DEMO_WO_1, DEMO_WO_2, DEMO_WO_3, DEMO_WO_4, DEMO_WO_5]
    
    for demo in all_demos:
        wo = demo["work_order"]
        order_id = wo["orderId"]
        print(f"\n{'='*60}")
        print(f"Creating {order_id}: {wo.get('faultCode', 'N/A')}")
        print(f"Equipment: {wo['equipmentId']}")
        print(f"Status: {wo['status']}")
        print(f"{'='*60}")
        
        # Insert work order
        db.workorders.update_one(
            {"orderId": order_id},
            {"$set": wo},
            upsert=True
        )
        print(f"✓ Work order inserted/updated")
        
        # Insert machine logs
        for log in demo.get("machine_logs", []):
            db.machinelogs.update_one(
                {"MachineID": log["MachineID"], "logTimestamp": log["logTimestamp"]},
                {"$set": log},
                upsert=True
            )
        print(f"✓ {len(demo.get('machine_logs', []))} machine logs inserted")
        
        # Insert diagnostics
        if "diagnostics" in demo:
            diag = demo["diagnostics"]
            db.diagnostics.update_one(
                {"fault_code": diag["fault_code"], "engineModel": diag["engineModel"]},
                {"$set": diag},
                upsert=True
            )
            print(f"✓ Diagnostics inserted for {diag['fault_code']}")
        
        # Insert operations
        for op in demo.get("operations", []):
            db.operations.update_one(
                {"operationId": op["operationId"]},
                {"$set": op},
                upsert=True
            )
        print(f"✓ {len(demo.get('operations', []))} operations inserted")
        
        # Insert confirmations
        for conf in demo.get("confirmations", []):
            db.confirmations.update_one(
                {"confirmationId": conf["confirmationId"]},
                {"$set": conf},
                upsert=True
            )
        print(f"✓ {len(demo.get('confirmations', []))} confirmations inserted")
    
    print("\n" + "="*60)
    print("DEMO DATA CREATION COMPLETE")
    print("="*60)
    
    # Summary
    print("\nDEMO WORK ORDERS CREATED:")
    print("-" * 80)
    print(f"{'Order ID':<15} {'Equipment':<20} {'Status':<12} {'Fault Code':<10} {'Description':<30}")
    print("-" * 80)
    
    for demo in all_demos:
        wo = demo["work_order"]
        desc = wo["issueDescription"].split("\n")[0][:30]
        print(f"{wo['orderId']:<15} {wo['equipmentId']:<20} {wo['status']:<12} {wo.get('faultCode', 'N/A'):<10} {desc}")
    
    print("-" * 80)
    
    # Confirmation counts
    print("\nCONFIRMATIONS BY WORK ORDER:")
    for demo in all_demos:
        wo = demo["work_order"]
        confs = demo.get("confirmations", [])
        print(f"  {wo['orderId']}: {len(confs)} confirmations")
    
    total_confs = sum(len(d.get("confirmations", [])) for d in all_demos)
    print(f"\nTOTAL CONFIRMATIONS: {total_confs}")
    
    return all_demos


if __name__ == "__main__":
    demos = insert_demo_data()
