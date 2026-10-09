"""Inspector and validator utility for the SatNet NASA Deep Space Network dataset."""

import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set


class SatNetInspector:
    """Inspects, parses, and validates SatNet JSON problem sets and maintenance CSVs."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            # Default to standard project datasets path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            data_dir = os.path.join(base_dir, "datasets", "satnet-master", "data")
        
        self.data_dir = data_dir
        self.problems_file = os.path.join(data_dir, "problems.json")
        self.maintenance_file = os.path.join(data_dir, "maintenance.csv")

    def validate_files_exist(self) -> None:
        """Verify required dataset files exist and are readable."""
        if not os.path.isdir(self.data_dir):
            raise FileNotFoundError(
                f"SatNet data directory not found: '{self.data_dir}'. "
                "Ensure datasets/satnet-master/data is present."
            )
        if not os.path.isfile(self.problems_file):
            raise FileNotFoundError(
                f"SatNet problems file not found: '{self.problems_file}'."
            )
        if not os.path.isfile(self.maintenance_file):
            raise FileNotFoundError(
                f"SatNet maintenance file not found: '{self.maintenance_file}'."
            )

    def load_problems(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load and parse problems.json."""
        self.validate_files_exist()
        try:
            with open(self.problems_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("problems.json root must be a JSON object keyed by week.")
                return data
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON in problems.json: {exc}") from exc

    def load_maintenance(self) -> List[Dict[str, Any]]:
        """Load and parse maintenance.csv."""
        self.validate_files_exist()
        rows = []
        try:
            with open(self.maintenance_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                expected_cols = {"week", "year", "starttime", "endtime", "antenna"}
                if not reader.fieldnames or not expected_cols.issubset(set(reader.fieldnames)):
                    raise ValueError(
                        f"maintenance.csv missing required columns. Found: {reader.fieldnames}, Expected: {expected_cols}"
                    )
                for idx, row in enumerate(reader):
                    try:
                        wk = int(float(row["week"]))
                        yr = int(float(row["year"]))
                        st = int(float(row["starttime"]))
                        et = int(float(row["endtime"]))
                        ant = str(row["antenna"]).strip()
                        if et < st:
                            raise ValueError(f"End time before start time at row {idx+1}")
                        rows.append({
                            "week": wk,
                            "year": yr,
                            "starttime": st,
                            "endtime": et,
                            "antenna": ant,
                        })
                    except (ValueError, TypeError) as conv_err:
                        raise ValueError(f"Malformed row {idx+1} in maintenance.csv: {conv_err}") from conv_err
            return rows
        except Exception as exc:
            if isinstance(exc, (ValueError, FileNotFoundError)):
                raise
            raise ValueError(f"Error reading maintenance.csv: {exc}") from exc

    def inspect_week(self, week_key: str = "W10_2018") -> Dict[str, Any]:
        """Produce full audit and profile statistics for a selected week."""
        problems = self.load_problems()
        if week_key not in problems:
            available = sorted(list(problems.keys()))
            raise KeyError(
                f"Selected week '{week_key}' not found in problems.json. Available weeks: {available}"
            )

        requests = problems[week_key]
        maint_rows = self.load_maintenance()

        # Parse week number and year from key (e.g. W10_2018 -> week=10, year=2018)
        parts = week_key.replace("W", "").split("_")
        week_num = int(parts[0])
        year_num = int(parts[1]) if len(parts) > 1 else 2018

        # Filter maintenance for this week
        week_maint = [
            m for m in maint_rows
            if m["week"] == week_num and m["year"] == year_num
        ]

        unique_subjects: Set[int] = set()
        unique_track_ids: Set[str] = set()
        unique_resources: Set[str] = set()
        single_antennas: Set[str] = set()
        array_antennas: Dict[str, List[str]] = {}
        total_vps = 0
        malformed_records: List[Dict[str, Any]] = []

        durations_hrs: List[float] = []
        min_durations_hrs: List[float] = []
        setup_times_min: Set[int] = set()
        teardown_times_min: Set[int] = set()

        for idx, req in enumerate(requests):
            track_id = req.get("track_id")
            subject = req.get("subject")
            dur = req.get("duration")
            dur_min = req.get("duration_min")
            setup = req.get("setup_time")
            teardown = req.get("teardown_time")
            res_vps = req.get("resource_vp_dict", {})

            # Validation checks
            is_malformed = False
            reasons = []
            if not track_id:
                is_malformed = True
                reasons.append("Missing track_id")
            if subject is None:
                is_malformed = True
                reasons.append("Missing subject")
            if dur is None or dur <= 0:
                is_malformed = True
                reasons.append("Invalid duration")
            if dur_min is None or dur_min <= 0 or dur_min > (dur or 0):
                is_malformed = True
                reasons.append(f"Invalid duration_min ({dur_min} vs {dur})")
            if not res_vps or not isinstance(res_vps, dict):
                is_malformed = True
                reasons.append("Empty or non-dict resource_vp_dict")

            if is_malformed:
                malformed_records.append({
                    "index": idx,
                    "track_id": track_id,
                    "reasons": reasons,
                })
                continue

            unique_subjects.add(subject)
            unique_track_ids.add(track_id)
            durations_hrs.append(float(dur))
            min_durations_hrs.append(float(dur_min))
            if setup is not None:
                setup_times_min.add(int(setup))
            if teardown is not None:
                teardown_times_min.add(int(teardown))

            for res_name, vp_list in res_vps.items():
                unique_resources.add(res_name)
                if "_" in res_name:
                    constituents = [c.strip() for c in res_name.split("_") if c.strip()]
                    array_antennas[res_name] = constituents
                    for c in constituents:
                        single_antennas.add(c)
                else:
                    single_antennas.add(res_name)

                if isinstance(vp_list, list):
                    total_vps += len(vp_list)

        maint_antennas = {m["antenna"] for m in week_maint}
        total_maint_hours = sum(
            (m["endtime"] - m["starttime"]) / 3600.0 for m in week_maint
        )

        return {
            "week_key": week_key,
            "week_number": week_num,
            "year": year_num,
            "total_requests": len(requests),
            "valid_requests": len(requests) - len(malformed_records),
            "malformed_count": len(malformed_records),
            "malformed_records": malformed_records,
            "unique_subjects_count": len(unique_subjects),
            "unique_track_ids_count": len(unique_track_ids),
            "unique_resources_count": len(unique_resources),
            "single_antennas_count": len(single_antennas),
            "single_antennas": sorted(list(single_antennas)),
            "array_antennas_count": len(array_antennas),
            "array_antennas": array_antennas,
            "total_view_periods": total_vps,
            "avg_vps_per_request": round(total_vps / len(requests), 2) if requests else 0.0,
            "duration_hrs_min": min(durations_hrs) if durations_hrs else 0.0,
            "duration_hrs_max": max(durations_hrs) if durations_hrs else 0.0,
            "duration_hrs_avg": round(sum(durations_hrs) / len(durations_hrs), 2) if durations_hrs else 0.0,
            "min_duration_hrs_avg": round(sum(min_durations_hrs) / len(min_durations_hrs), 2) if min_durations_hrs else 0.0,
            "setup_times_minutes": sorted(list(setup_times_min)),
            "teardown_times_minutes": sorted(list(teardown_times_min)),
            "maintenance_intervals_count": len(week_maint),
            "maintenance_antennas_count": len(maint_antennas),
            "maintenance_antennas": sorted(list(maint_antennas)),
            "maintenance_total_hours": round(total_maint_hours, 1),
        }


if __name__ == "__main__":
    inspector = SatNetInspector()
    target_week = sys.argv[1] if len(sys.argv) > 1 else "W10_2018"
    try:
        report = inspector.inspect_week(target_week)
        print("=" * 60)
        print(f"SATNET INSPECTOR REPORT: {report['week_key']}")
        print("=" * 60)
        print(f"Requests: {report['total_requests']} (Valid: {report['valid_requests']}, Malformed: {report['malformed_count']})")
        print(f"Missions / Subjects: {report['unique_subjects_count']}")
        print(f"Candidate View Periods: {report['total_view_periods']} (Avg {report['avg_vps_per_request']} per request)")
        print(f"Resources: {report['unique_resources_count']} ({report['single_antennas_count']} physical antennas, {report['array_antennas_count']} arrays)")
        print(f"Physical Antennas: {report['single_antennas']}")
        print(f"Requested Duration: {report['duration_hrs_min']}h - {report['duration_hrs_max']}h (Avg: {report['duration_hrs_avg']}h, Min Acceptable Avg: {report['min_duration_hrs_avg']}h)")
        print(f"Setup Times (min): {report['setup_times_minutes']}")
        print(f"Teardown Times (min): {report['teardown_times_minutes']}")
        print(f"Maintenance Blocks: {report['maintenance_intervals_count']} intervals across {report['maintenance_antennas_count']} antennas ({report['maintenance_total_hours']} hours)")
        print("=" * 60)
    except Exception as e:
        print(f"Inspector error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
