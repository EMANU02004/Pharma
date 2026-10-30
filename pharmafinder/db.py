"""MySQL access: one PyMySQL connection per request, explicit transactions."""
from contextlib import contextmanager

import pymysql
import pymysql.cursors
from flask import current_app, g


def _connect(app=None):
    cfg = (app or current_app).config
    kwargs = dict(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        charset="utf8mb4",
        connect_timeout=10,
    )
    if cfg.get("DB_SSL_CA"):
        kwargs["ssl"] = {"ca": cfg["DB_SSL_CA"]}
    return pymysql.connect(**kwargs)


def get_db():
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.rollback()  # discard anything a request forgot to commit
        finally:
            conn.close()


def query(sql, params=None):
    with get_db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    with get_db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql, params=None):
    """Run a write and return lastrowid. Caller commits (or uses transaction())."""
    with get_db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid


def commit():
    get_db().commit()


@contextmanager
def transaction():
    """Commit on success, roll back on any exception."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_app(app):
    app.teardown_appcontext(close_db)
