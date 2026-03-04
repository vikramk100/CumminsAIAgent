from dotenv import load_dotenv
load_dotenv()

print("About to import agents")
from agents import run_orchestrator
print("Imported run_orchestrator OK")

print("Calling run_orchestrator...")
reply = run_orchestrator("Test message from script")
print("Got reply:", reply)