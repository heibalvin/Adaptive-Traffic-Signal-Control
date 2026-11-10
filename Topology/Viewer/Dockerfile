FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ATCS_EXTRACTOR_URL=http://topology-extractor:8010

WORKDIR /app

COPY Topology/Viewer/requirements.txt /app/Topology/Viewer/requirements.txt
RUN pip install -r /app/Topology/Viewer/requirements.txt

COPY Topology /app/Topology

EXPOSE 8011

CMD ["uvicorn", "Topology.Viewer.api:app", "--host", "0.0.0.0", "--port", "8011"]
