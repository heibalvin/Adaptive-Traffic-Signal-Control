# Adaptive-Traffic-Signal-Control

Adaptive Traffic Signal Control (ATCS) is an agentic AI system for intelligent, optimized, and self-healing traffic signal control based on LangGraph/LangChain.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Traffic     │────▶│              │────▶│              │
│ Light Agent │     │   KAFKA      │     │   POSTGRES   │
│  (CRUD)     │◀────│  (events)    │◀────│  (persistence│
└──────┬──────┘     └──────┬───────┘     └──────────────┘
       │                   │
       │    ┌──────────────▼──────────────┐
       │    │   Traffic Light Devices     │
       │    │  (autonomous state machines)│
       │    └──────────────▲──────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌──────────────┐
│   WEB APP   │◀────│  Kafka Events│
│ (Flask+SIO) │     └──────────────┘
└─────────────┘
```

## Components

### TrafficLightDevice
- **Data model**: `greenTimer` (50s), `orangeTimer` (5s), `redTimer` (240s), `state`, `colour`
- **States**: `IDLE`, `ACTIVE` (RED→GREEN→ORANGE), `INACTIVE` (ORANGE blinking)
- **Outbound events**: `hasChangeState`, `hasChangedColour`
- **Inbound events**: `willChangeTimer`, `willChangeState`, `willChangeColour`

### TrafficLightAgent
- Creates, reads, updates, deletes traffic light devices
- Communicates via Kafka topics
- Persists events to PostgreSQL

### Kafka Topics
- `traffic.light.events` - outbound events from devices
- `traffic.light.commands` - inbound commands to devices
- `traffic.light.agent` - agent-level events

### PostgreSQL Tables
- `traffic_lights` - device metadata and current state
- `traffic_light_events` - audit log of all Kafka events

### Web App
- Flask + Flask-SocketIO for real-time visualization
- Monitors Kafka events and updates UI live

## Setup

1. Copy `sample.env` to `.env` and adjust values:
```bash
cp sample.env .env
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start services (choose one mode):

```bash
# Agent mode (manages device fleet)
python -m atcs.main agent

# Device mode (single traffic light)
python -m atcs.main device tl-001

# Web app mode
python -m atcs.main web
```

## Environment Variables

See `sample.env` for configuration:
- `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `KAFKA_HOST`, `KAFKA_CLUSTER_ID`

## Docker

```bash
docker build -t atcs .
docker run -p 5000:5000 --env-file .env atcs
```