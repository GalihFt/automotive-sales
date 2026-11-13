# Pipeline impor penjualan otomotif

Repo latihan untuk memindahkan data CSV ke PostgreSQL menggunakan Python. Ada dua proses: **mengisi data awal** melalui `load_data.py` dan **mengimpor penjualan tambahan** melalui `pipeline_sales.py`.

Satu **batch** berarti satu file CSV yang diproses pada satu kali eksekusi. Versi ini memakai alur validasi Python → staging → upsert → laporan.

## Daftar isi

1. [Struktur repo](#struktur-repo)
2. [Data dan hubungan tabel](#data-dan-hubungan-tabel)
3. [Alur lengkap](#alur-lengkap)
4. [Validasi dan duplikat](#validasi-dan-duplikat)
5. [Staging dan upsert](#staging-dan-upsert)
6. [Perbedaan mode](#perbedaan-mode)
7. [Setup dan menjalankan](#setup-dan-menjalankan)
8. [Membaca laporan](#membaca-laporan)
9. [Memeriksa hasil](#memeriksa-hasil)
10. [Membuat CSV sendiri](#membuat-csv-sendiri)
11. [Tes dan penanganan masalah](#tes-dan-penanganan-masalah)
12. [Batas implementasi](#batas-implementasi)

## Struktur repo

```text
.
├── data/
│   ├── dealers.csv                 # Master dealer awal
│   ├── vehicles.csv                # Master kendaraan awal
│   ├── inventory.csv               # Snapshot stok awal
│   ├── sales.csv                   # Penjualan awal
│   └── incoming/
│       └── sales_2026_11.csv        # Contoh batch tambahan
├── sql/
│   ├── create_table.sql            # Setup schema dan tabel utama
│   ├── merge_sales.sql             # Upsert staging ke sales
│   └── analysis.sql                # Tempat latihan analisis; masih kosong
├── docs/
│   ├── pipeline-sales.html         # Diagram yang bisa dibuka di browser
│   └── pipeline-sales.md           # Diagram Mermaid dan penjelasan teks
├── tests/
│   └── test_pipeline_sales.py      # Tes parsing dan validasi
├── reports/                        # Dibuat otomatis; diabaikan Git
├── load_data.py                    # Loader data awal
├── pipeline_sales.py               # Pipeline penjualan tambahan
├── requirements.txt                # Dependensi Python
└── .gitignore                      # Abaikan environment, cache, dan laporan
```

Lihat [diagram HTML](docs/pipeline-sales.html) untuk mengikuti perjalanan data secara visual. HTML bisa dibuka tanpa internet. Versi sumber diagram ada di [dokumen Markdown](docs/pipeline-sales.md).

| Fungsi / file           | Tugas                                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| `main()`              | Membaca argumen terminal, memanggil run(), menangani pesan kegagalan  |
| `run(args)`           | Mengatur mode, koneksi, transaksi, staging, merge, dan laporan        |
| `local_ids()`         | Mengambil ID dari CSV master untuk validate-only                      |
| `read_batch()`        | Membaca header dan baris, memanggil validasi, memeriksa duplikat file |
| `validate()`          | Membersihkan, memeriksa, dan mengubah tipe data satu baris            |
| `sql/merge_sales.sql` | Menentukan insert, update, atau lewati berdasarkan ID dan timestamp   |

## Data dan hubungan tabel

| File / tabel | Baris CSV awal | Isi                                             |
| ------------ | -------------: | ----------------------------------------------- |
| dealers      |             20 | Identitas dealer, kota, dan region              |
| vehicles     |             15 | Merek, model, kategori, harga daftar            |
| inventory    |          5.000 | Stok per tanggal, dealer, dan kendaraan         |
| sales        |         10.000 | Pesanan, jumlah, harga, status, waktu pembaruan |

Penjualan awal mencakup 1 Januari 2025–31 Oktober 2026. Data latihan ini sintetis. Jumlah baris CSV bukan jaminan bahwa database tujuan sudah terisi.

```text
dealers.dealer_id   → sales.dealer_id
vehicles.vehicle_id → sales.vehicle_id

dealers.dealer_id   → inventory.dealer_id
vehicles.vehicle_id → inventory.vehicle_id
```

`sales.order_id` adalah primary key. Primary key inventory merupakan gabungan `snapshot_date`, `dealer_id`, dan `vehicle_id`. Dealer dan kendaraan harus tersedia sebelum data yang mereferensikannya dimasukkan.

Batch contoh `data/incoming/sales_2026_11.csv` berisi 13 baris:

- 10 pesanan baru: `ORD-DEMO-202611-0001` sampai `ORD-DEMO-202611-0010`.
- 1 pembaruan: `ORD-2025-003351`, pending menjadi delivered dengan timestamp lebih baru.
- 1 kesalahan sengaja: `ORD-DEMO-INVALID-QTY`, jumlah -1.
- 1 kesalahan sengaja: `ORD-DEMO-INVALID-DEALER`, dealer D999.

## Alur lengkap

### A. Data awal

```text
sql/create_table.sql → schema automotive dan empat tabel utama

CSV dealers   → automotive.dealers
CSV vehicles  → automotive.vehicles
CSV inventory → automotive.inventory
CSV sales     → automotive.sales
       melalui load_data.py
```

Loader awal membaca empat CSV dengan pandas, mengonversi tanggal/timestamp, lalu menambahkan data memakai `to_sql(if_exists="append")` dalam satu transaksi. Master dealer dan kendaraan diisi terlebih dahulu. Loader ini tidak melakukan upsert dan tidak aman untuk dijalankan berulang pada tabel yang sudah terisi.

### B. Penjualan tambahan

```text
CSV tambahan
     ↓
Validasi dan cek duplikat file di Python
     ├── Salah → rejected di memori Python
     ↓
accepted di memori Python
     ↓ INSERT
sales_staging di PostgreSQL
     ↓ sql/merge_sales.sql
sales: INSERT / UPDATE / lewati
     ↓
COMMIT untuk load / ROLLBACK untuk dry-run
     ↓
CSV penolakan + JSON ringkasan + ringkasan terminal
```

Urutan mode database:

1. `main()` membaca path CSV dan flag, lalu memanggil `run()`.
2. `run()` memeriksa `DATABASE_URL`, membuka koneksi, dan memulai transaksi.
3. Python menjalankan SELECT untuk mengambil ID dealer dan kendaraan dari master database tujuan.
4. `read_batch()` membaca header dan setiap baris CSV. `validate()` memeriksa nilai dan mengonversi tipe.
5. ID berulang dalam file diperiksa memakai set `seen`. Hasilnya dipisahkan menjadi list `accepted` dan `rejected`.
6. Python membuat tabel sementara `sales_staging` pada koneksi tersebut.
7. Jika accepted tidak kosong, Python memasukkan seluruh baris valid ke staging.
8. Python membaca file `sql/merge_sales.sql` sebagai teks dan menjalankannya melalui `conn.execute(text(sql))`.
9. PostgreSQL membandingkan staging dengan sales. `.rowcount` menjadi jumlah `applied`.
10. Load melakukan commit jika blok transaksi berhasil; dry-run melakukan rollback.
11. Koneksi dilepas, engine di-dispose, kemudian laporan ditulis dan ringkasan dicetak.

Jika accepted kosong, staging tetap dibuat pada mode database, tetapi pengisian staging dan merge dilewati. Laporan tetap dibuat jika proses mencapai tahap tersebut.

Pipeline tidak mengunduh seluruh isi sales ke Python. Perbandingan dengan pesanan yang tersimpan dilakukan PostgreSQL saat upsert.

## Validasi dan duplikat

CSV dibaca dengan library bawaan `csv`, memakai encoding UTF-8 dengan atau tanpa BOM. Header harus tepat sama, termasuk urutan:

```csv
order_id,order_date,dealer_id,vehicle_id,qty,unit_price,status,updated_at
```

| Kolom       | Aturan                                                                                              |
| ----------- | --------------------------------------------------------------------------------------------------- |
| Semua kolom | Wajib terisi; spasi awal/akhir dibuang                                                              |
| order_id    | Maksimal 50 karakter                                                                                |
| dealer_id   | Maksimal 10 karakter dan terdaftar pada master                                                      |
| vehicle_id  | Maksimal 10 karakter dan terdaftar pada master                                                      |
| order_date  | Bisa dikonversi menjadi date, misalnya 2026-11-01                                                   |
| qty         | Bilangan bulat antara 1 dan 32.767                                                                  |
| unit_price  | Angka terbatas, positif, kurang dari 10^18, nilainya tidak membutuhkan lebih dari dua angka desimal |
| status      | Tepat pending, delivered, atau cancelled                                                            |
| updated_at  | Timestamp tanpa zona waktu; tanggalnya tidak sebelum order_date                                     |

`updated_at` wajib di pipeline meskipun schema awal mengizinkan NULL. Gunakan waktu lokal yang konsisten dengan data tujuan. Harga ditulis tanpa simbol mata uang atau pemisah ribuan. Pemeriksaan berhenti pada alasan kegagalan pertama per baris.

| Kasus ID                 | Penanganan              | Hasil                                                    |
| ------------------------ | ----------------------- | -------------------------------------------------------- |
| Berulang dalam satu CSV  | Python, set seen        | Baris valid pertama dipakai; berikutnya ditolak          |
| Sudah ada di tabel sales | PostgreSQL, ON CONFLICT | Update jika memenuhi syarat timestamp; selain itu lewati |

`seen` direset untuk setiap file dan hanya mencatat ID dari baris valid yang diterima. Jika kemunculan pertama tidak valid, kemunculan valid berikutnya masih bisa diterima. Program tidak memilih timestamp terbaru dari beberapa kemunculan ID dalam satu CSV.

Kesalahan satu baris dicatat di rejected dan pemrosesan dilanjutkan. Header salah menggagalkan seluruh proses file.

## Staging dan upsert

| Nama             | Lokasi                  | Fungsi                                   |
| ---------------- | ----------------------- | ---------------------------------------- |
| accepted         | Memori Python           | List hasil validasi                      |
| rejected         | Memori Python           | List data salah, nomor baris, dan alasan |
| sales_staging    | PostgreSQL, sementara   | Sumber tabel untuk SQL merge             |
| automotive.sales | PostgreSQL, tabel utama | Menyimpan pesanan setelah commit         |

Staging dibuat di `pipeline_sales.py`:

```sql
CREATE TEMP TABLE sales_staging ON COMMIT DROP AS
SELECT * FROM automotive.sales WITH NO DATA;
```

Perintah ini mengambil nama dan tipe kolom hasil SELECT tanpa menyalin baris. Tidak menyalin seluruh constraint atau indeks sales. Tabel berada di schema sesi PostgreSQL, misalnya `pg_temp_3`, dan hanya terlihat pada koneksi pembuatnya.

Seluruh perintah staging dan merge menggunakan `conn` yang sama. SQL editor dengan koneksi lain tidak bisa melihat staging pipeline. Menjalankan `merge_sales.sql` sendirian biasanya gagal karena staging belum dibuat pada sesi tersebut.

Saat commit, ON COMMIT DROP menghapus staging. Saat rollback, pembuatan staging ikut dibatalkan. Staging tidak dipertahankan untuk audit setelah proses selesai.

### Penjelasan query merge_sales.sql

Query lengkap yang dipanggil pipeline:

```sql
INSERT INTO automotive.sales AS target (
    order_id, order_date, dealer_id, vehicle_id, qty, unit_price, status, updated_at
)
SELECT order_id, order_date, dealer_id, vehicle_id, qty, unit_price, status, updated_at
FROM sales_staging
ON CONFLICT (order_id) DO UPDATE SET
    order_date = EXCLUDED.order_date,
    dealer_id = EXCLUDED.dealer_id,
    vehicle_id = EXCLUDED.vehicle_id,
    qty = EXCLUDED.qty,
    unit_price = EXCLUDED.unit_price,
    status = EXCLUDED.status,
    updated_at = EXCLUDED.updated_at
WHERE target.updated_at IS NULL OR EXCLUDED.updated_at > target.updated_at;
```

#### 1. INSERT INTO: tentukan tabel tujuan

```sql
INSERT INTO automotive.sales AS target (
    order_id, order_date, dealer_id, vehicle_id, qty, unit_price, status, updated_at
)
```

`automotive` adalah schema dan `sales` adalah tabel tujuan. Daftar di dalam kurung
menentukan kolom yang akan diisi. `AS target` memberi nama alias pada tabel tujuan
agar nilai baris yang sudah tersimpan bisa dirujuk sebagai `target.updated_at`.
Alias ini tidak membuat tabel baru.

#### 2. SELECT FROM: ambil data masukan dari staging

```sql
SELECT order_id, order_date, dealer_id, vehicle_id, qty, unit_price, status, updated_at
FROM sales_staging
```

Sumber data bukan `VALUES (...)` yang ditulis manual, melainkan hasil SELECT dari
tabel staging. Kolom hasil SELECT dipasangkan ke daftar kolom INSERT berdasarkan
posisi: nilai pertama ke order_id, kedua ke order_date, dan seterusnya.
Query memproses seluruh baris staging, bukan hanya satu baris.

Tabel `sales_staging` sudah dibuat dan diisi oleh Python pada koneksi yang sama.
File SQL ini tidak membuat staging dan tidak membaca CSV secara langsung.

#### 3. ON CONFLICT: tangani ID yang sudah ada

```sql
ON CONFLICT (order_id) DO UPDATE SET
```

`sales.order_id` adalah primary key, sehingga dua baris tidak boleh memiliki ID yang
sama. Jika ID masukan belum ada, PostgreSQL menjalankan INSERT biasa. Jika ID sudah
ada, PostgreSQL masuk ke cabang DO UPDATE, dengan syarat WHERE di bagian akhir.

Konflik yang ditangani di sini adalah benturan keunikan order_id. Ini tidak mengabaikan
semua jenis error: pelanggaran foreign key atau constraint lain tetap bisa menggagalkan
perintah dan menyebabkan transaksi pipeline dibatalkan.

#### 4. EXCLUDED: ambil nilai dari baris masukan

```sql
status = EXCLUDED.status,
updated_at = EXCLUDED.updated_at
```

`EXCLUDED` adalah nama khusus PostgreSQL untuk baris yang hendak diinsert tetapi
berbenturan dengan baris lama. Ini bukan nama file, tabel staging, atau baris yang
ditolak validasi Python.

**Dari mana PostgreSQL mengetahui baris masukan tersebut?** Pada query ini, sumbernya
adalah `SELECT ... FROM sales_staging`. Hasil SELECT menjadi calon baris untuk INSERT
ke `automotive.sales`. Ketika order_id calon baris itu sudah ada di tabel tujuan,
nilai calon baris tersebut tersedia sebagai `EXCLUDED` pada bagian DO UPDATE.

```text
Baris di sales_staging
        ↓ SELECT ... FROM sales_staging
Calon baris untuk INSERT ke automotive.sales
        ↓ order_id sudah ada: terjadi konflik
ON CONFLICT DO UPDATE dapat membaca nilai masukan lewat EXCLUDED
        ↓ jika syarat WHERE terpenuhi
Baris lama diperbarui menggunakan nilai masukan
```

Jadi, pada query kita, `EXCLUDED.status` berisi nilai status dari masukan yang berasal
dari staging. `EXCLUDED` bukan alias seluruh tabel sales_staging; ia merujuk ke calon
baris insert yang sedang mengalami konflik. PostgreSQL menyediakannya otomatis,
sehingga tidak perlu CREATE TABLE atau FROM EXCLUDED.

Sebagai ilustrasi: sales_staging membawa `ORD-001, delivered`, sedangkan sales sudah
memiliki `ORD-001, pending`. Saat konflik ditangani, `target.status` bernilai pending
dan `EXCLUDED.status` bernilai delivered. Assignment `status = EXCLUDED.status`
mengganti status lama menjadi delivered jika syarat timestamp pada WHERE terpenuhi.

Contoh jika ID yang sama punya status lama pending dan status masukan delivered:

| Ekspresi                | Nilai yang dirujuk                        |
| ----------------------- | ----------------------------------------- |
| `target.status`       | pending, dari baris lama di sales         |
| `EXCLUDED.status`     | delivered, dari baris masukan             |
| `target.updated_at`   | Waktu pembaruan yang tersimpan sebelumnya |
| `EXCLUDED.updated_at` | Waktu pembaruan yang dibawa masukan       |

Pada assignment `status = EXCLUDED.status`, sisi kiri adalah kolom yang akan
diperbarui di sales dan sisi kanan adalah nilai penggantinya. Prinsip yang sama
berlaku untuk order_date, dealer_id, vehicle_id, qty, unit_price, dan updated_at.
order_id tidak diganti karena digunakan untuk mencocokkan pesanan.

#### 5. WHERE: batasi kapan update boleh dilakukan

```sql
WHERE target.updated_at IS NULL OR EXCLUDED.updated_at > target.updated_at;
```

Ada dua alasan untuk mengizinkan update:

1. `target.updated_at IS NULL`: baris lama belum memiliki timestamp pembaruan.
2. `EXCLUDED.updated_at > target.updated_at`: timestamp masukan lebih baru.

Operator OR berarti cukup salah satu kondisi benar. Pemeriksaan ini dilakukan
terhadap baris yang konfliknya sudah ditemukan. WHERE tersebut membatasi DO UPDATE,
bukan menyaring seluruh SELECT dan bukan syarat bagi ID baru untuk diinsert.
Timestamp masukan selalu diisi pada baris yang lolos validasi pipeline ini.

Jika timestamp sama atau lebih lama, update tidak dilakukan; baris lama tetap ada
dan baris tersebut tidak dihitung sebagai applied. SQL tidak mencatatnya sebagai
penolakan Python di CSV rejected.

#### 6. Contoh tiga keputusan dalam satu batch

Misalkan sales sudah berisi ORD-001 dan ORD-002, keduanya pending dengan timestamp
`2026-11-12 10:00:00`. Staging berisi:

| order_id | status masukan | updated_at masukan  | Hasil                      |
| -------- | -------------- | ------------------- | -------------------------- |
| ORD-001  | delivered      | 2026-11-13 10:00:00 | UPDATE karena lebih baru   |
| ORD-002  | cancelled      | 2026-11-11 10:00:00 | Lewati karena lebih lama   |
| ORD-003  | pending        | 2026-11-13 10:00:00 | INSERT karena ID belum ada |

Dengan asumsi semua kolom lain valid dan terisi, hasil query adalah 2 applied
(1 insert + 1 update) dan 1 skipped_same_or_older. Contoh ini ilustrasi, bukan isi
database yang dibaca saat dokumentasi dibuat.

```text
Setiap baris staging
  ├── ID belum ada → INSERT
  └── ID sudah ada
        ├── Timestamp lama NULL → UPDATE
        ├── Timestamp masukan lebih baru → UPDATE
        └── Timestamp sama/lebih lama → LEWATI
```

Python menjalankan seluruh query ini melalui `conn.execute(text(sql))`. `.rowcount`
menghitung total baris yang berhasil diinsert atau diupdate. Penyimpanan permanen
ditentukan transaksi di Python: load melakukan commit; dry-run melakukan rollback.

### Ringkasan perilaku upsert

| Kondisi                                      | Tindakan            |
| -------------------------------------------- | ------------------- |
| ID belum ada                                 | INSERT pesanan baru |
| ID sudah ada, timestamp lama NULL            | UPDATE dari masukan |
| ID sudah ada, timestamp masukan lebih baru   | UPDATE dari masukan |
| ID sudah ada, timestamp sama atau lebih lama | Lewati              |

Contoh ilustrasi:

```text
sales: ORD-001, pending,   updated_at 2026-11-01 10:00:00
CSV:   ORD-001, delivered, updated_at 2026-11-02 10:00:00
Hasil setelah commit: ORD-001 menjadi delivered dengan timestamp 2 November.
```

Semua kolom pesanan pada bagian SET diganti ketika update; masukan harus berisi baris lengkap. Timestamp sama tetap dilewati walaupun status atau kolom lain berbeda.

Mengimpor ulang file yang sama tidak menggandakan pesanan. Sifat ini disebut **idempotensi**. Hasilnya tetap mengikuti isi masukan, data tujuan, dan aturan timestamp.

## Perbedaan mode

| Tahap                      | --validate-only                        | --dry-run                              | Tanpa flag / load                      |
| -------------------------- | -------------------------------------- | -------------------------------------- | -------------------------------------- |
| Butuh PostgreSQL           | Tidak                                  | Ya                                     | Ya                                     |
| Referensi master           | CSV lokal                              | Tabel DB tujuan                        | Tabel DB tujuan                        |
| Validasi Python            | Ya                                     | Ya                                     | Ya                                     |
| Membuat staging            | Tidak                                  | Ya                                     | Ya                                     |
| Membandingkan dengan sales | Tidak                                  | Ya, jika ada baris valid               | Ya, jika ada baris valid               |
| Menjalankan insert/update  | Tidak                                  | Ya, lalu dibatalkan                    | Ya, lalu disimpan                      |
| Akhir transaksi DB         | Tidak ada                              | ROLLBACK                               | COMMIT jika berhasil                   |
| Laporan                    | Ya, jika proses mencapai tahap laporan | Ya, jika proses mencapai tahap laporan | Ya, jika proses mencapai tahap laporan |

Dry-run menjalankan operasi database sungguhan di dalam transaksi, lalu rollback. Perubahan pada tabel pipeline ini tidak disimpan permanen. Laporan di filesystem tetap ditulis dan tidak ikut rollback. Belum ada laporan nilai sebelum/sesudah per pesanan.

Flag dibuat melalui `argparse` dalam main(), menggunakan `action="store_true"`. `--validate-only` menjadi `args.validate_only`; `--dry-run` menjadi `args.dry_run`. Keduanya tidak boleh dipakai bersama. Tanpa kedua flag, program memilih load.

## Setup dan menjalankan

### 1. Coba tanpa database

Gunakan Python 3.10 atau lebih baru. Jalankan dari folder repo:

```powershell
python pipeline_sales.py data/incoming/sales_2026_11.csv --validate-only
```

Mode ini hanya memakai library bawaan Python. Hasil contoh: **11 accepted, 2 rejected**. Belum memverifikasi koneksi, staging, atau upsert PostgreSQL.

### 2. Siapkan environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

| Library    | Peran                                                |
| ---------- | ---------------------------------------------------- |
| pandas     | Membaca CSV dan mengonversi tanggal pada loader awal |
| SQLAlchemy | Koneksi, transaksi, eksekusi SQL                     |
| psycopg    | Driver PostgreSQL                                    |

Perintah berikut memakai executable dari .venv sehingga tidak perlu mengaktifkan environment melalui PowerShell.

### 3. Siapkan tabel dan data awal satu kali

Jika tabel dan data awal sudah tersedia, lanjut ke langkah 4.

1. Siapkan database PostgreSQL dan akses koneksinya.
2. Jalankan seluruh `sql/create_table.sql` lewat SQL editor pada database tujuan. Perintah CREATE TABLE tidak memakai IF NOT EXISTS, sehingga script ditujukan untuk setup awal.
3. Sesuaikan URL koneksi pada create_engine() di `load_data.py`.
4. Jalankan loader:

```powershell
.\.venv\Scripts\python.exe load_data.py
```

**Loader awal belum membaca DATABASE_URL**; koneksinya ditulis langsung di kode. Pastikan tujuannya sama dengan pipeline tambahan. Jangan ulangi loader pada tabel yang sudah terisi karena append bisa bentrok primary key. Jika operasi gagal, transaksi membatalkan perubahan batch loader itu.

### 4. Atur koneksi pipeline tambahan

Ganti placeholder sesuai tujuan:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@HOST:5432/NAMA_DATABASE'
```

- HOST adalah localhost untuk PostgreSQL sendiri, atau alamat server tujuan.
- Port 5432 adalah contoh; sesuaikan dengan server.
- Karakter khusus pada username/password perlu URL encoding pada komponennya.
- Variable berlaku untuk terminal PowerShell tersebut dan proses turunannya.
- File `.env` tidak dibaca otomatis.
- Akun koneksi memerlukan akses baca master, baca/insert/update sales, penggunaan schema automotive, dan izin membuat tabel sementara pada database.

### 5. Coba ke database tanpa menyimpan perubahan

```powershell
.\.venv\Scripts\python.exe pipeline_sales.py data/incoming/sales_2026_11.csv --dry-run
```

Pada data awal yang belum berubah: 11 accepted, 2 rejected, 11 applied, 0 skipped. Applied berarti perubahan yang sempat dijalankan sebelum rollback. Pesanan baru belum tersimpan dan status pesanan lama tetap seperti sebelum dry-run.

### 6. Impor sungguhan

```powershell
.\.venv\Scripts\python.exe pipeline_sales.py data/incoming/sales_2026_11.csv
```

Jika berhasil, transaksi otomatis commit. Pada data awal, 10 pesanan baru diinsert dan 1 pesanan lama diupdate. Dua baris salah ditolak.

Jalankan ulang setelah load berhasil: 11 accepted, 2 rejected, **0 applied, 11 skipped_same_or_older**. Hasil ini bergantung pada isi database tujuan; bisa berbeda jika datanya sudah berubah.

### 7. Opsi tambahan

```powershell
# Bantuan CLI.
.\.venv\Scripts\python.exe pipeline_sales.py --help

# Folder laporan pilihan sendiri.
.\.venv\Scripts\python.exe pipeline_sales.py data/incoming/sales_2026_11.csv --validate-only --report-dir reports/latihan
```

Path CSV dan path relatif --report-dir mengikuti folder terminal saat dijalankan. Referensi CSV lokal, file SQL merge, dan default folder reports dihitung dari folder script pipeline.

## Membaca laporan

```text
reports/
├── sales_<waktu>_<id>.json
└── sales_<waktu>_<id>_rejected.csv
```

Nama memuat waktu lokal proses dan potongan UUID untuk membedakan batch.

| Field JSON            | Arti                                                     |
| --------------------- | -------------------------------------------------------- |
| file                  | Path absolut CSV masukan                                 |
| mode                  | validate-only, dry-run, atau load                        |
| accepted              | Jumlah baris lolos validasi dan cek duplikat file        |
| rejected              | Jumlah baris ditolak Python                              |
| applied               | Jumlah insert + update; pada dry-run kemudian dibatalkan |
| skipped_same_or_older | accepted dikurangi applied pada mode database            |
| rejected_file         | Path CSV penolakan                                       |

Pada validate-only, applied dan skipped_same_or_older bernilai null karena sales tidak diperiksa. Accepted tidak berarti pasti masuk ke sales: SQL masih bisa melewati baris berdasarkan timestamp.

CSV penolakan berisi kolom masukan ditambah `line` dan `reason`. Untuk CSV satu record per baris, header berada di baris 1 dan record pertama di baris 2. Jika tidak ada penolakan, CSV laporan tetap dibuat dengan header saja.

Timestamp updated_at berasal dari data dan menentukan urutan pembaruan. Waktu pada nama laporan menunjukkan kapan program dijalankan.

## Memeriksa hasil

Setelah load, jalankan lewat SQL editor:

```sql
-- Sepuluh pesanan baru dan satu pesanan yang diperbarui.
SELECT order_id, order_date, dealer_id, vehicle_id,
       qty, unit_price, status, updated_at
FROM automotive.sales
WHERE order_id LIKE 'ORD-DEMO-202611-%'
   OR order_id = 'ORD-2025-003351'
ORDER BY order_id;

-- Seharusnya 10 setelah load pertama berhasil pada data awal.
SELECT COUNT(*) AS demo_orders
FROM automotive.sales
WHERE order_id LIKE 'ORD-DEMO-202611-%';

-- Seharusnya kosong: kedua baris ini ditolak sebelum staging.
SELECT *
FROM automotive.sales
WHERE order_id IN ('ORD-DEMO-INVALID-QTY', 'ORD-DEMO-INVALID-DEALER');
```

## Membuat CSV sendiri

Simpan file baru di data/incoming/, misalnya sales_latihan.csv:

```csv
order_id,order_date,dealer_id,vehicle_id,qty,unit_price,status,updated_at
ORD-LATIHAN-001,2026-11-12,D001,V001,1,265000000,pending,2026-11-12 10:00:00
```

Untuk insert, pilih ID baru. Untuk update, buat batch berikutnya dengan ID sama, nilai lengkap, dan timestamp lebih baru:

```csv
order_id,order_date,dealer_id,vehicle_id,qty,unit_price,status,updated_at
ORD-LATIHAN-001,2026-11-12,D001,V001,1,265000000,delivered,2026-11-13 10:00:00
```

Proses kedua CSV secara terpisah untuk belajar insert lalu update. Jika kedua record ada di satu file, Python menerima baris valid pertama dan menolak berikutnya. Hanya file yang disebut pada perintah yang diproses, bukan seluruh folder incoming.

## Tes dan penanganan masalah

```powershell
python -m unittest discover -s tests -v
```

Tes memeriksa konversi tipe, nilai ditolak, batas nilai database, duplikat file, record kurang kolom, dan komposisi data contoh. Tes belum mengeksekusi staging atau upsert pada PostgreSQL. Gunakan dry-run untuk memeriksa jalur database di environment tujuan.

| Masalah                            | Pemeriksaan                                               |
| ---------------------------------- | --------------------------------------------------------- |
| DATABASE_URL belum diatur          | Set variable pada terminal yang menjalankan pipeline      |
| ModuleNotFoundError                | Pasang requirements dengan executable Python yang sama    |
| Koneksi gagal                      | Periksa host, port, nama DB, kredensial, dan jaringan     |
| Tabel/schema tidak ada             | Jalankan setup SQL pada database tujuan yang sama         |
| Dealer/kendaraan ditolak           | Periksa master tujuan; CSV lokal dan DB bisa berbeda      |
| Header ditolak                     | Cocokkan nama dan urutan kolom dengan contoh              |
| Accepted tetapi skipped            | Bandingkan updated_at dengan nilai di sales               |
| Staging tidak terlihat di editor   | Tabel hanya terlihat pada koneksi pembuatnya              |
| SQL merge gagal dijalankan sendiri | Staging harus dibuat dan diisi pada sesi yang sama        |
| Loader awal bentrok primary key    | Data awal kemungkinan sudah terisi; loader memakai append |

Perilaku kegagalan:

- Baris gagal validasi: masuk rejected; baris lain dilanjutkan.
- Header salah/file tidak ditemukan: program berhenti; laporan batch belum ditulis.
- Error dalam transaksi DB: perubahan database batch di-rollback; laporan batch belum ditulis.
- Penulisan laporan gagal setelah commit: data DB sudah tersimpan; laporan mungkin tidak lengkap.
- Alur selesai menghasilkan exit code 0 meskipun ada penolakan. Lihat jumlah rejected pada ringkasan. Error proses yang ditangani main() menghasilkan exit code 1.

Pesan error DB sengaja umum agar URL koneksi yang mungkin berisi password tidak dicetak. Belum ada laporan error database terperinci.

## Batas implementasi

- Pipeline tambahan hanya menangani sales; tidak mengimpor master atau inventory.
- Tidak mengurangi stok saat delivered. Inventory berisi snapshot per tanggal.
- Belum membatasi perpindahan status. Timestamp lebih baru bisa mengubah delivered menjadi pending.
- Belum ada scheduler, auto-retry, atau impor seluruh folder.
- Batch accepted/rejected ditampung di memori; belum memakai chunk untuk file besar.
- Jalankan satu batch pada satu waktu untuk latihan ini.
- Staging tidak disimpan untuk audit; simpan input dan laporan untuk penelusuran.
- Laporan belum memisahkan jumlah insert/update atau nilai sebelum/sesudah.
- Transaksi DB dan file laporan terpisah; keduanya tidak atomik bersama.
- Git mengabaikan .venv/, __pycache__/, reports/, dan .env.

Versi ini ditujukan untuk belajar impor batch dengan validasi, tabel sementara, upsert berbasis timestamp, transaksi, dan laporan hasil.
