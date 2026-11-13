# Latihan query analisis penjualan otomotif

Kerjakan 10 soal berikut di `sql/analysis.sql`, menggunakan tabel dalam schema
`automotive`: `dealers`, `vehicles`, `sales`, dan `inventory`.

## Ketentuan

- Omzet dihitung dari `qty * unit_price` untuk pesanan berstatus `delivered`.
- Omzet adalah nilai penjualan, belum memperhitungkan biaya atau laba.
- Gunakan `order_date` sebagai tanggal penjualan; `updated_at` adalah waktu pembaruan data.
- Periode 2026 berarti 1 Januari–31 Desember 2026, kecuali soal menyebut rentang lain.
- Jika soal menyebut bulan tanpa penjualan, bulan tersebut tetap harus muncul dengan nilai 0.
- Gunakan ID sebagai identitas saat mengelompokkan data; nama digunakan untuk tampilan.
- Soal tidak disertai jawaban agar bisa dikerjakan mandiri.

## 1. Peringkat dealer per region

Cari tiga dealer dengan omzet tertinggi di setiap region selama 2026.
Dealer dengan omzet sama mendapat peringkat sama. Gunakan peringkat berurutan tanpa
loncatan (`DENSE_RANK`), lalu ambil peringkat 1–3. Hasil dapat memuat lebih dari tiga
dealer per region jika ada omzet yang sama. Sertakan dealer tanpa penjualan dengan omzet 0.

**Kolom hasil:** region, dealer_id, nama dealer, omzet, jumlah unit terjual, peringkat.

## 2. Pertumbuhan omzet bulanan

Hitung omzet bulanan sepanjang Januari 2025–Oktober 2026, omzet bulan sebelumnya,
dan persentase pertumbuhannya. Bulan tanpa penjualan tetap muncul dengan omzet 0.
Pertumbuhan bulan pertama dan bulan yang omzet sebelumnya 0 ditampilkan sebagai NULL.

**Kolom hasil:** bulan, omzet, omzet bulan sebelumnya, persentase pertumbuhan.

## 3. Kontribusi model terhadap penjualan mereknya

Untuk setiap merek selama 2026, hitung jumlah unit terjual per model dan persentase
kontribusinya terhadap total unit merek tersebut. Tampilkan hanya model yang
berkontribusi minimal 20%. Gunakan vehicle_id sebagai identitas model kendaraan.

**Kolom hasil:** merek, vehicle_id, model, unit terjual, total unit merek, persentase kontribusi.

## 4. Harga jual dibandingkan harga daftar

Hitung rata-rata harga jual tertimbang per model selama 2026:
total omzet dibagi total unit delivered. Bandingkan dengan `vehicles.list_price`
dalam persentase, menggunakan `(list_price - rata_rata_harga_jual) / list_price * 100`.

Cari lima model dengan harga jual rata-rata paling jauh di bawah harga daftar,
dengan syarat minimal 20 unit terjual. Ambil hanya model yang rata-rata harga jualnya
memang lebih rendah daripada harga daftar. Jika persentasenya sama, urutkan berdasarkan vehicle_id.

**Kolom hasil:** vehicle_id, merek, model, unit terjual, harga daftar,
rata-rata harga jual tertimbang, persentase di bawah harga daftar.

## 5. Dealer yang konsisten mengalami penurunan

Cari dealer yang omzetnya turun selama **tiga bulan berturut-turut** pada periode
Januari 2025–Oktober 2026. Gunakan empat bulan berurutan untuk membuktikan tiga
penurunan, misalnya omzet Januari > Februari > Maret > April.

Bulan tanpa penjualan dihitung 0. Semua bulan dalam rangkaian harus berada di dalam
periode soal. Tampilkan setiap rangkaian yang memenuhi syarat; rangkaian boleh tumpang tindih.

**Kolom hasil:** dealer_id, nama dealer, bulan akhir rangkaian,
omzet tiga bulan sebelumnya, omzet dua bulan sebelumnya, omzet satu bulan sebelumnya,
omzet bulan akhir.

## 6. Tingkat pembatalan pesanan

Hitung persentase jumlah pesanan `cancelled` terhadap seluruh pesanan untuk setiap
dealer pada 2026. Gunakan jumlah pesanan, bukan jumlah unit.

Tampilkan dealer yang memiliki minimal 30 pesanan dan tingkat pembatalan lebih tinggi
daripada tingkat pembatalan seluruh perusahaan pada periode yang sama. Tingkat
perusahaan dihitung dari total pesanan cancelled dibagi total seluruh pesanan,
bukan rata-rata persentase masing-masing dealer.

**Kolom hasil:** dealer_id, nama dealer, total pesanan, pesanan cancelled,
persentase pembatalan dealer, persentase pembatalan perusahaan.

## 7. Prioritas penambahan stok

Gunakan tanggal snapshot inventory terbaru secara keseluruhan. Untuk setiap pasangan
dealer–kendaraan yang tercatat pada tanggal tersebut, hitung total unit delivered
selama 90 hari kalender sampai tanggal snapshot, termasuk tanggal itu.

Rentang tanggalnya adalah tanggal snapshot dikurangi 89 hari sampai tanggal snapshot.
Rata-rata penjualan harian adalah total unit periode tersebut dibagi 90, termasuk
hari tanpa penjualan. Estimasi hari stok bertahan adalah stok dibagi rata-rata harian.

Tampilkan pasangan dengan penjualan positif dan estimasi stok bertahan kurang dari
14 hari, termasuk yang stoknya 0. Jangan memakai penjualan setelah tanggal snapshot.

**Kolom hasil:** dealer_id, nama dealer, vehicle_id, model, tanggal snapshot,
stok, unit delivered 90 hari, rata-rata unit per hari, estimasi hari stok bertahan.

## 8. Stok tersedia, tetapi tidak laku

Pada tanggal snapshot inventory terbaru secara keseluruhan, cari pasangan
dealer–kendaraan dengan stok positif tetapi tidak memiliki penjualan delivered
selama 60 hari kalender sampai tanggal snapshot, termasuk tanggal itu.

Rentang tanggalnya adalah tanggal snapshot dikurangi 59 hari sampai tanggal snapshot.
Cari juga tanggal penjualan delivered terakhir sampai tanggal snapshot. Tanggal
tersebut boleh NULL jika belum pernah terjual. Abaikan penjualan setelah snapshot.

**Kolom hasil:** dealer_id, nama dealer, vehicle_id, model, tanggal snapshot,
stok, tanggal penjualan delivered terakhir.

## 9. Dealer penyumbang 80% omzet

Urutkan dealer berdasarkan omzet 2026 dari terbesar. Hitung persentase kontribusi
masing-masing dealer dan persentase kontribusi kumulatifnya terhadap omzet perusahaan.

Ambil kelompok dealer terkecil yang mencapai minimal 80% omzet perusahaan,
**termasuk dealer yang membuat kumulatif melewati 80%**. Jika omzet sama, urutkan
berdasarkan dealer_id agar urutan kumulatif konsisten. Asumsikan omzet perusahaan positif.

**Kolom hasil:** urutan, dealer_id, nama dealer, omzet, persentase kontribusi,
persentase kontribusi kumulatif.

## 10. Penjualan di atas rata-rata dan konsistensi bulanan

Untuk setiap bulan Januari–Oktober 2026, cari dealer yang omzetnya melebihi rata-rata
omzet seluruh dealer pada bulan tersebut. Semua dealer dalam tabel master harus
diperhitungkan; dealer tanpa penjualan diberi omzet 0.

Kemudian tampilkan dealer yang berhasil melampaui rata-rata selama minimal tujuh
bulan. Omzet yang sama dengan rata-rata tidak dihitung sebagai melampaui rata-rata.

**Kolom hasil:** dealer_id, nama dealer, jumlah bulan di atas rata-rata,
total omzet Januari–Oktober 2026.

## Cara mengerjakan

1. Beri komentar nomor soal di `sql/analysis.sql`, lalu tulis query di bawahnya.
2. Jalankan setiap query secara terpisah melalui SQL editor.
3. Periksa contoh hasil secara manual: satu dealer, satu model, atau satu bulan.
4. Periksa pembagian desimal, nilai NULL, rentang tanggal, dan JOIN yang dapat menggandakan baris.
5. Urutkan hasil agar mudah diperiksa. Lakukan pembulatan persentase pada tampilan akhir,
   bukan sebelum pemfilteran atau pemeringkatan.

Nomor 2, 5, 7, dan 9 menggabungkan pengolahan tanggal, CTE, agregasi, atau window function.
