#!/usr/bin/env python3
"""Initialize the database with all tables."""

from app import app, db

with app.app_context():
    # Create all tables
    db.create_all()
    print("✓ Database tables created successfully!")

    # Show tables
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"\n✓ Created {len(tables)} tables:")
    for table in sorted(tables):
        print(f"  - {table}")
