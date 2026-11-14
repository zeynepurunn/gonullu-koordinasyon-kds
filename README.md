# Deprem Sonrası Gönüllü Koordinasyon Sistemi

İstanbul Beykent Üniversitesi — YBS Bitirme Projesi 2026  
Zeynep URUN & Seray OSANMAZ

---

## Teknoloji Stack

| Katman    | Teknoloji                        |
|-----------|----------------------------------|
| Frontend  | HTML5, CSS3, Bootstrap 5, JS     |
| Backend   | Python 3 + Flask                 |
| NLP       | Kural tabanlı anahtar kelime analizi |
| Veritabanı| SQLite (deprem.db)               |

---

## Proje Yapısı

```
deprem_sistemi/
├── app.py          ← Flask backend + NLP + API
├── index.html      ← Gönüllü kayıt sayfası
├── admin.html      ← Yönetici paneli
├── requirements.txt
└── deprem.db       ← Otomatik oluşturulur
```

---

## Veritabanı Şeması

```sql
-- Gönüllüler
volunteers (id, ad_soyad, email, tel, meslek, aciklama, atanan_gorev, kayit_tarihi)

-- Görevler
tasks (id, gorev_adi, aciklama)

-- Atamalar (gönüllü ↔ görev ilişkisi)
assignments (id, volunteer_id, task_id, atama_tarihi)
```

---

## Kurulum ve Çalıştırma

### 1. Python kurulu mu kontrol et
```
python --version   # 3.8+ olmalı
```

### 2. Flask kur
```
pip install flask
```

### 3. Backend'i başlat
```
python app.py
```
Terminal çıktısı:
```
✅  Veritabanı hazır → deprem.db
🚀  http://localhost:5000
```

### 4. Frontend'i aç
- **index.html** → tarayıcıda çift tıkla (gönüllü kayıt)
- **admin.html** → tarayıcıda çift tıkla (yönetici paneli)



---

## NLP Nasıl Çalışır?

```
Kullanıcı → meslek + açıklama girer
     ↓
Metin Ön İşleme (küçük harf, noktalama temizleme)
     ↓
Tokenizasyon (kelimelere ayırma)
     ↓
Anahtar Kelime Eşleştirme (5 görev kategorisi × sözlük)
     ↓
Skor Hesaplama (eşleşen kelime sayısı)
     ↓
En yüksek skorlu görev atanır → veritabanına kaydedilir
```

### Görev Kategorileri
| Görev              | Örnek Anahtar Kelimeler          |
|--------------------|----------------------------------|
| Sağlık Destek      | doktor, hemşire, ilaç, acil      |
| Arama Kurtarma     | enkaz, kurtarma, dağcı, itfaiye  |
| Lojistik Destek    | şoför, kamyon, nakliye, ehliyet  |
| Beslenme Destek    | aşçı, yemek, mutfak, restoran    |
| Psikolojik Destek  | psikolog, travma, terapi, kriz   |

---

## API Endpoint'leri

| Method | URL                                  | Açıklama              |
|--------|--------------------------------------|-----------------------|
| POST   | /api/kayit                           | Gönüllü kaydı + NLP  |
| GET    | /api/gonulluler                      | Tüm gönüllüler        |
| GET    | /api/gonullu/<id>                    | Gönüllü detay         |
| POST   | /api/gonullu/<id>/gorev-guncelle     | Manuel görev değiştir |
| GET    | /api/gorevler                        | Görev listesi         |
| GET    | /api/istatistik                      | Dashboard istatistik  |
| POST   | /api/nlp-test                        | NLP canlı test        |
| POST   | /api/admin-giris                     | Admin girişi          |
