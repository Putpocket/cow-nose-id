from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.cows.service import create_cow, delete_cow, get_cow, list_cows, update_cow
from app.utils.model import ValidationError


cows_bp = Blueprint("cows", __name__, url_prefix="/admin/cows")


@cows_bp.route("", methods=["GET"])
def list_cows_route():
    db_conn_factory = current_app.config["DB_CONNECTION_FACTORY"]
    with db_conn_factory() as conn, conn.cursor() as cur:
        return jsonify(list_cows(cur))


@cows_bp.route("", methods=["POST"])
def create_cow_route():
    db_conn_factory = current_app.config["DB_CONNECTION_FACTORY"]
    payload = request.get_json(silent=True) or {}
    try:
        with db_conn_factory() as conn, conn.cursor() as cur:
            cow_id = create_cow(cur, payload)
            return jsonify({"cow_id": cow_id}), 201
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@cows_bp.route("/<int:cow_id>", methods=["GET"])
def get_cow_route(cow_id: int):
    db_conn_factory = current_app.config["DB_CONNECTION_FACTORY"]
    with db_conn_factory() as conn, conn.cursor() as cur:
        cow = get_cow(cur, cow_id)
        if not cow:
            return jsonify({"error": "not found"}), 404
        return jsonify(cow)


@cows_bp.route("/<int:cow_id>", methods=["PUT"])
def update_cow_route(cow_id: int):
    db_conn_factory = current_app.config["DB_CONNECTION_FACTORY"]
    payload = request.get_json(silent=True) or {}
    try:
        with db_conn_factory() as conn, conn.cursor() as cur:
            if not update_cow(cur, cow_id, payload):
                return jsonify({"error": "not found"}), 404
            return jsonify({"message": "updated"})
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400


@cows_bp.route("/<int:cow_id>", methods=["DELETE"])
def delete_cow_route(cow_id: int):
    db_conn_factory = current_app.config["DB_CONNECTION_FACTORY"]
    with db_conn_factory() as conn, conn.cursor() as cur:
        if not delete_cow(cur, cow_id):
            return jsonify({"error": "not found"}), 404
        return jsonify({"message": "deleted"})
