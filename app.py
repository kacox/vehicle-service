import logging
import logging.config
from dataclasses import asdict
from typing import Annotated

import requests
from flask import Flask, Response, json, request
from werkzeug.exceptions import HTTPException, UnprocessableEntity

from db import Vehicle, VehicleTable, VIN_PATTERN


NHSTA_BASE_URL = "https://vpic.nhtsa.dot.gov/api/"

logging.config.fileConfig("logging.conf")
LOGGER = logging.getLogger("vehicleService")

app = Flask(__name__)


def extract_from_response(response):
    if not response:
        raise ValueError("Response is empty or missing")

    vin, make, model, model_year, body_class = (
        None,
        None,
        None,
        None,
        None,
    )

    vin = response["SearchCriteria"].lstrip("VIN:")
    for result in response["Results"]:
        if result["Variable"] == "Make":
            make = result["Value"]
        elif result["Variable"] == "Model":
            model = result["Value"]
        elif result["Variable"] == "Model Year":
            model_year = result["Value"]
        elif result["Variable"] == "Body Class":
            body_class = result["Value"]
        else:
            continue

    return Vehicle(
        vin=vin,
        make=make,
        model=model,
        model_year=model_year,
        body_class=body_class,
    )


def validate_vin(vin):
    if not VIN_PATTERN.fullmatch(vin):
        LOGGER.warning(f"{vin} is not a valid VIN")
        raise UnprocessableEntity("Not a valid VIN")


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps(
        {
            "code": e.code,
            "name": e.name,
            "description": e.description,
        }
    )
    response.content_type = "application/json"
    return response


@app.get("/lookup/<vin>")
def lookup_vehicle(vin):
    """
    Looks up a vechicle by VIN.
    """
    validate_vin(vin)

    cached = False
    vehicle = VehicleTable.get_by_vin(vin)
    if vehicle:
        cached = True
    else:
        response = requests.get(
            NHSTA_BASE_URL + f"/vehicles/DecodeVin/{vin}",
            params={"format": "json"},
        ).json()
        vehicle_data = extract_from_response(response)
        LOGGER.info(f"Vehicle {vin} fetched from NHSTA API")
        vehicle = VehicleTable.create(vehicle_data)
    response = asdict(vehicle)
    response["from_cache"] = cached
    return response


@app.delete("/remove/<vin>")
def remove_vehicle(vin):
    """
    Removes a vehicle by VIN.
    """
    validate_vin(vin)

    vehicle = VehicleTable.delete_by_vin(vin)
    if vehicle:
        return {
            "vin": vin,
            "success": False,
        }
    else:
        return {
            "vin": vin,
            "success": True,
        }


@app.post("/export")
def export_cache():
    """
    Exports the SQLite database cache and return a binary file (parquet
    format) containing the data in the cache.

    Note: ideally in production you would return a link (e.g. an S3
    link) that clients could use to download the file instead of
    allowing direct server downloads.
    """
    parquet = VehicleTable.get_db_as_parquet()

    # parquet is None, so would otherwise throw a `TypeError: The view function
    # for 'export_cache' did not return a valid response.` , even though the
    # file gets returned OK to client; set to 200 response to avoid confusion
    # for the client.
    return Response(response=parquet, status=200, mimetype="application/octet-stream")
