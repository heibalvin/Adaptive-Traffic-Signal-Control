"""ATCS Topology Viewer (Sprint 1).

Visual viewer that renders overlay canvas sprites (roads, lights, intersections,
districts) over a layout background image map, refreshed from PostgreSQL/topology
state.
"""

from .app import main

__all__ = ["main"]
