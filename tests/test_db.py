from sqlite3 import IntegrityError, OperationalError
from unittest.mock import patch
import os

from pandas import read_parquet
import pytest

from db import (
    PARQUET_FILE_LOCATION,
    Vehicle,
    VehicleTable,
    _row_to_vehicle,
    get_connection,
)


TEST_VEHICLE_1 = Vehicle(
    body_class="Truck-Tractor",
    make="PETERBILT",
    model="388",
    model_year="2014",
    vin="1XPWD40X1ED215307",
)
TEST_VEHICLE_2 = Vehicle(
    body_class="Truck-Tractor",
    make="VOLVO TRUCK",
    model="VNL",
    model_year="2014",
    vin="4V4NC9EJXEN171694",
)
TEST_VEHICLE_3 = Vehicle(
    body_class="Truck-Tractor",
    make="PETERBILT",
    model="379",
    model_year="2000",
    vin="1XP5DB9X7YN526158",
)


@pytest.fixture
def vehicle_table():
    conn = get_connection(testing=True)
    cur = conn.cursor()
    try:
        cur.execute(
            "CREATE TABLE vehicle(body_class TEXT, make TEXT, model TEXT, model_year TEXT, vin TEXT PRIMARY KEY)"
        )
        res = cur.execute("SELECT name FROM sqlite_master")
        success = "vehicle" in res.fetchone()
        print("Successfully created database table...")
    except OperationalError:
        res = cur.execute("SELECT name FROM sqlite_master")
        success = "vehicle" in res.fetchone()
        if success:
            print("vehicle table already exists...")
        else:
            raise


@patch("db.get_connection")
def test_create(test_connection, vehicle_table):
    test_connection.return_value = get_connection(testing=True)

    vehicle = VehicleTable.create(TEST_VEHICLE_1)
    assert isinstance(vehicle, Vehicle)
    assert vehicle.body_class == TEST_VEHICLE_1.body_class
    assert vehicle.make == TEST_VEHICLE_1.make
    assert vehicle.model == TEST_VEHICLE_1.model
    assert vehicle.model_year == TEST_VEHICLE_1.model_year
    assert vehicle.vin == TEST_VEHICLE_1.vin


@patch("db.get_connection")
def test_create_duplicate(test_connection, vehicle_table):
    """
    Creating duplicate entries by VIN should violate the unique
    constraint on the `vin` column.
    """
    test_connection.return_value = get_connection(testing=True)

    # create the initial record
    vehicle = VehicleTable.create(TEST_VEHICLE_2)

    # attempt a duplicate record
    with pytest.raises(IntegrityError) as excinfo:
        VehicleTable.create(TEST_VEHICLE_2)
    assert "UNIQUE constraint failed" in str(excinfo.value)

    # ensure the duplicate did not persist
    read_conn = get_connection(testing=True)
    with read_conn:
        cur = read_conn.execute(
            """
            SELECT * FROM vehicle WHERE vin = :vin
            """,
            {"vin": TEST_VEHICLE_2.vin},
        )
        vehicle_data = cur.fetchall()
        assert len(vehicle_data) == 1


@patch("db.get_connection")
def test_delete_by_vin(test_connection, vehicle_table):
    test_connection.return_value = get_connection(testing=True)

    # create a vehicle
    VehicleTable.create(TEST_VEHICLE_3)

    # delete it
    vehicle = VehicleTable.delete_by_vin(TEST_VEHICLE_3.vin)
    assert not vehicle


@patch("db.VehicleTable.get_by_vin")
@patch("db.get_connection")
def test_delete_by_vin_vehicle_still_exists(test_connection, get_by_vin, vehicle_table):
    """
    Should return a vehicle if deletion fails silently.
    """
    test_connection.return_value = get_connection(testing=True)
    # patch so get_by_vin still returns something
    get_by_vin.return_value = TEST_VEHICLE_3

    # create a vehicle
    VehicleTable.create(TEST_VEHICLE_3)

    # attempt to delete the vehicle
    vehicle = VehicleTable.delete_by_vin(TEST_VEHICLE_3.vin)
    assert vehicle
    assert vehicle.vin == TEST_VEHICLE_3.vin


@patch("db.get_connection")
def test_get_by_vin(test_connection, vehicle_table):
    test_connection.return_value = get_connection(testing=True)
    # create vehicle so there is something to fetch
    VehicleTable.create(TEST_VEHICLE_3)

    vehicle = VehicleTable.get_by_vin(TEST_VEHICLE_3.vin)
    assert isinstance(vehicle, Vehicle)
    assert vehicle.body_class == TEST_VEHICLE_3.body_class
    assert vehicle.make == TEST_VEHICLE_3.make
    assert vehicle.model == TEST_VEHICLE_3.model
    assert vehicle.model_year == TEST_VEHICLE_3.model_year
    assert vehicle.vin == TEST_VEHICLE_3.vin

    # delete the vehicle so it doesn't hang around b/t test cases
    VehicleTable.delete_by_vin(TEST_VEHICLE_3.vin)


@patch("db.get_connection")
def test_get_by_vin_not_found(test_connection, vehicle_table):
    test_connection.return_value = get_connection(testing=True)

    vehicle = VehicleTable.get_by_vin(TEST_VEHICLE_3.vin)
    assert not vehicle


@patch("db.get_connection")
def test_get_db_as_parquet(test_connection, vehicle_table):
    test_connection.return_value = get_connection(testing=True)
    # ensure db is empty before starting
    prep_conn = get_connection(testing=True)
    with prep_conn:
        prep_conn.execute(
            """
            DELETE from vehicle
            """
        )
        cur = prep_conn.execute(
            """
            SELECT * from vehicle
            """
        )
        vehicle_data = cur.fetchall()
        assert len(vehicle_data) == 0

    # create one record
    VehicleTable.create(TEST_VEHICLE_3)

    # dump db contents into file
    VehicleTable.get_db_as_parquet()

    # check that the file is good
    parq = read_parquet(PARQUET_FILE_LOCATION)
    assert len(parq) == 1

    # cleanup parquet file and db record
    os.remove(PARQUET_FILE_LOCATION)
    VehicleTable.delete_by_vin(TEST_VEHICLE_3.vin)


def test_row_to_vehicle():
    row = {
        "body_class": "Truck-Tractor",
        "make": "PETERBILT",
        "model": "388",
        "model_year": "2014",
        "vin": "1XPWD40X1ED215307",
    }

    result = _row_to_vehicle(row)
    assert isinstance(result, Vehicle)
    assert result.body_class == row["body_class"]
    assert result.make == row["make"]
    assert result.model == row["model"]
    assert result.model_year == row["model_year"]
    assert result.vin == row["vin"]


def test_row_to_vehicle_invalid_vin():
    row = {
        "body_class": "Truck-Tractor",
        "make": "PETERBILT",
        "model": "388",
        "model_year": "2014",
        "vin": "PWD40X1ED215307",
    }

    with pytest.raises(AssertionError) as excinfo:
        _row_to_vehicle(row)
    assert "Invalid VIN" in str(excinfo.value)


def test_row_to_vehicle_invalid_model_year():
    row = {
        "body_class": "Truck-Tractor",
        "make": "PETERBILT",
        "model": "388",
        "model_year": "1800",
        "vin": "1XPWD40X1ED215307",
    }

    with pytest.raises(AssertionError) as excinfo:
        _row_to_vehicle(row)
    assert "Model year is invalid" in str(excinfo.value)


def test_row_to_vehicle_none_arg():
    result = _row_to_vehicle({})
    assert not result
