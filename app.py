"""Almaha's Study Planner: educational Flask/PostgreSQL lab application."""
import os
import re
import socket
from datetime import date, timedelta
from functools import wraps

import click
import psycopg
from psycopg.rows import dict_row
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for, send_from_directory
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder=".", static_folder=None)
app.config.update(
    SECRET_KEY=os.environ["SECRET_KEY"],
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    MAX_CONTENT_LENGTH=16384,
)
if len(app.config["SECRET_KEY"]) < 32:
    raise RuntimeError("SECRET_KEY must contain at least 32 characters")
CSRFProtect(app)
SERVER_NAME = os.getenv("INSTANCE_NAME", socket.gethostname())


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, connect_timeout=5)


@app.cli.command("init-db")
def init_db():
    """Create missing tables; does not remove existing records."""
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username VARCHAR(40) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(160) NOT NULL, course VARCHAR(60) NOT NULL DEFAULT '',
            due_date DATE, completed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
        db.execute("CREATE INDEX IF NOT EXISTS tasks_user_id_idx ON tasks(user_id)")
    click.echo("Database ready: users and tasks tables exist.")


@app.before_request
def load_user():
    g.user = None
    if session.get("user_id") and request.endpoint not in ("style", "health", "whoami"):
        with connect() as db:
            g.user = db.execute("SELECT id, username FROM users WHERE id=%s", (session["user_id"],)).fetchone()
        if g.user is None:
            session.clear()


@app.after_request
def headers(response):
    response.headers["X-Served-By"] = SERVER_NAME
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def page(mode, **values):
    return render_template("page.html", mode=mode, server_name=SERVER_NAME, **values)


@app.get("/style.css")
def style():
    return send_from_directory(app.root_path, "style.css")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[a-z0-9_]{3,40}", username):
            flash("Use 3–40 letters, numbers or underscores for your username.")
        elif not 10 <= len(password) <= 128:
            flash("Choose a password between 10 and 128 characters.")
        else:
            try:
                with connect() as db:
                    db.execute("INSERT INTO users(username, password_hash) VALUES (%s,%s)",
                               (username, generate_password_hash(password)))
            except psycopg.errors.UniqueViolation:
                flash("That username is already registered. Try another or sign in.")
            else:
                flash("Account created. Sign in to start your planner.")
                return redirect(url_for("login"))
    return page("register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        with connect() as db:
            user = db.execute("SELECT * FROM users WHERE username=%s", (username,)).fetchone()
        if user and len(password) <= 128 and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(url_for("dashboard"))
        flash("Username or password is incorrect.")
    return page("login")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def dashboard():
    with connect() as db:
        tasks = db.execute("SELECT * FROM tasks WHERE user_id=%s ORDER BY completed, due_date NULLS LAST, id DESC",
                           (g.user["id"],)).fetchall()
    return page("dashboard", tasks=tasks, total=len(tasks), done=sum(t["completed"] for t in tasks))


@app.post("/tasks")
@login_required
def add_task():
    title = request.form.get("title", "").strip()
    course = request.form.get("course", "").strip()
    due = request.form.get("due_date", "").strip()
    try:
        due = date.fromisoformat(due) if due else None
    except ValueError:
        abort(400, "Invalid date")
    if not 1 <= len(title) <= 160 or len(course) > 60:
        abort(400, "Task title or course is too long or missing")
    with connect() as db:
        db.execute("INSERT INTO tasks(user_id,title,course,due_date) VALUES (%s,%s,%s,%s)",
                   (g.user["id"], title, course, due))
    flash("Task saved to your database.")
    return redirect(url_for("dashboard"))


@app.post("/tasks/<int:task_id>/<action>")
@login_required
def change_task(task_id, action):
    with connect() as db:
        if action == "toggle":
            result = db.execute("UPDATE tasks SET completed=NOT completed WHERE id=%s AND user_id=%s",
                                (task_id, g.user["id"]))
        elif action == "delete":
            result = db.execute("DELETE FROM tasks WHERE id=%s AND user_id=%s", (task_id, g.user["id"]))
        else:
            abort(404)
        if not result.rowcount:
            abort(404)
    return redirect(url_for("dashboard"))


@app.get("/health")
def health():
    try:
        with connect() as db:
            db.execute("SELECT 1").fetchone()
    except psycopg.Error:
        return jsonify(status="unavailable", instance=SERVER_NAME), 503
    return jsonify(status="ok", database="connected", instance=SERVER_NAME)


@app.get("/whoami")
def whoami():
    return jsonify(instance=SERVER_NAME)
