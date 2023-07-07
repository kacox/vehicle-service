import logging
import re
import sqlite3
from dataclasses import asdict, dataclass

from pandas import read_sql_query


LOGGER = logging.getLogger("vinService")
PARQUET_FILE_LOCATION = "vehicle.parquet"
_SQLITE_CONN = None
VIN_REGEX = "^[A-Z0-9]{17}$"
VIN_PATTERN = re.compile(VIN_REGEX)


def get_connection(testing=False):
    # in production would use SQLAlchemy to manage connection pool
    global _SQLITE_CONN
    if not _SQLITE_CONN:
        if testing:
            _SQLITE_CONN = sqlite3.connect(":memory:")
        else:
            _SQLITE_CONN = sqlite3.connect("vehicle.db")
        _SQLITE_CONN.row_factory = sqlite3.Row
    return _SQLITE_CONN


@dataclass
class Vehicle:
    body_class: str
    make: str
    model: str
    model_year: str
    vin: str

    def __post_init__(self) -> None:
        assert 1886 <= int(self.model_year) <= 9999, "Model year is invalid"
        assert VIN_PATTERN.fullmatch(self.vin) is not None, "Invalid VIN"


def _row_to_vehicle(row):
    if not row:
        return None
    return Vehicle(
        body_class=row["body_class"],
        make=row["make"],
        model=row["model"],
        model_year=row["model_year"],
        vin=row["vin"],
    )


class VehicleTable:
    def create(vehicle):
        conn = get_connection()
        with conn:
            cur = conn.execute(
                """
                INSERT INTO vehicle VALUES
                (:body_class, :make, :model, :model_year, :vin)
                """,
                asdict(vehicle),
            )
        LOGGER.info(f"Inserted vehicle {vehicle.vin} into cache")
        return vehicle

    def delete_by_vin(vin):
        conn = get_connection()
        with conn:
            cur = conn.execute(
                """
                DELETE from vehicle WHERE vin = :vin
                """,
                {"vin": vin},
            )
            LOGGER.info(f"Deleted {cur.rowcount} rows")
        return VehicleTable.get_by_vin(vin)

    def get_by_vin(vin):
        conn = get_connection()
        with conn:
            cur = conn.execute(
                """
                SELECT * FROM vehicle WHERE vin = :vin
                """,
                {"vin": vin},
            )
            vehicle_data = cur.fetchone()
            if vehicle_data:
                LOGGER.info(f"Vehicle {vin} found in cache")
            else:
                LOGGER.info(f"Vehicle {vin} not in cache")
        return _row_to_vehicle(vehicle_data)

    def get_db_as_parquet():
        conn = get_connection()
        with conn:
            db_dataframe = read_sql_query("SELECT * FROM vehicle", conn)
        return db_dataframe.to_parquet(
            PARQUET_FILE_LOCATION, engine="fastparquet", index=False
        )
