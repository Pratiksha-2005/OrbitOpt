"""Initial database schema for datasets, stations, passes, runs, and allocations.

Revision ID: 20261009_0001
Revises: 
Create Date: 2026-10-09 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20261009_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Datasets Table
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
    )

    # Ground Stations Table
    op.create_table(
        "ground_stations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("station_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("latitude_deg", sa.Float(), nullable=False),
        sa.Column("longitude_deg", sa.Float(), nullable=False),
        sa.Column("elevation_mask_deg", sa.Float(), nullable=False),
        sa.Column("max_concurrent_passes", sa.Integer(), nullable=False),
        sa.Column("supported_bands", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_ground_stations_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ground_stations")),
    )
    op.create_index(op.f("ix_ground_stations_dataset_id"), "ground_stations", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_ground_stations_station_id"), "ground_stations", ["station_id"], unique=False)

    # Satellite Passes Table
    op.create_table(
        "satellite_passes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("pass_id", sa.String(length=64), nullable=False),
        sa.Column("satellite_id", sa.String(length=64), nullable=False),
        sa.Column("ground_station_id", sa.String(length=64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_elevation_deg", sa.Float(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("data_volume_gb", sa.Float(), nullable=False),
        sa.Column("required_bandwidth_mbps", sa.Float(), nullable=True),
        sa.Column("channel_band", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_satellite_passes_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_satellite_passes")),
    )
    op.create_index(op.f("ix_satellite_passes_dataset_id"), "satellite_passes", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_satellite_passes_pass_id"), "satellite_passes", ["pass_id"], unique=False)
    op.create_index(op.f("ix_satellite_passes_satellite_id"), "satellite_passes", ["satellite_id"], unique=False)
    op.create_index(op.f("ix_satellite_passes_ground_station_id"), "satellite_passes", ["ground_station_id"], unique=False)
    op.create_index(op.f("ix_satellite_passes_start_time"), "satellite_passes", ["start_time"], unique=False)
    op.create_index(op.f("ix_satellite_passes_end_time"), "satellite_passes", ["end_time"], unique=False)
    op.create_index(op.f("ix_satellite_passes_priority"), "satellite_passes", ["priority"], unique=False)

    # Schedule Runs Table
    op.create_table(
        "schedule_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("validation_violations", sa.JSON(), nullable=False),
        sa.Column("solver_status_detail", sa.String(length=64), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("unassigned_passes", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_schedule_runs_dataset_id_datasets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_runs")),
    )
    op.create_index(op.f("ix_schedule_runs_dataset_id"), "schedule_runs", ["dataset_id"], unique=False)
    op.create_index(op.f("ix_schedule_runs_algorithm"), "schedule_runs", ["algorithm"], unique=False)

    # Scheduled Allocations Table
    op.create_table(
        "scheduled_allocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schedule_run_id", sa.String(length=64), nullable=False),
        sa.Column("pass_id", sa.String(length=64), nullable=False),
        sa.Column("satellite_id", sa.String(length=64), nullable=False),
        sa.Column("ground_station_id", sa.String(length=64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("data_volume_gb", sa.Float(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_run_id"],
            ["schedule_runs.id"],
            name=op.f("fk_scheduled_allocations_schedule_run_id_schedule_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_allocations")),
    )
    op.create_index(op.f("ix_scheduled_allocations_schedule_run_id"), "scheduled_allocations", ["schedule_run_id"], unique=False)
    op.create_index(op.f("ix_scheduled_allocations_pass_id"), "scheduled_allocations", ["pass_id"], unique=False)
    op.create_index(op.f("ix_scheduled_allocations_satellite_id"), "scheduled_allocations", ["satellite_id"], unique=False)
    op.create_index(op.f("ix_scheduled_allocations_ground_station_id"), "scheduled_allocations", ["ground_station_id"], unique=False)


def downgrade() -> None:
    op.drop_table("scheduled_allocations")
    op.drop_table("schedule_runs")
    op.drop_table("satellite_passes")
    op.drop_table("ground_stations")
    op.drop_table("datasets")
