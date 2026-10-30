"""Consistent JSON errors for the API."""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, message, status=400, fields=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.fields = fields or {}


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(err):
        body = {"error": err.message}
        if err.fields:
            body["fields"] = err.fields
        return jsonify(body), err.status

    @app.errorhandler(HTTPException)
    def _http_error(err):
        # JSON for API routes; static pages keep their normal behaviour
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify({"error": err.description}), err.code
        return err

    @app.errorhandler(Exception)
    def _unhandled(err):
        app.logger.exception("Unhandled error")
        return jsonify({"error": "Internal server error"}), 500
