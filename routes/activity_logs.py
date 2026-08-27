from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from extensions import db_session
from models import ActivityLog
from services.permission_service import require_role
from serializers import serialize_activity_log
from utils import error_response

activity_logs_bp = Blueprint("activity_logs", __name__)


@activity_logs_bp.get("")
@require_role("Admin")
def list_activity_logs():
    query = db_session.query(ActivityLog)

    action = request.args.get("action")
    if action:
        query = query.filter(ActivityLog.action == action)

    user_id = request.args.get("user_id")
    if user_id:
        try:
            query = query.filter(ActivityLog.user_id == int(user_id))
        except ValueError:
            return error_response("user_id must be an integer.")

    start = request.args.get("start")
    end = request.args.get("end")
    try:
        if start:
            query = query.filter(ActivityLog.occurred_at >= datetime.strptime(start, "%Y-%m-%d"))
        if end:
            query = query.filter(ActivityLog.occurred_at < datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        return error_response("start/end must be in YYYY-MM-DD format.")

    logs = query.order_by(ActivityLog.occurred_at.desc()).limit(500).all()
    return jsonify({"activity_logs": [serialize_activity_log(l) for l in logs]}), 200
