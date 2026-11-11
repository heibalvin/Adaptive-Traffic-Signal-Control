# ATCS Simulator

Branch: `Simulator` (from `main`). Provides MQTT-based traffic stub devices/managers and Compose deployment.

## Components

- **Devices** (`Simulator/Devices/`)
  - `generator_device.py` (`generatorDevice`): traffic source state machine (rate, 1440-min probability profile, tick/emission, state).
  - `absorber_device.py` (`absorberDevice`): traffic sink state machine (capacity, attraction profile, ingest/tick/queue, state).
  - `road_device.py` (`roadDevice`): road segment state (capacity, speed, flow, queue, occupancy, open/closed).
- **Managers** (`Simulator/Managers/`)
  - `generator_manager.py`, `absorber_manager.py`, `road_manager.py`: subscribe to device telemetry, cache state, publish manager telemetry, and send command/variable updates to devices over MQTT.
- **Common** (`Simulator/Common/mqtt.py`): topic helpers, `DeviceType/DeviceState`, message envelope.
- **Topology Filler** (`../Topology/Filler/filler.py`): adds generator/absorber stubs to an existing topology and writes `country-town-district-topology-filler.json/png` (or `.png.txt`).

## MQTT contract

- Device telemetry (device -> broker/managers): `devices/{district_id}/{intersection_id}/{device_type}/{device_id}/telemetry`
- Device command (manager -> device): `devices/{district_id}/{intersection_id}/{device_type}/{device_id}/command`
- Manager telemetry: `managers/{device_type}/{manager_id}/telemetry`

Message payloads are JSON (`type`, `device_type`, `device_id`, `district_id`, `intersection_id`, `state`, `payload`, `ts`, `msg_id`, `source`). Command payloads: `{"action":"activate|stop|ready|reset|update|tick|ingest|flow_update","params":{...}}`.

## Docker deployment

Prereq: Docker + Docker Compose. From repo root:

```bash
docker compose -f Simulator/docker-compose.yml up --build -d
docker compose -f Simulator/docker-compose.yml ps
docker compose -f Simulator/docker-compose.yml logs -f --tail=100
```

Compose project: `atcs` (same as `Topology/docker-compose.yml`). Services/images:

| Service | Image | Role |
|---|---|---|
| `mqtt` | `eclipse-mosquitto:2.1.2-alpine` | MQTT broker (`1883`) |
| `generator-device` | `atcs-generator-device:dev` | Generator device |
| `absorber-device` | `atcs-absorber-device:dev` | Absorber device |
| `road-device` | `atcs-road-device:dev` | Road device |
| `generator-manager` | `atcs-generator-manager:dev` | Generator manager |
| `absorber-manager` | `atcs-absorber-manager:dev` | Absorber manager |
| `road-manager` | `atcs-road-manager:dev` | Road manager |

Default runtime IDs (override with env vars): `DISTRICT_ID=district-1`, `GENERATOR_DEVICE_ID=gen-1`, `ABSORBER_DEVICE_ID=abs-1`, `ROAD_DEVICE_ID=road-1`, `INTERSECTION_ID=boundary|segment`.

```bash
# example: custom district/device IDs
DISTRICT_ID=downtown-dubai GENERATOR_DEVICE_ID=gen-dd-1 \
  docker compose -f Simulator/docker-compose.yml up --build -d
```

Stop:

```bash
docker compose -f Simulator/docker-compose.yml down
```

## Local run (without Docker)

Requires MQTT broker and `paho-mqtt`:

```bash
pip install -r Simulator/requirements.txt

# Devices
python3 -m Simulator.Devices.generator_device --device-id gen-1 --district-id d1 --broker-host localhost
python3 -m Simulator.Devices.absorber_device  --device-id abs-1 --district-id d1 --broker-host localhost
python3 -m Simulator.Devices.road_device      --device-id road-1 --district-id d1 --broker-host localhost

# Managers
python3 -m Simulator.Managers.generator_manager --broker-host localhost
python3 -m Simulator.Managers.absorber_manager  --broker-host localhost
python3 -m Simulator.Managers.road_manager      --broker-host localhost
```

## Topology Filler

Adds generator/absorber stub data to an existing topology and produces `country-town-district-topology-filler.json/png`:

```bash
python3 -m Topology.Filler.filler \
  --country "United Arab Emirates" --town "Dubai" --district "Downtown Dubai" \
  --in-json Topology/Data/uae-dubai-downtown-topology.json
# -> Topology/Data/united-arab-emirates-dubai-downtown-dubai-topology-filler.json
# -> ...-topology-filler.png (copied if --in-png provided) or .png.txt marker
```

## Notes

- Device/manager runtime depends on `paho-mqtt` and a reachable MQTT broker.
- Managers send variable changes to devices on command topics; devices publish state/telemetry back on telemetry topics.
- Uses the same Compose project name as `Topology/docker-compose.yml` (`atcs`), so both stacks can be managed under one project. If port `1883` conflicts with an existing broker, stop it or change the `mqtt` port mapping.

