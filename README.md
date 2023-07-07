# Vehicle Service

A simple flask webservice that can lookup vehicles by their VIN
(vehicle identification number).

## Setup

Create a virtual environment and install the packages specified in the
`requirements.txt` file.

Create the SQLite3 database "cache" by running the `setup_db.py` script.

Run the webserver using:
```
flask run --reload
```

## API

`GET /lookup/{vin}`

Retrieves vehicle information using the provided VIN.

`DELETE /remove/{vin}`

Removes the specified vehicle's information from the cache.

`POST /export`

Returns a parquet file containing all vehicles currently in the cache.

## Development

To run tests, from the top level directory execute:
```
python -m pytest
```

To run a linter/formatter:
```
black [--check] .
```

## Additional info

This webservice uses the vPIC API provided by the NHSTA to lookup
vehicle information.
