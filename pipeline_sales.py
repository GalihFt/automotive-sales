"""Impor CSV penjualan: validasi -> staging sementara -> upsert PostgreSQL."""

import argparse
import csv
import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv



ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

COLUMNS = (
    "order_id", "order_date", "dealer_id", "vehicle_id",
    "qty", "unit_price", "status", "updated_at",
)


def validate(row, dealer_ids, vehicle_ids):
    """Kembalikan data bertipe sesuai DB; ValueError berarti baris ditolak."""
    values = {key: (row.get(key) or "").strip() for key in COLUMNS}
    if any(not value for value in values.values()):
        raise ValueError("Semua kolom wajib diisi, termasuk updated_at")
    for key, limit in (("order_id", 50), ("dealer_id", 10), ("vehicle_id", 10)):
        if len(values[key]) > limit:
            raise ValueError(f"{key} melebihi {limit} karakter")
    if values["dealer_id"] not in dealer_ids:
        raise ValueError("dealer_id tidak terdaftar")
    if values["vehicle_id"] not in vehicle_ids:
        raise ValueError("vehicle_id tidak terdaftar")
    if values["status"] not in {"pending", "delivered", "cancelled"}:
        raise ValueError("status harus pending, delivered, atau cancelled")
    try:
        values["order_date"] = date.fromisoformat(values["order_date"])
        values["updated_at"] = datetime.fromisoformat(values["updated_at"])
        values["qty"] = int(values["qty"])
        values["unit_price"] = Decimal(values["unit_price"])
    except (ValueError, InvalidOperation):
        raise ValueError("Format tanggal, qty, atau unit_price tidak valid") from None
    if values["updated_at"].tzinfo is not None:
        raise ValueError("updated_at harus waktu lokal tanpa zona waktu")
    if values["updated_at"].date() < values["order_date"]:
        raise ValueError("updated_at tidak boleh sebelum order_date")
    if not 1 <= values["qty"] <= 32767:
        raise ValueError("qty harus antara 1 dan 32767")
    price = values["unit_price"]
    if not price.is_finite() or not 0 < price < Decimal("1e18"):
        raise ValueError("unit_price harus positif dan muat NUMERIC(20,2)")
    if price != price.quantize(Decimal("0.01")):
        raise ValueError("unit_price maksimal dua angka desimal")
    return values


def read_batch(path, dealer_ids, vehicle_ids):
    accepted, rejected, seen = [], [], set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError(f"Header CSV harus: {','.join(COLUMNS)}")
        for line, row in enumerate(reader, start=2):
            try:
                if None in row:
                    raise ValueError("Jumlah kolom berlebih")
                record = validate(row, dealer_ids, vehicle_ids)
                if record["order_id"] in seen:
                    raise ValueError("order_id duplikat dalam file; baris valid pertama dipakai")
                seen.add(record["order_id"])
                accepted.append(record)
            except ValueError as error:
                rejected.append({**{key: row.get(key) for key in COLUMNS},
                                 "line": line, "reason": str(error)})
    return accepted, rejected


def local_ids(filename, column):
    with (ROOT / "data" / filename).open(newline="", encoding="utf-8-sig") as handle:
        return {row[column] for row in csv.DictReader(handle)}


def run(args):
    applied = 0
    if args.validate_only:
        accepted, rejected = read_batch(
            args.file, local_ids("dealers.csv", "dealer_id"),
            local_ids("vehicles.csv", "vehicle_id"),
        )
    else:
        if not os.environ.get("DATABASE_URL"):
            raise ValueError("Set DATABASE_URL terlebih dahulu; lihat README.md")
        from sqlalchemy import create_engine, text

        engine = create_engine(os.environ["DATABASE_URL"])
        try:
            with engine.connect() as conn:
                with conn.begin() as transaction:
                    # Referensi diperiksa terhadap DB tujuan, bukan master CSV lokal.
                    dealer_ids = set(conn.execute(text("SELECT dealer_id FROM automotive.dealers")).scalars())
                    vehicle_ids = set(conn.execute(text("SELECT vehicle_id FROM automotive.vehicles")).scalars())
                    accepted, rejected = read_batch(args.file, dealer_ids, vehicle_ids)
                    conn.execute(text("""
                        CREATE TEMP TABLE sales_staging ON COMMIT DROP AS
                        SELECT * FROM automotive.sales WITH NO DATA
                    """))
                    if accepted:
                        columns = ", ".join(COLUMNS)
                        params = ", ".join(f":{key}" for key in COLUMNS)
                        conn.execute(text(f"INSERT INTO sales_staging ({columns}) VALUES ({params})"), accepted)
                        sql = (ROOT / "sql" / "merge_sales.sql").read_text(encoding="utf-8")
                        applied = conn.execute(text(sql)).rowcount
                    if args.dry_run:
                        transaction.rollback()
        finally:
            engine.dispose()

    args.report_dir.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    reject_path = args.report_dir / f"sales_{batch_id}_rejected.csv"
    with reject_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*COLUMNS, "line", "reason"])
        writer.writeheader()
        writer.writerows(rejected)
    summary = {
        "file": str(args.file.resolve()),
        "mode": "validate-only" if args.validate_only else "dry-run" if args.dry_run else "load",
        "accepted": len(accepted), "rejected": len(rejected),
        "applied": applied if not args.validate_only else None,
        "skipped_same_or_older": len(accepted) - applied if not args.validate_only else None,
        "rejected_file": str(reject_path.resolve()),
    }
    (args.report_dir / f"sales_{batch_id}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="CSV penjualan tambahan")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--validate-only", action="store_true", help="Validasi dengan master CSV lokal, tanpa DB")
    modes.add_argument("--dry-run", action="store_true", help="Jalankan ke DB lalu rollback seluruh perubahan")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        # Hindari mencetak URL koneksi yang mungkin memuat password.
        if isinstance(error, (ValueError, FileNotFoundError, ModuleNotFoundError)):
            parser.exit(1, f"Gagal: {error}\n")
        parser.exit(1, f"Gagal ({type(error).__name__}); periksa koneksi, tabel, dan dependensi.\n")


if __name__ == "__main__":
    main()
