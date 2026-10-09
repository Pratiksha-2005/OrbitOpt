# SatNet Benchmark Comparison Report (W10_2018)

- **Dataset Path:** `E:\Space-Tech\OrbitOpt\datasets\satnet-master\data`
- **Timestamp (UTC):** `2026-10-09T14:23:55Z`
- **Total Requests:** 257 (1191.5 total requested contact hours)
- **Candidate Windows:** 2513
- **Ground Network:** 12 physical DSN antennas, 27 composite arrays
- **Maintenance Outages:** 37 intervals (174.2 hours)

## Performance Comparison

| Metric | FCFS Baseline | OR-Tools CP-SAT | Optimization Delta |
| :--- | :---: | :---: | :---: |
| **Solver Status** | `FEASIBLE` | `FEASIBLE` | — |
| **Independent Validation** | `0 Violations` | `0 Violations` | Feasible & Conflict-Free |
| **Scheduled Requests** | 214 / 257 | 223 / 257 | **+9 requests (+3.50%)** |
| **Request Satisfaction Rate** | 83.27% | 86.77% | **+3.50%** |
| **Scheduled Contact Hours** | 837.30h | 896.83h | **+59.53 hours** |
| **Hours Completion Rate** | 70.27% | 75.27% | **+5.00%** |
| **Rejected Requests** | 43 | 34 | **-9 rejected** |
| **Runtime** | 0.0031s | 30.34s | 30.0s solver limit |

## Constraint & Metric Notes
- **Outcome Metric:** NASA DSN SatNet evaluates operational contact hours and request satisfaction, not synthetic data volume or throughput (no GB or Mbps).
- **Solver Optimality Status:** CP-SAT returned `FEASIBLE` within its 30-second execution time budget. It is not marked as `OPTIMAL` because exploration was terminated upon reaching the time limit.
- **Conflict Prevention:** All composite antenna arrays (`DSS-24_DSS-25`, etc.) accurately reserved all constituent dishes, and all maintenance blocks were respected.