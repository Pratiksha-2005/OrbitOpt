# OrbitOpt API Contract & Frontend Integration Guide (v1)

This document establishes the official API contract, mathematical formulation, TypeScript types, and integration guide for the **OrbitOpt: Autonomous Ground Station Scheduling for Multi-Satellite Downlink** system.

- **Backend Base URL**: `http://localhost:8000`
- **API Base Route**: `/api/v1`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Raw OpenAPI Schema**: `http://localhost:8000/openapi.json`
- **DateTime Format**: UTC ISO 8601 string (`YYYY-MM-DDTHH:MM:SSZ` or `2026-10-10T12:00:00Z`)
- **Units**:
  - **Durations**: `seconds` ($s$)
  - **Data Volumes**: `Gigabytes` (decimal GB, $1\text{ GB} = 10^9\text{ Bytes} = 1000\text{ MB} = 8000\text{ Mbits}$)
  - **Data Transmission Rates**: `Mbps` (Megabits per second, $10^6\text{ bits/s}$)
  - **Coordinates**: Latitude $\in [-90.0, 90.0]^\circ$, Longitude $\in [-180.0, 180.0]^\circ$
  - **Elevation Masks**: Minimum horizon elevation in degrees $\in [0.0, 90.0]^\circ$
  - **Priorities**: Integer $1 \dots 5$ ($1 = \text{Critical/Highest}$, $5 = \text{Lowest}$)

---

## 1. Mathematical Formulation & Units

### A. Transferable Data Volume Calculation
$$\text{Channel Capacity (GB)}_i = \frac{\text{effective\_data\_rate\_mbps}_i \times \text{usable\_duration\_seconds}_i}{8000.0}$$
$$\text{Transferable Data (GB)}_i = \min\left( \text{pending\_data\_gb}_i, \; \text{Channel Capacity (GB)}_i \right)$$

### B. Global Optimization Objective
$$\text{Objective Value} = \sum_{i \in \text{Scheduled}} \left( w_{p(i)} \times \text{transferable\_data\_gb}_i \right)$$

**Default Priority Weights**:
- Priority 1 (Critical): $w_1 = 10.0$
- Priority 2 (High): $w_2 = 5.0$
- Priority 3 (Medium): $w_3 = 2.0$
- Priority 4 (Low): $w_4 = 1.0$
- Priority 5 (Lowest): $w_5 = 0.5$

---

## 2. API Endpoints Summary

| Method | Endpoint Path | Summary | Persists Data? | Status Codes |
|---|---|---|---|---|
| `GET` | `/health` | Root system health & DB status | No | `200` |
| `GET` | `/api/v1/health` | Versioned system health | No | `200` |
| `POST` | `/api/v1/datasets` | Create & validate scenario dataset | **Yes** (`datasets` table) | `201`, `422` |
| `GET` | `/api/v1/datasets/{dataset_id}` | Retrieve scenario dataset | No | `200`, `404` |
| `POST` | `/api/v1/schedules/baseline` | Run real First-Come-First-Served schedule | **Yes** (`schedule_runs` table) | `200`, `404`, `500` |
| `POST` | `/api/v1/schedules/optimize` | Run real OR-Tools CP-SAT optimizer | **Yes** (`schedule_runs` table) | `200`, `404`, `500` |
| `GET` | `/api/v1/schedules/{run_id}` | Retrieve schedule run details & timeline | No | `200`, `404` |
| `GET` | `/api/v1/schedules/{run_id}/metrics` | Retrieve comparative metrics & KPIs | No | `200`, `404` |

---

## 3. Detailed Endpoint Contracts

### 3.1 Health Check
**`GET /health`** or **`GET /api/v1/health`**
- **Success Response (`200 OK`)**:
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2026-10-09T17:00:00Z",
    "environment": "development",
    "database_connected": true
  }
  ```

---

### 3.2 Dataset Creation
**`POST /api/v1/datasets`**
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "name": "LEO Multi-Satellite Scenario",
    "description": "Scenario with 2 ground stations and 4 pass opportunities",
    "ground_stations": [
      {
        "station_id": "GS-SVALBARD",
        "name": "Svalbard Arctic Station",
        "latitude_deg": 78.2297,
        "longitude_deg": 15.4077,
        "elevation_mask_deg": 5.0,
        "max_concurrent_passes": 1,
        "supported_bands": ["S-band", "X-band"]
      }
    ],
    "satellite_passes": [
      {
        "pass_id": "PASS-SAT01-001",
        "satellite_id": "SAT-EARTHOBS-1",
        "ground_station_id": "GS-SVALBARD",
        "start_time": "2026-10-10T12:00:00Z",
        "end_time": "2026-10-10T12:10:00Z",
        "max_elevation_deg": 65.0,
        "priority": 1,
        "data_volume_gb": 4.0,
        "pending_data_gb": 4.0,
        "effective_data_rate_mbps": 150.0,
        "channel_band": "X-band"
      }
    ]
  }
  ```
- **Success Response (`201 Created`)**:
  ```json
  {
    "dataset_id": "ds_8f7b2c14-5231-4e9b-b4a1-0f37f34c988a",
    "name": "LEO Multi-Satellite Scenario",
    "description": "Scenario with 2 ground stations and 4 pass opportunities",
    "ground_station_count": 1,
    "satellite_pass_count": 1,
    "created_at": "2026-10-09T17:00:00Z",
    "ground_stations": [...],
    "satellite_passes": [...]
  }
  ```

---

### 3.3 Run Baseline Schedule (FCFS)
**`POST /api/v1/schedules/baseline`**
- **Request Body**:
  ```json
  {
    "dataset_id": "ds_8f7b2c14-5231-4e9b-b4a1-0f37f34c988a",
    "setup_time_seconds": 60
  }
  ```
- **Success Response (`200 OK`)**:
  ```json
  {
    "run_id": "run_fcfs_93a1c",
    "dataset_id": "ds_8f7b2c14-5231-4e9b-b4a1-0f37f34c988a",
    "algorithm": "baseline_fcfs",
    "status": "completed",
    "is_mock": false,
    "is_valid": true,
    "validation_violations": [],
    "solver_status_detail": "FEASIBLE",
    "created_at": "2026-10-09T17:01:00Z",
    "execution_time_ms": 12.4,
    "scheduled_passes": [
      {
        "pass_id": "PASS-SAT01-001",
        "satellite_id": "SAT-EARTHOBS-1",
        "ground_station_id": "GS-SVALBARD",
        "start_time": "2026-10-10T12:00:00Z",
        "end_time": "2026-10-10T12:03:34Z",
        "duration_seconds": 214.0,
        "data_volume_gb": 4.0,
        "transferable_data_gb": 4.0,
        "priority": 1
      }
    ],
    "unassigned_passes": [],
    "metrics": {
      "total_passes": 1,
      "scheduled_passes_count": 1,
      "unassigned_passes_count": 0,
      "scheduled_percentage": 100.0,
      "total_data_downlinked_gb": 4.0,
      "total_pending_data_gb": 4.0,
      "total_contact_time_seconds": 214.0,
      "objective_value": 40.0,
      "priority_satisfaction_rate": 100.0,
      "priority_breakdown": { "1": 1 },
      "ground_station_utilization": { "GS-SVALBARD": 100.0 },
      "conflicts_detected": 0
    }
  }
  ```

---

### 3.4 Run Schedule Optimizer (CP-SAT)
**`POST /api/v1/schedules/optimize`**
- **Request Body**:
  ```json
  {
    "dataset_id": "ds_8f7b2c14-5231-4e9b-b4a1-0f37f34c988a",
    "time_limit_seconds": 30.0,
    "setup_time_seconds": 60,
    "priority_weights": {
      "1": 10.0,
      "2": 5.0,
      "3": 2.0,
      "4": 1.0,
      "5": 0.5
    },
    "maximize_data_volume": true
  }
  ```
- **Success Response (`200 OK`)**:
  Same unified `ScheduleRunResponse` schema, with `algorithm: "cp_sat_optimizer"` and `solver_status_detail: "OPTIMAL"`.

---

### 3.5 Retrieve Schedule Run & Metrics
- **`GET /api/v1/schedules/{run_id}`** $\to$ Returns full `ScheduleRunResponse`.
- **`GET /api/v1/schedules/{run_id}/metrics`** $\to$ Returns embedded `ScheduleMetrics` object.

---

### 3.6 Error Response Schema
All error responses adhere to standard JSON:
```json
{
  "detail": "Dataset with ID 'ds_missing' was not found.",
  "error_code": "RESOURCE_NOT_FOUND",
  "details": []
}
```

**Standard Error Codes**:
- `RESOURCE_NOT_FOUND` (`404`): Dataset or Run ID does not exist.
- `VALIDATION_ERROR` (`422`): Request payload failed Pydantic schema validation.
- `DATASET_VALIDATION_ERROR` (`422`): Scenario data contains temporal or negative volume errors.
- `SCHEDULING_ENGINE_ERROR` (`500`): Solver crash or internal algorithm failure.

---

## 4. TypeScript Type Definitions for Frontend

```typescript
// types/api.ts

export type PriorityLevel = 1 | 2 | 3 | 4 | 5;

export type AlgorithmType = 'baseline_fcfs' | 'cp_sat_optimizer' | 'mock_integration';

export type ScheduleStatus = 'completed' | 'failed' | 'running' | 'infeasible' | 'timeout';

export interface GroundStation {
  station_id: string;
  name: string;
  latitude_deg: number;
  longitude_deg: number;
  elevation_mask_deg?: number;
  max_concurrent_passes?: number;
  supported_bands?: string[];
}

export interface SatellitePass {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  start_time: string; // ISO 8601 UTC
  end_time: string;   // ISO 8601 UTC
  max_elevation_deg: number;
  priority: PriorityLevel;
  data_volume_gb: number;
  pending_data_gb?: number;
  effective_data_rate_mbps?: number;
  channel_band?: string;
}

export interface Dataset {
  dataset_id: string;
  name: string;
  description?: string;
  ground_station_count: number;
  satellite_pass_count: number;
  created_at: string;
  ground_stations: GroundStation[];
  satellite_passes: SatellitePass[];
}

export interface ScheduledPass {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  data_volume_gb: number;
  transferable_data_gb: number;
  priority: PriorityLevel;
}

export interface UnassignedPass {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  start_time: string;
  end_time: string;
  priority: PriorityLevel;
  reason: string;
}

export interface ScheduleMetrics {
  total_passes: number;
  scheduled_passes_count: number;
  unassigned_passes_count: number;
  scheduled_percentage: number;
  total_data_downlinked_gb: number;
  total_pending_data_gb: number;
  total_contact_time_seconds: number;
  objective_value: number;
  priority_satisfaction_rate: number;
  priority_breakdown: Record<string, number>;
  ground_station_utilization: Record<string, number>;
  conflicts_detected: number;
}

export interface ScheduleRunResponse {
  run_id: string;
  dataset_id: string;
  algorithm: AlgorithmType;
  status: ScheduleStatus;
  is_mock: boolean;
  is_valid: boolean;
  validation_violations: string[];
  solver_status_detail?: string; // 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'TIMEOUT'
  created_at: string;
  execution_time_ms: number;
  scheduled_passes: ScheduledPass[];
  unassigned_passes: UnassignedPass[];
  metrics: ScheduleMetrics;
}

export interface ApiErrorResponse {
  detail: string;
  error_code: string;
  details?: unknown[];
}
```

---

## 5. React / Axios Integration Example

```typescript
// services/orbitOptApi.ts
import axios from 'axios';
import type { Dataset, ScheduleRunResponse, ScheduleMetrics } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const createDataset = async (data: Omit<Dataset, 'dataset_id' | 'created_at' | 'ground_station_count' | 'satellite_pass_count'>): Promise<Dataset> => {
  const response = await apiClient.post<Dataset>('/datasets', data);
  return response.data;
};

export const getDataset = async (datasetId: string): Promise<Dataset> => {
  const response = await apiClient.get<Dataset>(`/datasets/${datasetId}`);
  return response.data;
};

export const runBaseline = async (datasetId: string, setupTimeSeconds = 60): Promise<ScheduleRunResponse> => {
  const response = await apiClient.post<ScheduleRunResponse>('/schedules/baseline', {
    dataset_id: datasetId,
    setup_time_seconds: setupTimeSeconds,
  });
  return response.data;
};

export const runOptimize = async (
  datasetId: string,
  timeLimitSeconds = 30.0,
  priorityWeights?: Record<string, number>
): Promise<ScheduleRunResponse> => {
  const response = await apiClient.post<ScheduleRunResponse>('/schedules/optimize', {
    dataset_id: datasetId,
    time_limit_seconds: timeLimitSeconds,
    priority_weights: priorityWeights || { '1': 10.0, '2': 5.0, '3': 2.0, '4': 1.0, '5': 0.5 },
  });
  return response.data;
};

export const getScheduleRun = async (runId: string): Promise<ScheduleRunResponse> => {
  const response = await apiClient.get<ScheduleRunResponse>(`/schedules/${runId}`);
  return response.data;
};

export const getScheduleMetrics = async (runId: string): Promise<ScheduleMetrics> => {
  const response = await apiClient.get<ScheduleMetrics>(`/schedules/${runId}/metrics`);
  return response.data;
};
```

---

## 6. Recommended Frontend State Flow

1. **Scenario Selection / Creation**:
   - Show list or file upload of scenarios.
   - On upload / submit $\to$ call `createDataset()` $\to$ store `dataset_id`.
2. **Comparison Execution**:
   - Provide **"Run Comparison"** button that executes both `runBaseline(dataset_id)` and `runOptimize(dataset_id)`.
   - Show loading progress bar / spinner during solver execution.
3. **Displaying Results**:
   - **Gantt / Timeline View**: Render `scheduled_passes` color-coded by satellite or ground station.
   - **KPI Cards**: Display `objective_value`, `total_data_downlinked_gb`, `scheduled_percentage`, `execution_time_ms`.
   - **Mock Badge**: If `is_mock === true`, display a badge: `[MOCK ENGINE]`.
   - **Validation Alert**: If `is_valid === false`, display an alert with `validation_violations`.
   - **Unassigned Table**: Render `unassigned_passes` with their `reason` string explaining dropped conflicts.
