# Assessment Management

Custom App untuk **Frappe Framework / ERPNext v16** — pengelolaan assessment kompetensi SDM/eksekutif: master data, penjadwalan assessor, lembar kerja penilaian bertingkat (Working Sheet), Quality Control (QC), pembayaran honor assessor, hingga monitoring, laporan, dan KPI.

## Instalasi

```bash
cd ~/frappe-bench
bench get-app https://github.com/<USERNAME>/assessment_management.git
bench --site <nama-site> install-app assessment_management
bench --site <nama-site> migrate
bench build --app assessment_management
bench restart
```

Setelah terpasang, aplikasi muncul di **Apps screen** desk (ikon *Assessment Management*) dan sebagai Workspace **Assessment Management**. Tile hanya tampil untuk pengguna yang punya salah satu role di bawah.

> Untuk branch tertentu: `bench get-app <url> --branch main`.

## Peran & Hak Akses

Tiga role dibuat otomatis saat install/migrate:

| Role | Akses |
|---|---|
| **Assessment Admin** | Penuh pada master data, penjadwalan, pembayaran, revisi hasil (Revise), dan laporan |
| **Assessment Admin View** | Read-only + export di seluruh modul, monitoring, dan laporan |
| **Assessor** | Dashboard pribadi, jadwal miliknya, dan mengisi/mengirim Working Sheet miliknya saja |

Pembatasan data Assessor diterapkan di server (`permission_query_conditions` + `has_permission`). Saat dokumen Assessor dibuat, akun terkait otomatis mendapat role *Assessor* dan *User Permission*.

## Fitur

### Master Data
- **Assessment Project** — nama proyek (unik) dan target jumlah asesi.
- **Assessee** — ID unik (mis. P018526), nama, email, telepon, gender.
- **Assessor** — terhubung ke User login, kode inisial unik (mis. AMF), data pribadi, rekening bank, link feedback default, dan tabel **fee per tipe assessment**.
- **Assessor Group** — kelompok assessor per proyek.
- **Competency Master** — kompetensi, Level 1–5, dan Positive Indicators per level.

### Assessment (dokumen induk per asesi per proyek)
- Otomatis memuat 6 tahap: **SPM, SRB, PK, RW, QC, Feedback**.
- Per tahap: assessor, jadwal, deadline, link meet, status (Pending / In Progress / Overdue / Finished), fee, status pembayaran, tanggal bayar.
- **Fee otomatis** dari master Assessor dan dibekukan setelah Paid.
- **Progres otomatis** `X/6`.
- Status **Overdue** diperbarui otomatis tiap jam.
- Tombol Admin: *Create/Edit Schedule*, *Delete Schedule*, *Delete Finished At*, *Mark as Paid*, *Delete Paid*, *Import Answer Assessee*.
- **Import Answer Assessee** — impor massal jawaban asesi dari Excel/CSV per Project dan tipe (SPM, SRB, PK, Aspirasi Karir, Tanggung Jawab). Kolom pertama `assessee_id`, kolom lain = pertanyaan.

### Working Sheet
Dibuat otomatis begitu assessor dijadwalkan. Empat variasi form:
- **SPM / SRB / PK** — jawaban asesi (collapsible), kompetensi + level + indikator positif, status Meet/Not Meet per level, Rating, Evidence, Analysis, Flag, Assessor Notes.
- **RW (Integrated Rating)** — terkunci sampai SPM, SRB, PK *Finished*; menampilkan perbandingan hasil, Suggested Score otomatis, Final Rating, IG Notes, Strength & Weakness.
- **QC** — terkunci sampai RW *Finished*; menampilkan hasil SPM/SRB/PK/RW, Final QC Rating, QC Notes, dan revisi Strength & Weakness (otomatis terisi dari RW).
- **Feedback** — link video hasil feedback, foto bukti (JPG/JPEG/PNG maks 1 MB), remarks, dan popup *Show Assessment Result Summary* (matriks kompetensi vs Level 1–5).

Perilaku umum: **Auto-Save** draft berkala, **Save as Draft**, **Submit and Finish** (mengunci sheet dan mengisi `finished_at`), **Revise** (khusus Admin, membuka kembali sheet tanpa mengubah `finished_at`), validasi **minimal 1.300 karakter** untuk Strength/Weakness dengan **live character counter**.

### Bank Statement
Arsip bukti transfer honor per proyek (PDF/JPG/PNG maks 1 MB).

### Dashboard & Monitoring
- **Assessment Dashboard** (`/app/assessment-dashboard`) — Admin: Finished vs Target, Assessors Assigned, Paid vs Need to Be Paid, grafik penyelesaian per periode, Latest Activities, ringkasan KPI. Assessor: Finished vs Assigned, status pembayaran pribadi, *My Schedule* dengan tautan ke Working Sheet.
- **Assessment Monitoring** (`/app/assessment-monitoring`) — filter Project/Assessee/Assessor/Status; tab *By Assessee, By Assessor, By Type, By Schedule, By Assessment Matrix*; **export Excel/CSV**.

### Laporan & KPI
- **Final Report Assessee** — Print Format pada Assessment: status sheet, distribusi Assessor Flag, Competence Result (SPM, SRB, PK, IG Final, QC Final), Strength & Weakness. Tombol *Final Report (PDF)* ada di form Assessment.
- **Assessor Fee Summary** — Script Report berdasarkan rentang tanggal (From Date – To Date).
- **Assessor KPI** & **Assessor Group KPI** — per bulan; indikator Jumlah Simulasi, Kualitas Observasi, Konsistensi Pelaporan, Kepatuhan Administratif, Feedback Peserta (On Target / Below Target).
- API laporan: `get_final_report`, `get_assessor_report`, `get_fee_summary`.

## Catatan Teknis
- Working Sheet dan Assessment **tidak** memakai docstatus Submit/Cancel; "Submit and Finish" adalah aksi khusus agar kompatibel dengan auto-save dan Revise.
- Rating berskala 1–5. Item yang diberi Flag boleh tidak dinilai.
- Field status, `finished_at`, dan pembayaran hanya dapat diubah lewat aksi sistem; nilai yang dikirim klien diabaikan.

## Struktur
```
assessment_management/              # root repo (bench get-app)
├── pyproject.toml
├── license.txt
└── assessment_management/          # python package
    ├── hooks.py, api.py, permissions.py, tasks.py, utils.py
    ├── setup/install.py
    └── assessment_management/      # module
        └── doctype/ page/ report/ print_format/ workspace/
```

## Lisensi
MIT
