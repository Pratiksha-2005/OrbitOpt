# NASA Deep Space Network (SatNet) Integration & Benchmark Guide

## 1. Overview & Dataset Attribution

OrbitOpt includes an adapter, validator, and benchmark execution pipeline for the **NASA Deep Space Network (DSN) SatNet** benchmark problem suite.

- **Primary Source:** SatNet Benchmark Dataset (`problems.json`, `maintenance.csv`).
- **Research References:**
  1. *Scheduling Deep Space Network Antennas using Reinforcement Learning*, IEEE Aerospace Conference (2021) — [IEEE Xplore](https://ieeexplore.ieee.org/abstract/document/9438519/)
  2. *Deep Reinforcement Learning for Deep Space Network Scheduling*, AAAI Workshop on Machine Learning for Operations Research (ML4OR 2021) — [OpenReview](https://openreview.net/forum?id=buIUxK7F-Bx)
- **Licensing & Placement:**
  Place the extracted SatNet dataset under `datasets/satnet-master/data/` (containing `problems.json` and `maintenance.csv`). The dataset files remain external / git-ignored to prevent excessive repository bloat while maintaining reproducible local execution.

---

## 2. SatNet Problem Formulation & Supported Constraints

Unlike synthetic pass models that prioritize data volume (GB) or arbitrary priority weights, the SatNet problem is strictly grounded in **Deep Space Network (DSN) mission operations**:

### Supported & Enforced Constraints
1. **At-Most-One Allocation:** Each mission request specifies multiple candidate view periods across single antennas or array configurations, but can only be scheduled at most once.
2. **Composite Array Antenna Locking:** Composite resource requests (e.g. `DSS-24_DSS-25` or `DSS-14_DSS-24_DSS-25`) require exclusive reservation of **every constituent physical antenna** for the entire setup, contact, and teardown window.
3. **Antenna Maintenance Exclusion:** Pre-scheduled maintenance intervals from `maintenance.csv` are enforced as immovable blackout windows.
4. **Flexible Contact Duration:** The optimizer can adjust contact duration between the mission's minimum requirement (`duration_min`) and the requested maximum (`duration`).
5. **Setup and Teardown Margins:** Request-specific setup (30-60 min) and teardown (15-40 min) buffers are reserved without violating candidate view period boundaries `[vp_start, vp_end]`.
6. **Time-Window Enclosure:** All setup, tracking, and teardown activities must fit strictly within the request's allowable window `[time_window_start, time_window_end]`.

---

## 3. Outcome Metrics: Contact Time vs Data Volume

> **Important Operational Distinction:**  
> SatNet requests do not define transmission bandwidth (Mbps) or total data volume (GB). Therefore, all SatNet benchmarks strictly measure:
> - **Scheduled Contact Hours:** Total operational tracking time allocated across all scheduled requests.
> - **Request Satisfaction Rate (%):** Percentage of submitted mission requests successfully scheduled ($N_{\text{scheduled}} / N_{\text{total}}$).
> - **Hours Completion Rate (%):** Percentage of requested tracking hours fulfilled ($H_{\text{scheduled}} / H_{\text{requested}}$).
> - **Constraint Violations:** Independent verification of 0 overlaps, 0 maintenance breaches, and 0 window overruns.

---

## 4. Understanding Solver Status: `FEASIBLE` vs `OPTIMAL`

- **`FEASIBLE`**: The OR-Tools CP-SAT solver found a mathematically valid, conflict-free schedule that strictly improves upon the baseline heuristic, but search was terminated when the allocated time limit (e.g. 30 seconds) was reached. The global mathematical optimum is not guaranteed.
- **`OPTIMAL`**: The solver explored or pruned the entire search space and proved that no better objective value can exist.
- *Benchmark Reporting Rule:* We report `FEASIBLE` whenever the time budget stops search before full optimality proof.

---

## 5. Running the Reproducible Benchmark

Execute the standardized benchmark runner from the repository root:

```bash
# Default execution on Week 10 (30-second time budget)
python scripts/run_satnet_benchmark.py

# Custom dataset directory, week, or solver time limit
python scripts/run_satnet_benchmark.py --dataset-dir datasets/satnet-master/data --week W10_2018 --time-limit 30.0 --output-json docs/satnet_benchmark_w10.json --output-report docs/satnet_benchmark_w10.md
```

### Verified Empirical Output (`W10_2018`)

| Metric | FCFS Baseline | OR-Tools CP-SAT | Optimization Delta |
| :--- | :---: | :---: | :---: |
| **Solver Status** | `FEASIBLE` | `FEASIBLE` | — |
| **Independent Validation** | `0 Violations` | `0 Violations` | Fully Valid |
| **Scheduled Requests** | 214 / 257 | 226 / 257 | **+12 requests (+4.67%)** |
| **Request Satisfaction Rate** | 83.27% | 87.94% | **+4.67%** |
| **Scheduled Contact Hours** | 837.30h | 913.88h | **+76.58 hours** |
| **Hours Completion Rate** | 70.27% | 76.70% | **+6.43%** |
| **Rejected Requests** | 43 requests | 31 requests | **-12 rejections** |
| **Runtime** | 0.003s | 30.27s | 30s solver limit |

---

## 6. CI and Automated QA Coverage

OrbitOpt uses a two-tier verification strategy:
1. **Continuous Integration (GitHub Actions):**
   - Runs fast unit tests, API tests, and domain model tests using isolated synthetic scenarios and small SatNet fixtures.
   - Runs TypeScript compilation (`tsc -b`), linting (`oxlint`), and Vite production bundling.
   - Does *not* block routine PR checks with the full 30-second SatNet CP-SAT optimization.
2. **On-Demand Benchmark Suite:**
   - Evaluates full multi-week scenarios (`W10_2018` through `W50_2018`) via `scripts/run_satnet_benchmark.py`.
