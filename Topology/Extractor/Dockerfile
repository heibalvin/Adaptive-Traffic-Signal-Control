FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ATCS_TOPOLOGY_DATA_DIR=/app/Topology/Data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    proj-data \
    && rm -rf /var/lib/apt/lists/*

COPY Topology/Extractor/requirements.txt /app/Topology/Extractor/requirements.txt
RUN pip install -r /app/Topology/Extractor/requirements.txt

COPY Topology /app/Topology

EXPOSE 8010

CMD ["uvicorn", "Topology.Extractor.api:app", "--host", "0.0.0.0", "--port", "8010"]
