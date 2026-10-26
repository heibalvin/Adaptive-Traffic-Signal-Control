# Adaptive-Traffic-Signal-Control

Adaptive Traffic Signal Control (ATCS) is an agentic AI system for intelligent, optimized, and self-healing traffic signal control based on LangGraph/LangChain.

## Environment
- python 3.12.13 (using pyenv local 3.12.13)
- virtual python environment venv (python -m venv .venv)
- Cloud Data systems running in docker project aicd accessible through .env environment variables: apache/kafka:4.3.1

## Architecture
- **Traffic Light Device**: Runs autonomously, communicates via Kafka topics (producer/consumer), changes state based on Kafka messages
- **Traffic Light Group**: Manages fleet of devices through registration/unregistration, tracks device states in Postgres, sends/receives Kafka messages, provides REST API (port 9000)
- **Kafka Broker**: Communication between devices and group

## Installation

### Setup Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration
Copy and configure environment variables:
```bash
cp sample.env .env
# Edit .env with your Kafka configuration
```

## Testing

### Start Traffic Light Group (Terminal 1)
```bash
source .venv/bin/activate
python -m trafficLightGroup.app
```
Group runs on http://localhost:9000

### Start Traffic Light Device(s) (Terminal 2+)
```bash
source .venv/bin/activate
# Set device ID
export DEVICE_ID=TL-001
python -m trafficLightDevice.app
```

### API Usage (Group)
```bash
# Get all devices
curl http://localhost:9000/devices

# Send command to change state
curl -X POST http://localhost:9000/devices/TL-001/command \
  -H "Content-Type: application/json" \
  -d '{"command": "willChangeState", "state": "ACTIVE"}'

# Send command to change colour
curl -X POST http://localhost:9000/devices/TL-001/command \
  -H "Content-Type: application/json" \
  -d '{"command": "willChangeColour", "colour": "GREEN"}'

# Send command to change timer
curl -X POST http://localhost:9000/devices/TL-001/command \
  -H "Content-Type: application/json" \
  -d '{"command": "willChangeTimer", "timer": 60}'
```
