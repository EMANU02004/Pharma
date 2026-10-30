"""PharmaFinder Flask application factory."""
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Flask, send_from_directory
from flask.json.provider import DefaultJSONProvider

from . import db
from .config import Config
from .errors import register_error_handlers

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")


class JSONProvider(DefaultJSONProvider):
    """ISO dates, plain numbers for DECIMAL, HH:MM for MySQL TIME values."""
    @staticmethod
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat(sep=" ", timespec="minutes")
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, timedelta):
            secs = int(o.total_seconds())
            return f"{secs // 3600:02d}:{secs % 3600 // 60:02d}"
        return DefaultJSONProvider.default(o)


def create_app(overrides=None):
    app = Flask(__name__, static_folder=None)
    app.json_provider_class = JSONProvider
    app.json = JSONProvider(app)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    db.init_app(app)
    register_error_handlers(app)

    from .routes import admin, auth, doctor, patient, pharmacy, search
    for module in (auth, doctor, patient, pharmacy, search, admin):
        app.register_blueprint(module.bp)

    @app.get("/api/health")
    def health():
        db.query_one("SELECT 1 AS ok")
        return {"status": "ok"}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # Local development: Flask serves the frontend. On Vercel the CDN serves public/.
    @app.get("/")
    def index():
        return send_from_directory(PUBLIC_DIR, "index.html")

    @app.get("/<path:path>")
    def static_files(path):
        return send_from_directory(PUBLIC_DIR, path)

    return app
