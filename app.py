"""
Deprem Sonrası Gönüllü Koordinasyon Sistemi
Backend: Python Flask + SQLite
NLP: Kural tabanlı anahtar kelime analizi (NLTK benzeri)
"""

from flask import Flask, request, jsonify, render_template, g
import sqlite3, re, os

app = Flask(__name__)
DATABASE = "deprem.db"

# ──────────────────────────────────────────────────────────────
# VERİTABANI BAĞLANTISI
# ──────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    """Veritabanı tablolarını oluştur ve varsayılan görevleri ekle."""
    with sqlite3.connect(DATABASE) as conn:
        conn.executescript("""
            -- Gönüllüler tablosu
            CREATE TABLE IF NOT EXISTS volunteers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_soyad    TEXT    NOT NULL,
                email       TEXT    UNIQUE NOT NULL,
                sifre       TEXT    NOT NULL DEFAULT '1234',
                tel         TEXT,
                meslek      TEXT,
                aciklama    TEXT,
                atanan_gorev TEXT   DEFAULT 'Genel Destek',
                kayit_tarihi TEXT   DEFAULT (datetime('now','localtime'))
            );

            -- Görevler tablosu
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                gorev_adi   TEXT    NOT NULL UNIQUE,
                aciklama    TEXT
            );

            -- Atamalar tablosu (gönüllü ↔ görev ilişkisi)
            CREATE TABLE IF NOT EXISTS assignments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                volunteer_id INTEGER NOT NULL,
                task_id      INTEGER NOT NULL,
                atama_tarihi TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (volunteer_id) REFERENCES volunteers(id),
                FOREIGN KEY (task_id)      REFERENCES tasks(id)
            );

            -- Admin tablosu
            CREATE TABLE IF NOT EXISTS admins (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                email   TEXT UNIQUE NOT NULL,
                sifre   TEXT NOT NULL,
                ad      TEXT
            );

            -- Varsayılan görevler
            INSERT OR IGNORE INTO tasks (gorev_adi, aciklama) VALUES
                ('Sağlık Destek',      'Doktor, hemşire, eczacı ve ilkyardım bilgisine sahip gönüllüler'),
                ('Arama Kurtarma',     'Enkaz altı arama, fiziksel kurtarma ve tahliye operasyonları'),
                ('Lojistik Destek',    'Malzeme taşıma, araç kullanımı ve depo yönetimi'),
                ('Beslenme Destek',    'Yemek hazırlama, dağıtım ve gıda güvenliği'),
                ('Psikolojik Destek',  'Travma danışmanlığı, kriz müdahalesi ve ruh sağlığı desteği'),
                ('Genel Destek',       'Belirli bir uzmanlık alanı olmayan, her türlü yardıma hazır gönüllüler');

            -- Varsayılan admin
            INSERT OR IGNORE INTO admins (email, sifre, ad)
            VALUES ('admin@deprem.gov.tr', 'admin123', 'Yönetici');
        """)
    print("✅  Veritabanı hazır → deprem.db")


# ──────────────────────────────────────────────────────────────
# NLP — KURAL TABANLI GÖREV ATAMA
# (NLTK'nın Türkçe stopword/stemmer desteği zayıf olduğundan
#  sözlük tabanlı ağırlıklı skorlama kullandık)
# ──────────────────────────────────────────────────────────────

GOREV_SOZLUK = {
    "Sağlık Destek": [
        # Meslekler
        "doktor","hekim","hemşire","eczacı","fizyoterapist","laborant",
        "veteriner","diyetisyen","radyolog","anestezi","cerrah","pratisyen",
        "uzman","asistan","stajyer","sağlıkçı","paramedik","ATT",
        # Tıbbi kavramlar
        "sağlık","tıp","acil","ilaç","yaralı","tedavi","hastane","ambulans",
        "klinik","cerrahi","ilkyardım","tıbbi","triaj","serum","tansiyon",
        "nabız","oksijen","yara","bandaj","kırık","ameliyat","reçete",
        "enjeksiyon","damar","steril","dezenfektan","hasta","muayene",
        # Bölümler / kurumlar
        "yoğun bakım","acil servis","eczane","kızılay","sağlık ocağı",
        "dispanser","klinik","poliklinik","diş","ortodonti","göz",
    ],
    "Arama Kurtarma": [
        # Meslekler / roller
        "arama","kurtarma","itfaiyeci","dağcı","dalgıç","halatçı",
        "operatör","ekip","timci","arama kurtarmacı",
        # Fiziksel yetenek
        "güçlü","dayanıklı","fiziksel","kondisyon","spor","atletik",
        # Ekipman
        "enkaz","drone","vinç","kepçe","iş makinesi","testere","sedye",
        "baret","harness","ip","köpek","arama köpeği","termal","kamera",
        # Kurum / eğitim
        "afad","itfaiye","jandarma","asker","polis","akut","umke",
        "arama kurtarma eğitimi","rescue","survival","tahliye","kurtarma",
        # Ortam
        "enkaz altı","yıkık","bina","harabe","göçük","çöken",
    ],
    "Lojistik Destek": [
        # Meslekler
        "şoför","sürücü","nakliyeci","depocu","forklift operatörü",
        "kurye","dağıtımcı","tedarikçi","satın alma",
        # Ehliyet / araç
        "ehliyet","b sınıfı","c sınıfı","kamyon","tır","minibüs",
        "pickup","araba","araç","motosiklet","bisiklet","ambulans",
        # Lojistik kavramlar
        "taşıma","nakliye","depo","lojistik","dağıtım","ulaşım",
        "kargo","tedarik","stok","envanter","sevkiyat","transfer",
        "yükleme","boşaltma","paketleme","ambalaj","depolama",
        # Planlama
        "planlama","organizasyon","koordinasyon","rota","güzergah",
        "harita","gps","takip","filo","yönetim",
    ],
    "Beslenme Destek": [
        # Meslekler
        "aşçı","şef","pastacı","fırıncı","garson","kasiyer",
        "gıda mühendisi","diyetisyen","yemekçi","catering",
        # Pişirme / mutfak
        "yemek","mutfak","pişirme","tarifler","menü","porsiyon",
        "restoran","kafeterya","aşevi","fırın","ocak","kazan",
        # Gıda türleri
        "çorba","ekmek","pilav","sebze","meyve","et","tavuk",
        "konserve","hazır gıda","mama","bebek maması",
        # Dağıtım / hijyen
        "gıda","beslenme","dağıtım","erzak","kumanya","tabldot",
        "paketleme","poşet","kap","hijyen","gıda güvenliği",
        "soğuk zincir","depolama","su","içecek","termos",
    ],
    "Psikolojik Destek": [
        # Meslekler
        "psikolog","psikiyatrist","terapist","danışman","sosyal hizmet",
        "pedagog","rehber öğretmen","sosyolog","çocuk gelişimi",
        "psikolojik danışman","okul psikoloğu",
        # Kavramlar
        "psikoloji","ruh sağlığı","terapi","travma","anksiyete","stres",
        "depresyon","yas","kayıp","kriz","panik","korku","şok",
        "rehabilitasyon","iyileşme","toparlanma","destek","dinleme",
        # Gruplar
        "çocuk","yaşlı","engelli","kadın","aile","yetim","mülteci",
        # Yöntemler
        "empati","iletişim","grup terapisi","bireysel terapi",
        "psikoeğitim","debriefing","psikososyal","müdahale",
        "nefes egzersizi","gevşeme","farkındalık","mindfulness",
    ],
}

def nlp_gorev_ata(meslek: str, aciklama: str) -> str:
    """
    Veri Ön İşleme → Tokenizasyon → Anahtar Kelime Eşleştirme → Skor
    En yüksek skoru alan görevi döndürür.
    """
    # 1. Ön işleme: birleştir, küçük harf, noktalama temizle
    metin = f"{meslek} {aciklama}".lower()
    metin = re.sub(r"[^\w\sığüşöçİĞÜŞÖÇ]", " ", metin)

    # 2. Tokenizasyon (basit boşluk bazlı)
    tokenlar = metin.split()

    # 3. Skorlama
    skorlar = {gorev: 0 for gorev in GOREV_SOZLUK}
    for gorev, kelimeler in GOREV_SOZLUK.items():
        for anahtar in kelimeler:
            for token in tokenlar:
                # kısmi eşleşme: "hemşir" → "hemşire"
                if anahtar in token or token in anahtar:
                    skorlar[gorev] += 1

    # 4. En yüksek skoru bul
    en_yuksek = max(skorlar.values())
    if en_yuksek == 0:
        return "Genel Destek"
    return max(skorlar, key=skorlar.get)


# ──────────────────────────────────────────────────────────────
# CORS BAŞLIKLARI
# ──────────────────────────────────────────────────────────────

@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>",             methods=["OPTIONS"])
def preflight(path): return jsonify({}), 200


# ──────────────────────────────────────────────────────────────
# API — GÖNÜLLÜ İŞLEMLERİ
# ──────────────────────────────────────────────────────────────

@app.route("/api/kayit", methods=["POST"])
def kayit():
    """Gönüllü kaydı + NLP görev atama."""
    d = request.json or {}
    zorunlu = ["ad_soyad", "email"]
    for alan in zorunlu:
        if not d.get(alan):
            return jsonify({"hata": f"'{alan}' zorunludur."}), 400

    # NLP
    atanan = nlp_gorev_ata(d.get("meslek",""), d.get("aciklama",""))

    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO volunteers (ad_soyad, email, sifre, tel, meslek, aciklama, atanan_gorev)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (d["ad_soyad"], d["email"], d.get("sifre","1234"),
             d.get("tel",""), d.get("meslek",""), d.get("aciklama",""), atanan)
        )
        volunteer_id = cur.lastrowid

        # tasks tablosundan task_id bul
        task = db.execute("SELECT id FROM tasks WHERE gorev_adi=?", (atanan,)).fetchone()
        if task:
            db.execute(
                "INSERT INTO assignments (volunteer_id, task_id) VALUES (?,?)",
                (volunteer_id, task["id"])
            )

        db.commit()
        return jsonify({
            "mesaj":        "Kayıt başarılı!",
            "volunteer_id": volunteer_id,
            "atanan_gorev": atanan
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({"hata": "Bu e-posta zaten kayıtlı."}), 409


@app.route("/api/gonulluler", methods=["GET"])
def gonulluler():
    """Tüm gönüllüler (admin için)."""
    db = get_db()
    rows = db.execute("""
        SELECT v.*, t.id as task_id
        FROM volunteers v
        LEFT JOIN assignments a ON a.volunteer_id = v.id
        LEFT JOIN tasks t ON t.id = a.task_id
        ORDER BY v.kayit_tarihi DESC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/gonullu/<int:vid>", methods=["GET"])
def gonullu_detay(vid):
    db = get_db()
    v = db.execute("SELECT * FROM volunteers WHERE id=?", (vid,)).fetchone()
    if not v: return jsonify({"hata": "Bulunamadı"}), 404
    return jsonify(dict(v))


@app.route("/api/gonullu/<int:vid>/gorev-guncelle", methods=["POST"])
def gorev_guncelle(vid):
    """Manuel görev değiştirme (admin)."""
    d = request.json or {}
    gorev = d.get("gorev_adi")
    if not gorev: return jsonify({"hata": "gorev_adi gerekli"}), 400

    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE gorev_adi=?", (gorev,)).fetchone()
    if not task: return jsonify({"hata": "Görev bulunamadı"}), 404

    db.execute("UPDATE volunteers SET atanan_gorev=? WHERE id=?", (gorev, vid))
    db.execute("DELETE FROM assignments WHERE volunteer_id=?", (vid,))
    db.execute("INSERT INTO assignments (volunteer_id, task_id) VALUES (?,?)",
               (vid, task["id"]))
    db.commit()
    return jsonify({"mesaj": "Görev güncellendi."})


# ──────────────────────────────────────────────────────────────
# API — GÖREVLER
# ──────────────────────────────────────────────────────────────

@app.route("/api/gorevler", methods=["GET"])
def gorevler():
    db = get_db()
    rows = db.execute("""
        SELECT t.*, COUNT(a.id) as gonullu_sayisi
        FROM tasks t
        LEFT JOIN assignments a ON a.task_id = t.id
        GROUP BY t.id
    """).fetchall()
    return jsonify([dict(r) for r in rows])


# ──────────────────────────────────────────────────────────────
# API — İSTATİSTİK
# ──────────────────────────────────────────────────────────────

@app.route("/api/istatistik", methods=["GET"])
def istatistik():
    db = get_db()
    toplam = db.execute("SELECT COUNT(*) as c FROM volunteers").fetchone()["c"]
    dagilim = db.execute("""
        SELECT atanan_gorev, COUNT(*) as sayi
        FROM volunteers
        GROUP BY atanan_gorev
        ORDER BY sayi DESC
    """).fetchall()
    return jsonify({
        "toplam_gonullu": toplam,
        "gorev_dagilimi": [dict(r) for r in dagilim]
    })


# ──────────────────────────────────────────────────────────────
# API — NLP TEST (admin paneli için)
# ──────────────────────────────────────────────────────────────

@app.route("/api/nlp-test", methods=["POST"])
def nlp_test():
    d = request.json or {}
    meslek   = d.get("meslek", "")
    aciklama = d.get("aciklama", "")

    metin = f"{meslek} {aciklama}".lower()
    metin = re.sub(r"[^\w\sığüşöçİĞÜŞÖÇ]", " ", metin)
    tokenlar = metin.split()

    skorlar = {}
    for gorev, kelimeler in GOREV_SOZLUK.items():
        skor = 0
        eslesen = []
        for anahtar in kelimeler:
            for token in tokenlar:
                if anahtar in token or token in anahtar:
                    skor += 1
                    if anahtar not in eslesen:
                        eslesen.append(anahtar)
        skorlar[gorev] = {"skor": skor, "eslesen": eslesen}

    atanan = nlp_gorev_ata(meslek, aciklama)
    return jsonify({"atanan_gorev": atanan, "detay": skorlar})


# ──────────────────────────────────────────────────────────────
# API — ADMİN GİRİŞ
# ──────────────────────────────────────────────────────────────

@app.route("/api/admin-giris", methods=["POST"])
def admin_giris():
    d = request.json or {}
    db = get_db()
    admin = db.execute(
        "SELECT * FROM admins WHERE email=? AND sifre=?",
        (d.get("email"), d.get("sifre"))
    ).fetchone()
    if not admin:
        return jsonify({"hata": "Hatalı e-posta veya şifre."}), 401
    return jsonify({"mesaj": "Giriş başarılı", "ad": admin["ad"], "email": admin["email"]})


# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# API — KULLANICI GİRİŞ & PROFİL
# ──────────────────────────────────────────────────────────────

@app.route("/api/kullanici-giris", methods=["POST"])
def kullanici_giris():
    d = request.json or {}
    db = get_db()
    v = db.execute(
        "SELECT * FROM volunteers WHERE email=? AND sifre=?",
        (d.get("email"), d.get("sifre"))
    ).fetchone()
    if not v:
        return jsonify({"hata": "E-posta veya sifre hatali."}), 401
    return jsonify({
        "id": v["id"], "ad_soyad": v["ad_soyad"],
        "email": v["email"], "tel": v["tel"],
        "meslek": v["meslek"], "aciklama": v["aciklama"],
        "atanan_gorev": v["atanan_gorev"], "kayit_tarihi": v["kayit_tarihi"]
    })

@app.route("/api/kullanici/<int:vid>", methods=["GET"])
def kullanici_profil(vid):
    db = get_db()
    v = db.execute("SELECT * FROM volunteers WHERE id=?", (vid,)).fetchone()
    if not v:
        return jsonify({"hata": "Bulunamadi"}), 404
    t = db.execute(
        "SELECT t.aciklama FROM tasks t JOIN assignments a ON a.task_id=t.id WHERE a.volunteer_id=?",
        (vid,)
    ).fetchone()
    return jsonify({
        "id": v["id"], "ad_soyad": v["ad_soyad"],
        "email": v["email"], "tel": v["tel"],
        "meslek": v["meslek"], "aciklama": v["aciklama"],
        "atanan_gorev": v["atanan_gorev"], "kayit_tarihi": v["kayit_tarihi"],
        "gorev_aciklama": t["aciklama"] if t else ""
    })


# ──────────────────────────────────────────────────────────────
# API — PROFİL GÜNCELLE & ŞİFRE SIFIRLA
# ──────────────────────────────────────────────────────────────

@app.route("/api/kullanici/<int:vid>/guncelle", methods=["POST"])
def profil_guncelle(vid):
    d = request.json or {}
    db = get_db()
    # Sadece gelen alanları güncelle
    alanlar = []
    degerler = []
    if d.get("tel") is not None:
        alanlar.append("tel=?"); degerler.append(d["tel"])
    if d.get("meslek") is not None:
        alanlar.append("meslek=?"); degerler.append(d["meslek"])
    if d.get("aciklama") is not None:
        alanlar.append("aciklama=?"); degerler.append(d["aciklama"])
    if d.get("sifre") and len(d["sifre"]) >= 4:
        alanlar.append("sifre=?"); degerler.append(d["sifre"])
    if not alanlar:
        return jsonify({"hata": "Guncellenecek alan yok."}), 400
    degerler.append(vid)
    db.execute(f"UPDATE volunteers SET {', '.join(alanlar)} WHERE id=?", degerler)
    db.commit()
    return jsonify({"mesaj": "Profil guncellendi."})

@app.route("/api/admin/sifre-sifirla", methods=["POST"])
def sifre_sifirla():
    d = request.json or {}
    email = d.get("email")
    yeni_sifre = d.get("yeni_sifre", "1234")
    if not email:
        return jsonify({"hata": "Email gerekli."}), 400
    db = get_db()
    v = db.execute("SELECT id FROM volunteers WHERE email=?", (email,)).fetchone()
    if not v:
        return jsonify({"hata": "Bu e-posta ile kayitli gonullu bulunamadi."}), 404
    db.execute("UPDATE volunteers SET sifre=? WHERE email=?", (yeni_sifre, email))
    db.commit()
    return jsonify({"mesaj": f"Sifre basariyla sifirlandi. Yeni sifre: {yeni_sifre}"})

if __name__ == "__main__":
    init_db()
    print("🚀  http://localhost:5000")
    app.run(debug=True, port=5000)
