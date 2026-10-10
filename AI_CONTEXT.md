# OrbitOpt: Autonomous Ground Station Scheduling for Multi-Satellite Downlink

## Team Roles & Ownership Matrix
- **Developer 1 (Scheduling & Optimization)**:
  - Baseline FCFS scheduling algorithm
  - OR-Tools CP-SAT multi-satellite optimizer
  - Conflict detection engine & setup-time constraint satisfaction
  - Independent schedule validation module
  - Location: `backend/app/services/optimizer/` / `backend/app/services/scheduler/`

- **Developer 2 (Backend API & Data Persistence - Current Ownership)**:
  - FastAPI application entrypoint & API routers (`backend/app/main.py`, `backend/app/api/`)
  - Pydantic schemas for data validation & API contracts (`backend/app/schemas/`)
  - Database layer: SQLAlchemy 2.x models, async/sync sessions, Alembic migrations (`backend/app/db/`, `backend/alembic/`)
  - Dataset & Schedule persistence services (`backend/app/services/`)
  - API and schema test suites (`backend/tests/`)
  - Shared API contracts (`docs/API_CONTRACT.md`)

- **Developer 3 (Frontend & Visualization)**:
  - React + Vite + TypeScript application
  - Dashboard, interactive timeline/Gantt charts for passes, map view of ground stations
  - Scenario configuration and comparative metrics charts (Baseline vs Optimized)

- **Developer 4 (DevOps, QA, Integration & Performance)**:
  - Docker & Docker Compose setup (FastAPI + PostgreSQL + Frontend)
  - CI/CD workflows, automated integration pipelines
  - End-to-end testing, benchmarking & performance profiling

---

## Directory Structure
```
OrbitOpt/
├── docs/
│   ├── API_CONTRACT.md
│   └── AI_CONTEXT.md
├── backend/
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── errors.py
│   │   ├── schemas/
│   │   │   ├── common.py
│   │   │   ├── ground_station.py
│   │   │   ├── satellite_pass.py
│   │   │   ├── dataset.py
│   │   │   ├── schedule.py
│   │   │   └── metrics.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── models/
│   │   ├── services/
│   │   │   ├── scheduler_interface.py
│   │   │   ├── mock_scheduler.py
│   │   │   ├── dataset_service.py
│   │   │   ├── schedule_service.py
│   │   │   └── scheduler/
│   │   │       ├── __init__.py
│   │   │       ├── models.py
│   │   │       ├── validator.py
│   │   │       ├── fcfs.py
│   │   │       ├── cpsat.py
│   │   │       └── real_engine.py
│   │   └── api/
│   │       ├── deps.py
│   │       └── v1/
│   │           ├── router.py
│   │           └── endpoints/
│   └── tests/
│       ├── conftest.py
│       ├── api/
│       └── unit/
└── frontend/ (Developer 3)

---

## Status Checkpoint (Stage 4 Complete: End-to-End Backend Verification)
- **Real Scheduler Engine Audit**: 100% logic parity verified against `origin/feature/optimization-engine`. Adapter accurately bridges FastAPI schemas with Developer 1 domain models without altering solver or validation logic.
- **End-to-End API Flow**: Full lifecycle tested: dataset creation, retrieval, real FCFS baseline execution, real CP-SAT optimization execution, run retrieval, metrics retrieval, and database persistence matching API outputs.
- **Mathematical Consistency**: Objective function $\sum w_p \times \text{transferable\_data}$ independently verified against small deterministic test cases.
- **Independent Validation**: `ScheduleValidator` is confirmed to execute on all solver outputs; invalid schedules are rejected and violations are surfaced.
- **Database Status**: Models and migrations verified with `alembic check` (0 diffs). PostgreSQL live test requires credentials configured in `backend/.env`.
- **Test Suite**: 28 passed in 0.83s with zero warnings across unit, integration, and end-to-end API tests.

