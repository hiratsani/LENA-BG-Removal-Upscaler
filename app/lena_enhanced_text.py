from lena_text import COPY

COPY.update(
    {
        "tagline": (
            "Hapus latar. Perbesar foto.",
            "Remove backgrounds. Enlarge photos.",
        ),
        "remove_tab": ("Hapus Latar", "Remove BG"),
        "upscale_tab": ("Upscale", "Upscale"),
        "models": ("Models", "Models"),
        "model_what": ("Model itu apa?", "What’s a model?"),
        "model_explanation": (
            "Model adalah AI yang memproses fotomu. Setiap model punya kecepatan, detail, dan kualitas hasil yang berbeda-beda.",
            "A model is the AI that processes your photo. Each model offers different speed, detail, and output quality.",
        ),
        "model_intro": (
            "Pilih model sesuai kebutuhan. Foto tetap diproses di perangkatmu.",
            "Choose models for your needs. Photos stay on your device.",
        ),
        "download_all": ("Download Semua", "Download All"),
        "all_hint": ("Tujuh model tambahan", "Seven optional models"),
        "available": ("Ready", "Ready"),
        "included": ("Bawaan", "Included"),
        "upscale_title": ("Perbesar Foto", "Enlarge Photo"),
        "upscale_description": (
            "Perbesar foto dan rapikan noise, blur, serta kompresi.",
            "Enlarge photos and reduce noise, blur, and compression.",
        ),
        "scale": ("Pembesaran", "Scale"),
        "scale_note": (
            "Model bekerja pada 4×; hasil 2× diperkecil dari hasil model. Transparansi PNG dipertahankan.",
            "The model runs at 4×; 2× is resized from its output. PNG transparency is preserved.",
        ),
        "upscale_hint": (
            "Satu model. Detail foto lebih jelas.",
            "One model. Clearer photo details.",
        ),
        "send_upscale": ("Lanjut ke Upscale →", "Send to Upscale →"),
        "send_remove": ("Lanjut Hapus Latar →", "Send to Remove BG →"),
        "transfer_hint": (
            "Hasil tab ini menjadi input tab tujuan.",
            "Use this result as the other tab’s input.",
        ),
        "dimensions_empty": (
            "Masukkan foto untuk melihat ukuran hasil.",
            "Choose a photo to see the output dimensions.",
        ),
        "output_limit": (
            "Hasil maksimal 64 megapiksel. Pilih 2× atau gunakan foto yang lebih kecil.",
            "Output is limited to 64 megapixels. Choose 2× or use a smaller photo.",
        ),
        "admin_hint": (
            "Drag-and-drop dari Explorer tidak tersedia dalam mode administrator. Buka LENA tanpa administrator, atau gunakan Masukan Foto / Ctrl+V.",
            "Explorer drag-and-drop is unavailable in administrator mode. Open LENA normally, or use Choose Photo / Ctrl+V.",
        ),
        "upscale_error": (
            "Upscale belum berhasil. Coba foto yang lebih kecil atau mode CPU di Settings. Rincian tersimpan di app-error.log.",
            "Upscale could not finish. Try a smaller photo or CPU mode in Settings. Details are saved in app-error.log.",
        ),
        "upscale_guide": (
            "Upscale: pilih 2× atau 4×, download RealWebPhoto satu kali, lalu klik Upscale. Gunakan tombol Lanjut untuk memproses hasil di tab lain. Pindah tab saja tidak menjalankan proses. Ctrl+V bisa menempelkan gambar atau file foto.",
            "Upscale: choose 2× or 4×, download RealWebPhoto once, then click Upscale. Use Send to process the result in the other tab. Switching tabs alone never starts processing. Ctrl+V accepts copied images or photo files.",
        ),
        "welcome_body": (
            "Basic sudah siap. Model tambahan tersedia untuk hasil hapus latar yang lebih detail dan untuk memperbesar foto. Download hanya yang kamu perlukan.",
            "Basic is ready. Optional models offer finer background removal and photo upscaling. Download only what you need.",
        ),
        "upscale_slow": (
            "Memproses dengan CPU. Foto besar dapat memerlukan waktu lama.",
            "Processing on CPU. Large photos can take a long time.",
        ),
        "all_ready": ("Semua model sudah Ready", "All models are Ready"),
        "model_ready_hint": (
            "Ready berarti model sudah tersimpan dan bisa dipakai offline.",
            "Ready means the model is downloaded and available offline.",
        ),
        "download_error": (
            "Download {model} gagal. Penyebab: {reason}\nCoba lagi nanti atau gunakan Basic sementara.",
            "Could not download {model}. Reason: {reason}\nTry again later or use Basic for now.",
        ),
    }
)
COPY.update(
    {
        "photo": ("+ Masukkan Foto", "+ Choose Photo"),
        "remove_tagline": (
            "Hilangkan latar belakang. Seketika.",
            "Remove backgrounds. In an instant.",
        ),
        "up_tagline": ("Tajamkan gambar. Seketika.", "Sharper images. In an instant."),
        "upscale_hint": (
            "Satu model, satu klik.\nCepat dan tanpa ribet.",
            "One model, one click.\nQuick and simple.",
        ),
        "jpg_background": (
            "Pilih latar untuk area transparan",
            "Choose a background for transparent areas",
        ),
        "white": ("Putih", "White"),
        "black": ("Hitam", "Black"),
        "saved_jpg": ("JPG berhasil di-Save", "JPG saved"),
        "zoom_help": (
            "Zoom: gunakan scroll untuk memperbesar, drag untuk menggeser. Fit menampilkan seluruh foto; 100% menampilkan ukuran piksel asli.",
            "Zoom: scroll to magnify and drag to pan. Fit shows the whole photo; 100% shows actual pixels.",
        ),
        "upscale_steps": (
            "1. Masukkan foto, lalu pilih skala 2× atau 4×.\n\n2. Klik Upscale. Model SPAN akan di-download jika belum tersedia. Tunggu proses selesai.\n\n3. Klik Save PNG atau JPG. Untuk JPG, pilih latar putih atau hitam jika foto memiliki area transparan.",
            "1. Choose a photo, then select 2× or 4×.\n\n2. Click Upscale. SPAN is downloaded if needed. Wait for processing to finish.\n\n3. Click Save PNG or JPG. For transparent photos, choose a white or black JPG background.",
        ),
        "transfer_guide": (
            "Mode dikunci selama proses. Setelah selesai, gunakan tombol Lanjut untuk mengirim hasil ke tool lain. Pindah mode saja tidak menjalankan proses. Ctrl+V untuk menempelkan gambar atau file foto.",
            "The mode is locked during processing. Use Send after completion to move the result to the other tool. Switching modes does not start processing. Press Ctrl+V to paste an image or photo file.",
        ),
        "gpu_failure_note": (
            "Jika GPU pernah gagal memproses, Auto akan otomatis beralih ke CPU untuk mencegah error berulang.",
            "If a GPU previously failed, Auto switches to CPU to prevent repeated errors.",
        ),
    }
)
COPY["steps"] = (
    COPY["steps"][0]
    .replace("Masukan Foto", "Masukkan Foto")
    .replace("Untuk pilihan lain", "Untuk hasil lebih presisi"),
    COPY["steps"][1],
)
COPY["upscale_guide"] = COPY["upscale_steps"]
COPY["empty"] = (
    COPY["empty"][0].replace("Masukan Foto", "Masukkan Foto"),
    COPY["empty"][1],
)

COPY["process_first"] = (
    "Proses foto terlebih dahulu untuk memakai fitur ini.",
    "Process the photo first to use this feature.",
)

COPY["transfer_guide"] = (
    "Satu foto digunakan bersama di kedua mode. Mode dikunci saat proses. Tombol Lanjut memakai hasil sebagai foto baru untuk tool berikutnya. Ctrl+V untuk menempelkan foto.",
    "Both modes share one photo. Switching is locked during processing. Send uses the result as the new photo for the next tool. Ctrl+V pastes a photo.",
)

COPY["upscale_steps"] = (
    "1. Masukkan foto, lalu pilih 2× atau 4×.\n\n2. Klik Upscale dan tunggu hingga selesai. SPAN sudah tersedia di aplikasi.\n\n3. Klik Save PNG, atau JPG. Untuk foto transparan, JPG menyediakan pilihan latar putih atau hitam.",
    "1. Choose a photo, then pick 2× or 4×.\n\n2. Click Upscale and wait for it to finish. SPAN is included in the app.\n\n3. Click Save PNG, or JPG. For transparent photos, JPG lets you pick a white or black background.",
)
COPY["upscale_guide"] = COPY["upscale_steps"]
COPY["all_hint"] = ("Lima model tambahan", "Five optional models")
COPY.update(
    {
        "language_button": ("Language", "Language"),
        "theme_button": ("Theme", "Theme"),
        "preview_background": ("Latar Preview", "Preview Background"),
        "preview_transparent": ("Transparan", "Transparent"),
        "preview_white": ("Putih", "White"),
        "preview_black": ("Hitam", "Black"),
        "result_incomplete": (
            "Hasil mungkin belum lengkap.",
            "Result may be incomplete.",
        ),
        "try_best": ("Coba Best Quality", "Try Best Quality"),
    }
)
COPY["steps"] = (
    COPY["steps"][0],
    "1. Drop a photo into the app, or click Choose Photo.\n\n2. For a quick result, click Basic.\n\n3. For more control, pick a category, then choose an available quality. Click Download Model if needed.\n\n4. Click Start and wait for it to finish.\n\n5. Drag the divider to compare the original and result.\n\n6. Click Save PNG. Your original image dimensions are kept.",
)

# Universal quality chooser copy.
COPY["mode"] = ("Pilih Kualitas", "Choose Quality")
COPY["steps"] = (
    "1. Masukkan foto.\n\n2. Pilih Basic, Better, atau Best. Download quality tambahan lewat ikon hijau.\n\n3. Aktifkan Hair & Fur hanya untuk rambut, bulu, atau objek berbulu.\n\n4. Klik Remove BG.\n\n5. Geser pembatas untuk membandingkan hasil, lalu simpan PNG atau JPG.",
    "1. Choose a photo.\n\n2. Pick Basic, Better, or Best. Download optional qualities using the green icon.\n\n3. Turn on Hair & Fur only for visible hair, fur, feathers, or fuzzy objects.\n\n4. Click Remove BG.\n\n5. Drag the divider to compare, then save PNG or JPG.",
)
COPY["model_explanation"] = (
    "Basic sudah tersedia. Download Better, Best, dan Hair & Fur satu per satu saat diperlukan.",
    "Basic is included. Download Better, Best, and Hair & Fur individually when needed.",
)
