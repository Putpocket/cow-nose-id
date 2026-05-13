from contextlib import contextmanager

from app.db import get_connection


@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            yield conn, cur
            conn.commit()
        finally:
            cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all_dict(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_one_dict(cur):
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))
