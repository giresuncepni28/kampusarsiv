import os
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'kampusarsiv_gizli_anahtar_v6'

DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Kullanıcılar
    conn.execute('''
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT UNIQUE NOT NULL,
            sifre TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'Öğrenci',
            puan INTEGER DEFAULT 0
        )
    ''')
    
    # Forum Konuları (Trend & Puan Mekanizmalı)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS forum_konulari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            icerik TEXT NOT NULL,
            yazar TEXT NOT NULL,
            kategori TEXT DEFAULT 'Genel',
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            trend_puan INTEGER DEFAULT 0,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Forum Yanıtları
    conn.execute('''
        CREATE TABLE IF NOT EXISTS forum_yanitlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konu_id INTEGER NOT NULL,
            yazar TEXT NOT NULL,
            mesaj TEXT NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (konu_id) REFERENCES forum_konulari (id)
        )
    ''')
    
    # Zümreler
    conn.execute('''
        CREATE TABLE IF NOT EXISTS zumreler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            brans TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            olusturan TEXT NOT NULL
        )
    ''')

    # Zümre Mesajları (Video, Resim, GIF, Emoji Destekli)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS zumre_mesajlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zumre_id INTEGER NOT NULL,
            kullanici_adi TEXT NOT NULL,
            mesaj TEXT NOT NULL,
            medya_url TEXT,
            medya_tur TEXT DEFAULT 'resim', -- resim, gif, video
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zumre_id) REFERENCES zumreler (id)
        )
    ''')

    # Sabit Admin Hesabı (yigittalhaozer / talha333)
    admin_user = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", ('yigittalhaozer',)).fetchone()
    if not admin_user:
        hashed_sifre = generate_password_hash('talha333')
        conn.execute("INSERT INTO kullanicilar (kullanici_adi, sifre, rol, puan) VALUES (?, ?, ?, ?)",
                     ('yigittalhaozer', hashed_sifre, 'Admin', 999))
        
    conn.commit()
    conn.close()

init_db()

# MEB RSS / Haber Çekme Fonksiyonu
def meb_haberlerini_cek():
    haberler = []
    try:
        url = "https://www.meb.gov.tr/baglantilar/rss/rss.xml"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            for idx, item in enumerate(root.findall('./channel/item')[:8]):
                baslik = item.find('title').text if item.find('title') is not None else "MEB Duyurusu"
                detay = item.find('description').text if item.find('description') is not None else "Detay bulunamadı."
                tarih = item.find('pubDate').text if item.find('pubDate') is not None else "Güncel"
                haberler.append({
                    'id': idx + 1,
                    'baslik': baslik,
                    'detay': detay,
                    'tarih': tarih[:16]
                })
    except Exception:
        haberler = [
            {'id': 1, 'baslik': 'MEB Ortaokul & Lise Müfredat Değerlendirmesi', 'detay': 'Eğitimde yeni döneme ilişkin müfredat yenilikleri ve dijital ders materyalleri erişime açıldı.', 'tarih': 'Güncel'},
            {'id': 2, 'baslik': 'Zümre Çalışmaları ve Dijital Arşiv Projesi', 'detay': 'Tüm ortaokul ve lise branş zümreleri ortak ders içeriklerini dijital ortama aktarıyor.', 'tarih': 'Güncel'},
            {'id': 3, 'baslik': 'LGS ve YKS Sınav Hazırlık Destek Paketleri', 'detay': 'Öğrenciler için kazanım kavrama testleri ve örnek yazılı soru kitapçıkları yayımlandı.', 'tarih': 'Bugün'}
        ]
    return haberler

@app.route('/')
def index():
    haberler = meb_haberlerini_cek()
    conn = get_db_connection()
    trend_konular = conn.execute("SELECT * FROM forum_konulari ORDER BY (likes - dislikes + trend_puan) DESC LIMIT 5").fetchall()
    conn.close()
    return render_template('index.html', haberler=haberler, trend_konular=trend_konular)

@app.route('/kayitol', methods=['GET', 'POST'])
def kayitol():
    if request.method == 'POST':
        kullanici_adi = request.form['kullanici_adi'].strip()
        sifre = request.form['sifre']
        rol = request.form.get('rol', 'Öğrenci')
        
        if rol == 'Admin':
            flash('Admin rolüyle dışarıdan kayıt olunamaz!', 'error')
            return redirect(url_for('kayitol'))
        
        hashed_sifre = generate_password_hash(sifre)
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO kullanicilar (kullanici_adi, sifre, rol) VALUES (?, ?, ?)",
                         (kullanici_adi, hashed_sifre, rol))
            conn.commit()
            conn.close()
            flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
            return redirect(url_for('giris'))
        except sqlite3.IntegrityError:
            conn.close()
            flash('Bu kullanıcı adı zaten kullanılıyor!', 'error')
    return render_template('kayitol.html')

@app.route('/giris', methods=['GET', 'POST'])
def giris():
    if request.method == 'POST':
        kullanici_adi = request.form['kullanici_adi'].strip()
        sifre = request.form['sifre']
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (kullanici_adi,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['sifre'], sifre):
            session['user_id'] = user['id']
            session['kullanici_adi'] = user['kullanici_adi']
            session['rol'] = user['rol']
            flash('Hoş geldiniz!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'error')
            
    return render_template('giris.html')

@app.route('/cikis')
def cikis():
    session.clear()
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('index'))

# FORUM ÖZELLİĞİ (Tüm Detaylarıyla)
@app.route('/forum')
def forum():
    kategori = request.args.get('kategori', 'Tümü')
    conn = get_db_connection()
    if kategori != 'Tümü':
        konular = conn.execute("SELECT * FROM forum_konulari WHERE kategori = ? ORDER BY (likes - dislikes + trend_puan) DESC, id DESC", (kategori,)).fetchall()
    else:
        konular = conn.execute("SELECT * FROM forum_konulari ORDER BY (likes - dislikes + trend_puan) DESC, id DESC").fetchall()
    conn.close()
    return render_template('forum.html', konular=konular, secili_kategori=kategori)

@app.route('/forum/yeni', methods=['GET', 'POST'])
def forum_yeni():
    if 'user_id' not in session:
        flash('Konu açmak için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    if request.method == 'POST':
        baslik = request.form['baslik'].strip()
        icerik = request.form['icerik'].strip()
        kategori = request.form.get('kategori', 'Genel')
        yazar = session['kullanici_adi']
        
        conn = get_db_connection()
        conn.execute("INSERT INTO forum_konulari (baslik, icerik, yazar, kategori, trend_puan) VALUES (?, ?, ?, ?, 10)",
                     (baslik, icerik, yazar, kategori))
        conn.execute("UPDATE kullanicilar SET puan = puan + 5 WHERE kullanici_adi = ?", (yazar,))
        conn.commit()
        conn.close()
        flash('Konunuz başarıyla yayınlandı (+5 Puan kazandınız)!', 'success')
        return redirect(url_for('forum'))
    return render_template('forum_yeni.html')

@app.route('/forum/konu/<int:konu_id>', methods=['GET', 'POST'])
def forum_detay(konu_id):
    conn = get_db_connection()
    konu = conn.execute("SELECT * FROM forum_konulari WHERE id = ?", (konu_id,)).fetchone()
    
    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Yanıt yazmak için giriş yapmalısınız.', 'error')
            return redirect(url_for('giris'))
            
        mesaj = request.form.get('mesaj', '').strip()
        if mesaj:
            conn.execute("INSERT INTO forum_yanitlar (konu_id, yazar, mesaj) VALUES (?, ?, ?)",
                         (konu_id, session['kullanici_adi'], mesaj))
            conn.execute("UPDATE forum_konulari SET trend_puan = trend_puan + 2 WHERE id = ?", (konu_id,))
            conn.commit()
            
    yanitlar = conn.execute("SELECT * FROM forum_yanitlar WHERE konu_id = ? ORDER BY id ASC", (konu_id,)).fetchall()
    conn.close()
    return render_template('forum_detay.html', konu=konu, yanitlar=yanitlar)

@app.route('/forum/oy/<int:konu_id>/<string:tip>')
def forum_oy(konu_id, tip):
    if 'user_id' not in session:
        flash('Oy kullanmak için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    conn = get_db_connection()
    if tip == 'like':
        conn.execute("UPDATE forum_konulari SET likes = likes + 1, trend_puan = trend_puan + 3 WHERE id = ?", (konu_id,))
    elif tip == 'dislike':
        conn.execute("UPDATE forum_konulari SET dislikes = dislikes + 1, trend_puan = trend_puan - 2 WHERE id = ?", (konu_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('forum_detay', konu_id=konu_id))

# ZÜMRELER SOHBETİ & MEDYA / VİDEO PAYLAŞMA
@app.route('/zumreler')
def zumreler():
    conn = get_db_connection()
    tum_zumreler = conn.execute("SELECT * FROM zumreler").fetchall()
    conn.close()
    return render_template('zumreler.html', zumreler=tum_zumreler)

@app.route('/zumre/olustur', methods=['GET', 'POST'])
def zumre_olustur():
    if 'user_id' not in session:
        flash('Zümre oluşturmak için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    if request.method == 'POST':
        baslik = request.form['baslik'].strip()
        brans = request.form.get('brans', 'Türkçe (Ortaokul)')
        aciklama = request.form['aciklama'].strip()
        olusturan = session['kullanici_adi']
        
        conn = get_db_connection()
        conn.execute("INSERT INTO zumreler (baslik, brans, aciklama, olusturan) VALUES (?, ?, ?, ?)",
                     (baslik, brans, aciklama, olusturan))
        conn.commit()
        conn.close()
        flash('Zümre başarıyla oluşturuldu!', 'success')
        return redirect(url_for('zumreler'))
    return render_template('zumre_olustur.html')

@app.route('/zumre/<int:zumre_id>', methods=['GET', 'POST'])
def zumre_detay(zumre_id):
    if 'user_id' not in session:
        flash('Zümre sohbetine katılmak için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    conn = get_db_connection()
    zumre = conn.execute("SELECT * FROM zumreler WHERE id = ?", (zumre_id,)).fetchone()
    
    if request.method == 'POST':
        mesaj = request.form.get('mesaj', '').strip()
        medya_url = request.form.get('medya_url', '').strip()
        medya_tur = request.form.get('medya_tur', 'resim') # resim, gif, video
        kullanici_adi = session['kullanici_adi']
        
        if mesaj or medya_url:
            conn.execute("INSERT INTO zumre_mesajlar (zumre_id, kullanici_adi, mesaj, medya_url, medya_tur) VALUES (?, ?, ?, ?, ?)",
                         (zumre_id, kullanici_adi, mesaj, medya_url, medya_tur))
            conn.commit()
            
    mesajlar = conn.execute("SELECT * FROM zumre_mesajlar WHERE zumre_id = ? ORDER BY id ASC", (zumre_id,)).fetchall()
    conn.close()
    return render_template('zumre_detay.html', zumre=zumre, mesajlar=mesajlar)

@app.route('/zumre/mesaj/oy/<int:mesaj_id>/<string:tip>')
def zumre_mesaj_oy(mesaj_id, tip):
    if 'user_id' not in session:
        return jsonify({'error': 'Yetkisiz'}), 403
    conn = get_db_connection()
    mesaj = conn.execute("SELECT zumre_id FROM zumre_mesajlar WHERE id = ?", (mesaj_id,)).fetchone()
    if tip == 'like':
        conn.execute("UPDATE zumre_mesajlar SET likes = likes + 1 WHERE id = ?", (mesaj_id,))
    elif tip == 'dislike':
        conn.execute("UPDATE zumre_mesajlar SET dislikes = dislikes + 1 WHERE id = ?", (mesaj_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('zumre_detay', zumre_id=mesaj['zumre_id']))

# YAPAY ZEKA YAZILI SİHİRBAZI (ORTAOKUL & LİSE BRANŞLARI)
@app.route('/ai-yazili-olustur', methods=['GET', 'POST'])
def ai_yazili_olustur():
    if 'user_id' not in session:
        flash('Bu aracı kullanmak için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    soru_paketi = None
    if request.method == 'POST':
        ders = request.form.get('ders', 'Türkçe')
        seviye = request.form.get('seviye', '8. Sınıf (LGS Tarzı)')
        zorluk = request.form.get('zorluk', 'Orta')
        
        soru_paketi = {
            "ders": ders,
            "seviye": seviye,
            "zorluk": zorluk,
            "sorular": [
                f"1. {ders} dersi {seviye} kazanımlarına uygun ana kavramları açıklayınız.",
                f"2. {ders} dersine ait uygulama sorusunu aşama aşama çözünüz ({zorluk} Seviye).",
                f"3. Verilen metin veya tablo üzerinden {ders} mantığına göre yorum yapınız.",
                f"4. Mantık ve muhakeme gerektiren yeni nesil {ders} sorusu."
            ]
        }
    return render_template('ai_yazili.html', soru_paketi=soru_paketi)

if __name__ == '__main__':
    app.run(debug=True)
