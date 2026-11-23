from pathlib import Path

from sqlalchemy import text

from app.database import engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def apply_migrations() -> list[str]:
    applied_now = []
    with engine.begin() as connection:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(278341902)")
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        applied = set(
            connection.execute(text("SELECT version FROM schema_migrations")).scalars()
        )

        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration_path.name in applied:
                continue
            statements = migration_path.read_text(encoding="utf-8").split(";")
            for statement in statements:
                if statement.strip():
                    connection.exec_driver_sql(statement)
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": migration_path.name},
            )
            applied_now.append(migration_path.name)
    return applied_now


if __name__ == "__main__":
    migrations = apply_migrations()
    if migrations:
        print("Applied migrations:", ", ".join(migrations))
    else:
        print("Database schema is up to date.")
