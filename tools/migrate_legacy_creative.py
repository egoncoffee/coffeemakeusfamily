"""Repeat-safe append-only Creative extension; no business modules/schema edits."""
import argparse
import hashlib
import json
from pathlib import Path

MARKER = "## EGON Creative V5 — VIDEO-FIRST LOCAL PILOT"
ADDITION = """

## EGON Creative V5 — VIDEO-FIRST LOCAL PILOT

Arahan pemilik 12 November 2026 mengganti prioritas Creative menjadi 70% Reels animasi edukasi, 20% video seduh/produk asli, dan 10% carousel/Stories. Persentase dihitung per 10 unit konten, bukan target volume harian baru. Target 50 poster di instruksi lama adalah konteks historis dan bukan target pipeline video ini.

Creative Director mengatur tujuh peran: Coffee Research, Scriptwriting, Visual Director, Animation, Audio & Editing, dan Performance bersama Director. HQ tetap jalur eskalasi bisnis; Finance/Growth/Operations dan seluruh ledger, credential, schema serta integrasi bisnis tetap berlaku.

Implementasi tambahan: repo `egoncoffee/coffeemakeusfamily`, paket Python `egon_creative`; lihat docs/MIGRATION_PLAN.md, agents/*.md dan README repo. SQLite hanya mencatat produksi kreatif. Default lokal: Blender + Python, TTS Indonesia, FFmpeg, MP4 1080×1920 30–60 detik, caption tertanam, brand konsisten. API berbayar default Rp0; plafon Rp25.000/video termasuk versi dan percobaan. Performa nyata tidak dibuat-buat.

Pedoman publik V4 tentang bahasa sederhana, inspirasi, bukti, kebaruan, dan wibawa jujur tetap berlaku. Tidak mengklaim uji lab EGON tanpa log nyata. Nama/roast yang dikonfirmasi pemilik pada arahan ini: Flores Wae Rebo — Medium Roast; Flores Inerie — Full City Roast; Komodo Dragon Blend — Espresso Roast. Jangan menambah spesifikasi lainnya atau mengaktifkan SKU/harga dari daftar ini.

Logo wajib file kanonis asli dari pemilik, tidak digambar ulang, dicrop dari poster generatif, atau diubah. Uji engineering tanpa logo harus diberi penanda dan tidak boleh dipublikasikan. Flow hanya jalur impor manual; tidak ada asumsi API. Gemini opsional hanya setelah free tier dan proyek tanpa billing diverifikasi; tanpa fallback berbayar.

Status: LOCAL PILOT / REVIEW, bukan deployed. Tidak mengaktifkan scheduler, Make, Instagram, uang, pesan keluar atau publishing. Persetujuan manusia terikat pada hash input dan MP4 final. Setelah pilot dan logo direview, pemilik menentukan cutover jadwal lama. Tidak ada agent yang boleh memberi persetujuan publikasi atas pekerjaannya sendiri.

Fokus media Gen Z: sejarah, budaya, insight, tren industri, dan pengetahuan kopi dengan pembuka kuat, visual original, bahasa Indonesia kekinian yang wajar, serta CTA rasa ingin tahu/simpan/bagikan. Foto produk bukan prasyarat untuk video edukasi. Hard-sell bukan default. QA teknis tidak menggantikan review visual, suara, caption, dan ritme oleh manusia. Lihat docs/GEN_Z_EDITORIAL_AND_FLOW.md.
"""


def migrate(root, backup_dir):
    path = Path(root).resolve() / "03_AGENT_INSTRUCTIONS/CREATIVE.md"
    before = path.read_bytes()
    if MARKER in before.decode():
        return {"status": "ALREADY_APPLIED", "file": str(path)}
    sha = hashlib.sha256(before).hexdigest()
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / ("CREATIVE-before-" + sha + ".md")
    if not backup.exists():
        backup.write_bytes(before)
    after = before + ADDITION.encode()
    temp = path.with_name("CREATIVE.md.video-migration.tmp")
    temp.write_bytes(after)
    temp.replace(path)
    return {"status": "APPLIED", "file": str(path), "before_sha256": sha,
            "after_sha256": hashlib.sha256(after).hexdigest(), "backup": str(backup), "other_modules_modified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_root", type=Path)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(migrate(args.legacy_root, args.backup_dir), indent=2))
