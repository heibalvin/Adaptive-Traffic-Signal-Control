FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY Simulator/requirements.txt /app/Simulator/requirements.txt
RUN pip install --no-cache-dir -r /app/Simulator/requirements.txt
COPY Simulator /app/Simulator
CMD ["python", "-m", "Simulator.Devices.road_device", "--device-id", "road-1", "--district-id", "district-1", "--broker-host", "mqtt"]
