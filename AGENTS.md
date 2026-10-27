# Project database and runtime

- Use PostgreSQL in Docker for development and deployment preparation. The SQLite fallback is not the intended project database.
- Run Django management commands and database checks through the Docker web service (currently `paulibot_web`), so they use the configured PostgreSQL database.
- Do not infer account or application data from the local `db.sqlite3` file, switch to SQLite, or create replacement accounts to work around connection problems.
- The current Docker setup exposes Django on host port 8080 and PostgreSQL on host port 5432. The Vite development proxy should reach the Docker backend at `http://127.0.0.1:8080`.
- Preserve PostgreSQL data volumes. Do not reset or remove database volumes without explicit user authorization.
- Keep database credentials in environment configuration; do not commit secrets.
