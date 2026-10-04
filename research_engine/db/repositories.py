from datetime import date


def register_instrument(conn, instrument_key):
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key must be a non-empty string")
    cur = conn.execute(
        "INSERT INTO instruments (instrument_key) VALUES (?)",
        (instrument_key.strip(),),
    )
    conn.commit()
    return cur.lastrowid


def get_instrument_id(conn, instrument_key):
    row = conn.execute(
        "SELECT instrument_id FROM instruments WHERE instrument_key = ?",
        (instrument_key,),
    ).fetchone()
    return None if row is None else row["instrument_id"]


def get_observations(conn, instrument_id, start_date=None, end_date=None):
    query = """SELECT observation_date, value
               FROM observations
               WHERE instrument_id = ?"""
    params = [instrument_id]

    if start_date is not None:
        query += " AND observation_date >= ?"
        params.append(_date_text(start_date))
    if end_date is not None:
        query += " AND observation_date <= ?"
        params.append(_date_text(end_date))

    query += " ORDER BY observation_date"
    return conn.execute(query, params).fetchall()


def _date_text(value):
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
