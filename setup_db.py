import sqlite3


if __name__ == "__main__":
    conn = sqlite3.connect("vehicle.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "CREATE TABLE vehicle(body_class TEXT, make TEXT, model TEXT, model_year TEXT, vin TEXT PRIMARY KEY)"
        )
        res = cur.execute("SELECT name FROM sqlite_master")
        success = "vehicle" in res.fetchone()
        print("Successfully created database table...")
    except sqlite3.OperationalError:
        res = cur.execute("SELECT name FROM sqlite_master")
        success = "vehicle" in res.fetchone()
        if success:
            print("vehicle table already exists...")
        else:
            raise
    finally:
        conn.close()
