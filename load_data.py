import pandas as pd
from sqlalchemy import create_engine

# Koneksi PostgreSQL
engine = create_engine(
    "postgresql+psycopg://postgres:admin@localhost:5432/postgres"
)

# import data
dealers = pd.read_csv("data/dealers.csv")
vehicles = pd.read_csv("data/vehicles.csv")
inventory = pd.read_csv("data/inventory.csv")

# change data type to date
inventory["snapshot_date"] = pd.to_datetime(
    inventory["snapshot_date"]
).dt.date

# sales data
sales = pd.read_csv("data/sales.csv")

sales["order_date"] = pd.to_datetime(
    sales["order_date"]
).dt.date

sales["updated_at"] = pd.to_datetime(
    sales["updated_at"]
)


# Load
with engine.begin() as conn:

    dealers.to_sql(
        "dealers",
        con=conn,
        schema="automotive",
        if_exists="append",
        index=False
    )

    vehicles.to_sql(
        "vehicles",
        con=conn,
        schema="automotive",
        if_exists="append",
        index=False
    )

    inventory.to_sql(
        "inventory",
        con=conn,
        schema="automotive",
        if_exists="append",
        index=False
    )

    sales.to_sql(
        "sales",
        con=conn,
        schema="automotive",
        if_exists="append",
        index=False
    )

print("All data loaded successfully!")