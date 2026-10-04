from datetime import date


def register_instrument(conn, instrument_key, instrument_name=None):
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key must be a non-empty string")
    if instrument_name is not None and (
        not isinstance(instrument_name, str) or not instrument_name.strip()
    ):
        raise ValueError("instrument_name must be a non-empty string when provided")
    cur = conn.execute(
        "INSERT INTO instruments (instrument_key, instrument_name) VALUES (?, ?)",
        (
            instrument_key.strip(),
            instrument_name.strip() if instrument_name is not None else None,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_instrument_name(conn, instrument_key):
    row = conn.execute(
        "SELECT instrument_name FROM instruments WHERE instrument_key = ?",
        (instrument_key,),
    ).fetchone()
    return None if row is None else row["instrument_name"]


def set_instrument_name(conn, instrument_key, instrument_name):
    if not isinstance(instrument_name, str) or not instrument_name.strip():
        raise ValueError("instrument_name must be a non-empty string")
    cur = conn.execute(
        "UPDATE instruments SET instrument_name = ? WHERE instrument_key = ?",
        (instrument_name.strip(), instrument_key),
    )
    if cur.rowcount != 1:
        raise ValueError(f"Unknown instrument_key: {instrument_key}")
    conn.commit()


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
