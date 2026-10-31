import argparse

from server.config import Settings
from server.service import Service

parser = argparse.ArgumentParser(description="Activate current configuration for one authorized local event")
parser.add_argument("--event", required=True)
args = parser.parse_args()
Service(Settings.environment()).activate_configuration(args.event)
print("Configuration activated; compatible vectors reused and necessary work queued.")
