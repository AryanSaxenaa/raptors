"""Dogfood Portal -- a self-hostable hackathon submission and judging platform.

Built for DOGFOOD 2026. The interesting parts, in the order a reviewer probably
wants them:

    security.py    the role-isolation matrix, as a data structure, plus every
                   deny path in the system
    normalize.py   cross-judge score normalization and the proof of it
    schema.sql     the data model, with the constraints the database enforces
    audit.py       the append-only, hash-chained audit trail
    routers/       the HTTP surface; projects.py documents the deadline ordering
"""

__version__ = "1.0.0"
