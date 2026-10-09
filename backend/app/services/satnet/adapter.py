"""SatNet Dataset Adapter: Converts SatNet problem dictionaries to normalized domain scenarios."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from .inspector import SatNetInspector
from .models import (
    SatNetCandidateWindow,
    SatNetMaintenanceInterval,
    SatNetRequest,
    SatNetScenario,
)


def get_week_epoch_start(week_number: int, year: int = 2018) -> datetime:
    """Calculate the UTC start datetime (Monday 00:00:00) for a given ISO week of a year.
    
    For 2018:
    Week 1 starts Monday 2018-01-01.
    Week 10 starts Monday 2018-03-05 00:00:00 UTC.
    Week 20 starts Monday 2018-05-14 00:00:00 UTC.
    Week 30 starts Monday 2018-07-23 00:00:00 UTC.
    Week 40 starts Monday 2018-10-01 00:00:00 UTC.
    Week 50 starts Monday 2018-12-10 00:00:00 UTC.
    """
    # ISO week date calculation
    # Jan 4 is always in week 1 of any ISO year
    jan4 = datetime(year, 1, 4, 0, 0, 0, tzinfo=timezone.utc)
    # Find Monday of week 1
    week1_monday = jan4 - timedelta(days=jan4.weekday())
    # Add (week_number - 1) weeks
    target_monday = week1_monday + timedelta(weeks=week_number - 1)
    return target_monday


class SatNetAdapter:
    """Converts SatNet problem sets and maintenance blocks into a normalized scheduling scenario."""

    def __init__(self, data_dir: Optional[str] = None):
        self.inspector = SatNetInspector(data_dir=data_dir)

    def load_scenario(self, week_key: str = "W10_2018") -> SatNetScenario:
        """Load and normalize a specific week from SatNet into a SatNetScenario."""
        problems = self.inspector.load_problems()
        if week_key not in problems:
            available = sorted(list(problems.keys()))
            raise KeyError(f"Week '{week_key}' not in problems.json. Available: {available}")

        raw_requests = problems[week_key]
        raw_maint = self.inspector.load_maintenance()

        # Parse week and year
        parts = week_key.replace("W", "").split("_")
        week_num = int(parts[0])
        year_num = int(parts[1]) if len(parts) > 1 else 2018

        week_start_epoch = get_week_epoch_start(week_num, year_num)
        week_start_ts = int(week_start_epoch.timestamp())

        scenario = SatNetScenario(
            name=f"SatNet DSN Schedule Scenario ({week_key})",
            week_key=week_key,
            week_number=week_num,
            year=year_num,
            week_start_epoch=week_start_epoch,
        )

        all_resources: Set[str] = set()
        single_antennas: Set[str] = set()
        array_antennas: Dict[str, List[str]] = {}

        # 1. Parse and normalize requests
        for idx, r in enumerate(raw_requests):
            track_id = r.get("track_id", f"req_{idx}")
            subject = int(r.get("subject", 0))
            user = str(r.get("user", ""))
            dur_hrs = float(r.get("duration", 0.0))
            dur_min_hrs = float(r.get("duration_min", dur_hrs))
            setup_min = int(r.get("setup_time", 60))
            teardown_min = int(r.get("teardown_time", 15))
            tw_start_sec = int(r.get("time_window_start", 0))
            tw_end_sec = int(r.get("time_window_end", 604800))

            tw_start = week_start_epoch + timedelta(seconds=tw_start_sec)
            tw_end = week_start_epoch + timedelta(seconds=tw_end_sec)

            res_vp_dict = r.get("resource_vp_dict", {})
            candidate_resources = list(res_vp_dict.keys())
            candidate_windows: List[SatNetCandidateWindow] = []

            for res_name, vp_list in res_vp_dict.items():
                all_resources.add(res_name)
                if "_" in res_name:
                    constituents = [c.strip() for c in res_name.split("_") if c.strip()]
                    array_antennas[res_name] = constituents
                    for c in constituents:
                        single_antennas.add(c)
                else:
                    constituents = [res_name]
                    single_antennas.add(res_name)

                for vp_idx, vp in enumerate(vp_list):
                    t_on = int(vp.get("TRX ON", 0))
                    t_off = int(vp.get("TRX OFF", 0))
                    vp_dur_hrs = float(vp.get("DURATION_HRS", (t_off - t_on) / 3600.0))

                    vp_start = week_start_epoch + timedelta(seconds=t_on)
                    vp_end = week_start_epoch + timedelta(seconds=t_off)

                    candidate_windows.append(
                        SatNetCandidateWindow(
                            window_id=f"win_{track_id}_{res_name}_{vp_idx}",
                            track_id=track_id,
                            resource_id=res_name,
                            constituent_antennas=constituents,
                            start_time=vp_start,
                            end_time=vp_end,
                            vp_start_sec=t_on,
                            vp_end_sec=t_off,
                            duration_hours=vp_dur_hrs,
                        )
                    )

            scenario.requests.append(
                SatNetRequest(
                    track_id=track_id,
                    subject=subject,
                    user=user,
                    week=week_num,
                    year=year_num,
                    duration_hours=dur_hrs,
                    duration_min_hours=dur_min_hrs,
                    setup_time_minutes=setup_min,
                    teardown_time_minutes=teardown_min,
                    time_window_start_sec=tw_start_sec,
                    time_window_end_sec=tw_end_sec,
                    time_window_start=tw_start,
                    time_window_end=tw_end,
                    candidate_resources=candidate_resources,
                    candidate_windows=candidate_windows,
                )
            )

        # 2. Parse and normalize maintenance intervals for this week
        for m_idx, m in enumerate(raw_maint):
            if m["week"] == week_num and m["year"] == year_num:
                ant = m["antenna"]
                single_antennas.add(ant)
                m_start_abs = m["starttime"]
                m_end_abs = m["endtime"]

                m_start = datetime.fromtimestamp(m_start_abs, tz=timezone.utc)
                m_end = datetime.fromtimestamp(m_end_abs, tz=timezone.utc)

                # Relative seconds within the week
                m_start_rel = m_start_abs - week_start_ts
                m_end_rel = m_end_abs - week_start_ts

                scenario.maintenance_intervals.append(
                    SatNetMaintenanceInterval(
                        interval_id=f"maint_{week_key}_{ant}_{m_idx}",
                        antenna=ant,
                        start_time=m_start,
                        end_time=m_end,
                        start_sec=m_start_rel,
                        end_sec=m_end_rel,
                        week=week_num,
                        year=year_num,
                    )
                )

        scenario.single_antennas = single_antennas
        scenario.array_antennas = array_antennas
        scenario.all_resources = all_resources

        return scenario
