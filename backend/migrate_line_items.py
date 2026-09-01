import sqlite3
from pathlib import Path


# Backend directory:
# backend/scripts/migrate_line_items.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "legal_invoice.db"


def get_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def column_exists(cursor, table_name, column_name):
    return column_name in get_columns(cursor, table_name)


def main():
    print("=" * 60)
    print("LINE ITEMS DATABASE MIGRATION")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"\nDatabase not found: {DB_PATH}")
        print("Please make sure legal_invoice.db exists in the backend folder.")
        return

    print(f"\nDatabase: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check whether line_items table exists
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='line_items'
            """
        )

        if cursor.fetchone() is None:
            print("\nline_items table does not exist.")
            print("Please initialize the database first.")
            return

        columns = get_columns(cursor, "line_items")

        print("\nExisting columns:")
        print(", ".join(sorted(columns)))

        # ---------------------------------------------------------
        # Add missing columns required by the latest line item schema
        # ---------------------------------------------------------

        migrations = {
            "line_type": (
                "ALTER TABLE line_items "
                "ADD COLUMN line_type TEXT NOT NULL DEFAULT 'fee'"
            ),
            "description": (
                "ALTER TABLE line_items "
                "ADD COLUMN description TEXT"
            ),
            "timekeeper": (
                "ALTER TABLE line_items "
                "ADD COLUMN timekeeper TEXT"
            ),
            "role": (
                "ALTER TABLE line_items "
                "ADD COLUMN role TEXT"
            ),
            "hours": (
                "ALTER TABLE line_items "
                "ADD COLUMN hours REAL"
            ),
            "rate": (
                "ALTER TABLE line_items "
                "ADD COLUMN rate REAL"
            ),
        }

        print("\nChecking for missing columns...\n")

        for column_name, sql in migrations.items():
            if column_name not in columns:
                cursor.execute(sql)
                print(f"[ADDED] {column_name}")
            else:
                print(f"[EXISTS] {column_name}")

        # Refresh column list after migration
        columns = get_columns(cursor, "line_items")

        # ---------------------------------------------------------
        # Normalize existing data
        # ---------------------------------------------------------

        print("\nNormalizing existing line items...\n")

        # Any existing row with a description but no timekeeper
        # is most likely an expense.
        if (
            "line_type" in columns
            and "description" in columns
            and "timekeeper" in columns
        ):
            cursor.execute(
                """
                UPDATE line_items
                SET line_type = 'expense'
                WHERE
                    description IS NOT NULL
                    AND TRIM(description) != ''
                    AND (
                        timekeeper IS NULL
                        OR TRIM(timekeeper) = ''
                    )
                """
            )

            expense_count = cursor.rowcount
            print(
                f"[UPDATED] {expense_count} existing row(s) classified as expenses."
            )

        # Make sure all remaining NULL line_type values become fee
        if "line_type" in columns:
            cursor.execute(
                """
                UPDATE line_items
                SET line_type = 'fee'
                WHERE line_type IS NULL
                   OR TRIM(line_type) = ''
                """
            )

            fee_count = cursor.rowcount
            print(
                f"[UPDATED] {fee_count} row(s) assigned default type 'fee'."
            )

        conn.commit()

        print("\n" + "=" * 60)
        print("DATABASE MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print("\nFinal line_items columns:")
        final_columns = get_columns(cursor, "line_items")

        for column in sorted(final_columns):
            print(f" - {column}")

    except Exception as error:
        conn.rollback()

        print("\nMigration failed!")
        print(f"Error: {error}")

        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()