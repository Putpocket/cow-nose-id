from __future__ import annotations

from app.utils.model import CowCreate, CowUpdate


def list_cows(cur):
    cur.execute("SELECT cow_id, owner_id, name, created_at FROM cows ORDER BY cow_id DESC")
    rows = cur.fetchall()
    return [
        {
            "cow_id": row[0],
            "owner_id": row[1],
            "name": row[2],
            "created_at": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]


def get_cow(cur, cow_id: int):
    cur.execute("SELECT cow_id, owner_id, name, created_at FROM cows WHERE cow_id=%s", (cow_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "cow_id": row[0],
        "owner_id": row[1],
        "name": row[2],
        "created_at": row[3].isoformat() if row[3] else None,
    }


def create_cow(cur, payload: dict):
    req = CowCreate.from_payload(payload)
    cur.execute(
        "INSERT INTO cows (owner_id, name) VALUES (%s, %s) RETURNING cow_id",
        (req.owner_id, req.name),
    )
    return cur.fetchone()[0]


def update_cow(cur, cow_id: int, payload: dict):
    req = CowUpdate.from_payload(payload)
    cur.execute(
        "UPDATE cows SET owner_id=%s, name=%s WHERE cow_id=%s",
        (req.owner_id, req.name, cow_id),
    )
    return cur.rowcount > 0


def delete_cow(cur, cow_id: int):
    cur.execute("DELETE FROM cows WHERE cow_id=%s", (cow_id,))
    return cur.rowcount > 0
