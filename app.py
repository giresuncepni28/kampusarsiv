import os
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'kampusarsiv_gizli_anahtar_guvenli'

DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Kullanıcılar Tablosu
    conn.execute('''
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT UNIQUE NOT NULL,
            sifre TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'Öğrenci'
        )
    ''')
    
    # Zümreler Tablosu
    conn.execute('''
        CREATE TABLE IF NOT EXISTS zumreler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            olusturan TEXT NOT NULL
        )
    ''')

    # Zümre Mesajları ve Paylaşımları Tablosu (Resim, GIF, Emoji destekli)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS zumre_mesajlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zumre_id INTEGER NOT NULL,
            kullanici_adi TEXT NOT NULL,
            mesaj TEXT NOT NULL,
            medya_url TEXT,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zumre_id) REFERENCES zumreler (id)
        )
    ''')

    # Sabit Admin Hesabı Kontrolü (yigittalhaozer / talha333)
    admin_user = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", ('yigittalhaozer',)).fetchone()
    if not admin_user:
        hashed_sifre = generate_password_hash('talha333')
        conn.execute("INSERT INTO kullanicilar (kullanici_adi, sifre, rol) VALUES (?, ?, ?)",
                     ('yigittalhaozer', hashed_sifre, 'Admin'))
        
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
            for item in root.findall('./channel/item')[:6]:
                baslik = item.find('title').text if item.find('title') is not None else "Haber Başlığı"
                link = item.find('link').text if item.find('link') is not None else "#"
                tarih = item.find('pubDate').text if item.find('pubDate') is not None else ""
                haberler.append({'baslik': baslik, 'link': link, 'tarih': tarih[:16]})
    except Exception:
        haberler = [
            {'baslik': 'MEB’den Yeni Eğitim ve Müfredat Açıklaması', 'link': 'https://www.meb.gov.tr', 'tarih': 'Güncel'},
            {'baslik': '2025-2026 Eğitim Öğretim Yılı Takvimi Detayları', 'link': 'https://www.meb.gov.tr', 'tarih': 'Güncel'},
            {'baslik': 'Okullarımızda Dijital Arşiv ve Proje Çalışmaları Başladı', 'link': '#', 'tarih': 'Bugün'}
        ]
    return haberler

@app.route('/')
def index():
    haberler = meb_haberlerini_cek()
    return render_template('index.html', haberler=haberler)

@app.route('/kayitol', methods=['GET', 'POST'])
def kayitol():
    if request.method == 'POST':
        kullanici_adi = request.form['kullanici_adi'].strip()
        sifre = request.form['sifre']
        rol = request.form.get('rol', 'Öğrenci')
        
        if rol == 'Admin':
            flash('Admin rolüyle kayıt olunamaz!', 'error')
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
            flash('Bu kullanıcı adı zaten alınmış!', 'error')
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
            flash('Giriş başarılı, hoş geldiniz!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'error')
            
    return render_template('giris.html')

@app.route('/cikis')
def cikis():
    session.clear()
    flash('Güvenli çıkış yapıldı.', 'info')
    return redirect(url_for('index'))

@app.route('/zumreler')
def zumreler():
    conn = get_db_connection()
    tum_zumreler = conn.execute("SELECT * FROM zumreler").fetchall()
    conn.close()
    return render_template('zumreler.html', zumreler=tum_zumreler)

@app.route('/zumre/olustur', methods=['GET', 'POST'])
def zumre_olustur():
    if 'user_id' not in session or session.get('rol') not in ['Öğretmen', 'Admin']:
        flash('Bu alana yalnızca öğretmenler ve yöneticiler erişebilir.', 'error')
        return redirect(url_for('zumreler'))
        
    if request.method == 'POST':
        baslik = request.form['baslik'].strip()
        aciklama = request.form['aciklama'].strip()
        olusturan = session['kullanici_adi']
        
        conn = get_db_connection()
        conn.execute("INSERT INTO zumreler (baslik, aciklama, olusturan) VALUES (?, ?, ?)",
                     (baslik, aciklama, olusturan))
        conn.commit()
        conn.close()
        flash('Zümre başarıyla oluşturuldu.', 'success')
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
        kullanici_adi = session['kullanici_adi']
        
        if mesaj or medya_url:
            conn.execute("INSERT INTO zumre_mesajlar (zumre_id, kullanici_adi, mesaj, medya_url) VALUES (?, ?, ?, ?)",
                         (zumre_id, kullanici_adi, mesaj, medya_url))
            conn.commit()
            
    mesajlar = conn.execute("SELECT * FROM zumre_mesajlar WHERE zumre_id = ? ORDER BY id ASC", (zumre_id,)).fetchall()
    conn.close()
    return render_template('zumre_detay.html', zumre=zumre, mesajlar=mesajlar)

@app.route('/ai-yazili-olustur', methods=['GET', 'POST'])
def ai_yazili_olustur():
    if 'user_id' not in session:
        flash('Bu aracı kullanmak için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    soru_paketi = None
    if request.method == 'POST':
        ders = request.form.get('ders', 'Matematik')
        seviye = request.form.get('seviye', '9. Sınıf')
        zorluk = request.form.get('zorluk', 'Orta')
        
        soru_paketi = {
            "ders": ders,
            "seviye": seviye,
            "zorluk": zorluk,
            "sorular": [
                f"1. {ders} dersi {seviye} seviyesi için temel kavramları açıklayınız. ({zorluk} Seviye)",
                f"2. Aşağıdaki klasik problem modelini {ders} kurallarına göre çözünüz...",
                f"3. Gerçek hayat senaryolarında {ders} kullanımına dair örnek veriniz.",
                f"4. Analitik düşünme ve yorumlama gerektiren kapsamlı {ders} soru analizi."
            ]
        }
    return render_template('ai_yazili.html', soru_paketi=soru_paketi)

if __name__ == '__main__':
    app.run(debug=True)
