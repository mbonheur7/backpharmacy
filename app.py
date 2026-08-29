from datetime import timedelta

from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import init_db_session


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = Config.SECRET_KEY
    # Signed, httpOnly session cookie (Flask's built-in session mechanism) —
    # per the approved architecture, chosen over JWT-in-browser-storage.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "None"
    app.config["SESSION_COOKIE_SECURE"] = Config.SESSION_COOKIE_SECURE
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=Config.SESSION_LIFETIME_HOURS)

    # supports_credentials=True is required for the session cookie to be
    # sent/received cross-origin once Stage 3's frontend calls this API.
    CORS(app, supports_credentials=True, origins=Config.CORS_ORIGINS)

    init_db_session(app)

    from routes.auth import auth_bp
    from routes.medicines import medicines_bp
    from routes.sales import sales_bp
    from routes.alerts import alerts_bp
    from routes.reports import reports_bp
    from routes.users import users_bp
    from routes.activity_logs import activity_logs_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(medicines_bp, url_prefix="/api/medicines")
    app.register_blueprint(sales_bp, url_prefix="/api/sales")
    app.register_blueprint(alerts_bp, url_prefix="/api/alerts")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(activity_logs_bp, url_prefix="/api/activity-logs")

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Not found."}, 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return {"error": "Method not allowed."}, 405

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "VI-PHARMACY API"}

    return app
