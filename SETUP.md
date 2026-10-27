# Almaha's Study Planner

CCEN 448 Lab 6 — Almaha Rashed Alshamsi, 100062540.
Educational application created with AI assistance. This repository is application code only; it does not by itself deploy cloud resources or complete the lab's bonus tasks.

## Features

Register and sign in, add dated course tasks, mark tasks complete, and delete tasks. PostgreSQL stores users and tasks. Each request is handled by Flask on a web instance; passwords are hashed using Werkzeug. Signed session cookies, CSRF tokens, parameterized SQL and user-scoped task queries protect the application. The footer and X-Served-By response header identify the instance. /health checks database connectivity and /whoami reports the serving instance without caching.

## Files

- app.py: server, database queries, authentication, health check and schema command.
- page.html: login, registration and planner template.
- style.css: local stylesheet; no external assets or CDN required.
- requirements.txt: Python dependencies.
- SETUP.md: installation and architecture notes.

## Server requirements

Ubuntu 24.04 LTS, Python 3 with venv, PostgreSQL, and network access to the database. Install python3-venv and postgresql using apt for the initial single-instance exercise. The supplied OpenTofu template can install these packages and clone this repository into /opt/website. Database roles, environment configuration, schema initialization and the Gunicorn service are separate setup steps.

In /opt/website:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Provide these environment variables privately, preferably in a root-owned service environment file outside the repository with mode 600:

- DATABASE_URL: a PostgreSQL connection string for a dedicated planner role and database. The role must own the planner schema/tables to initialize them. Never publish the real connection string or password.
- SECRET_KEY: generate a random secret of at least 32 characters (for example, python3 -c 'import secrets; print(secrets.token_hex(32))'). Both web instances must use the SAME secret for shared login sessions.
- INSTANCE_NAME: a distinct non-secret label such as almaha-web-1.
- COOKIE_SECURE: false for the required direct-HTTP exercise; true when switching exclusively to HTTPS. Omit any fixed cookie domain so the temporary tunnel hostname can change. Sign in again when changing hostnames.

With the variables loaded:

```bash
.venv/bin/flask --app app init-db
.venv/bin/gunicorn --workers 2 --bind 0.0.0.0:8000 app:app
```

Run initialization once per database before starting web workers. init-db preserves existing tables and records; it is not a schema migration system. Use systemd to keep Gunicorn running after SSH disconnects. Port 8000 is the application port for the supplied OpenTofu template.

## Cloudflare tunnel

The lab's SSH forward maps Mac localhost:8080 to instance localhost:8000. cloudflared runs on the Mac and forwards to localhost:8080. All app forms and links use relative URLs, so a purchased domain or a fixed public URL is unnecessary. After public_http=false, keep both tunnel processes alive. Use COOKIE_SECURE=true for HTTPS-only access and restart the application service when changing its environment. Do not use Flask debug mode on the server.

## Extra-credit architecture plan

For two web instances, point both DATABASE_URL values at a separate shared PostgreSQL service; do not use two independent local databases. Use the same SECRET_KEY and different INSTANCE_NAME values. Restrict database connections to the web instances over the private network. A load balancer should health-check /health and distribute requests; the footer and /whoami show which backend responded. Run the SSH forward to the load balancer's HTTP listener for Cloudflare access. Existing records and login sessions can then survive one web backend stopping. The shared database and a single load balancer remain potential single points of failure; this demonstrates web-tier failover, not complete infrastructure high availability. OpenTofu and Ansible automation and the actual failover test are completed separately during the lab.

For direct HTTPS extra credit, configure a reverse proxy with a valid Let's Encrypt IP-address certificate, automatic renewal and port 443. This is separate from the Cloudflare tunnel and requires its own evidence. Do not claim these bonus exercises are complete until deployed and tested.

## Lab scope

Use fictitious study tasks and a password unique to this lab. This teaching application has no password-reset workflow, email verification, MFA or login rate limiting. Add these before production use. Never commit AWS keys, SSH private keys, database credentials, service environment files or OpenTofu state. Delete cloud resources after all required evidence and bonus demonstrations have been collected.
