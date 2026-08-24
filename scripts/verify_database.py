from sqlalchemy import inspect
from app.db.session import engine, verify_database_connection
from app.models import Base

def main() -> None:
    verify_database_connection()
    Base.metadata.create_all(engine)

    expected_tables = set(Base.metadata.tables)
    existing_tables = set(inspect(engine).get_table_names())
    missing_tables = expected_tables - existing_tables
    if missing_tables:
        raise RuntimeError(f"Missing tables: {', '.join(sorted(missing_tables))}")

    print("Database schema verified.")


if __name__ == "__main__":
    main()
