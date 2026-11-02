from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kampus_arsiv_secret_2026'

UPLOAD_FOLDER = 'static/uploads'
AVATAR_FOLDER = 'static/avatars'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AVATAR_FOLDER'] = AVATAR_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('kampus.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT UNIQUE NOT NULL,
            sifre TEXT NOT NULL,
            rol TEXT DEFAULT 'Öğrenci',
            biyografi TEXT DEFAULT 'Henüz biyografi yazılmamış.',
            profil_foto TEXT DEFAULT 'default_avatar.png',
            kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        cursor.execute("ALTER TABLE kullanicilar ADD COLUMN profil_foto TEXT DEFAULT 'default_avatar.png'")
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS konular (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            kategori TEXT NOT NULL,
            yazar TEXT NOT NULL,
            icerik TEXT NOT NULL,
            dosya_adi TEXT,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS yorumlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konu_id INTEGER NOT NULL,
            yazar TEXT NOT NULL,
            yorum TEXT NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (konu_id) REFERENCES konular (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zumreler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            kurucu TEXT NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mesajlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gonderen TEXT NOT NULL,
            alici TEXT NOT NULL,
            mesaj TEXT NOT NULL,
            okundu INTEGER DEFAULT 0,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    kategori = request.args.get('kategori')
    conn = get_db_connection()
    
    if kategori and kategori != 'Tümü':
        konular = conn.execute("SELECT * FROM konular WHERE kategori = ? ORDER BY id DESC", (kategori,)).fetchall()
    else:
        konular = conn.execute("SELECT * FROM konular ORDER BY id DESC").fetchall()
        
    son_dosyalar = conn.execute("SELECT * FROM konular WHERE dosya_adi != '' AND dosya_adi IS NOT NULL ORDER BY id DESC LIMIT 5").fetchall()
    son_100 = conn.execute("SELECT * FROM konular ORDER BY id DESC LIMIT 10").fetchall()
    
    conn.close()
    return render_template('index.html', konular=konular, son_dosyalar=son_dosyalar, son_100=son_100, aktif_kategori=kategori or 'Tümü')

@app.route('/kayitol', methods=['GET', 'POST'])
def kayitol():
    if request.method == 'POST':
        kullanici_adi = request.form['kullanici_adi'].strip()
        sifre = request.form['sifre']
        rol = request.form.get('rol', 'Öğrenci')
        
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
            session['kullanici_adi'] = user['kullanici_adi']
            session['rol'] = user['rol']
            flash(f'Hoş geldin, {user["kullanici_adi"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'error')
    return render_template('giris.html')

@app.route('/cikis')
def cikis():
    session.clear()
    flash('Oturum kapatıldı.', 'info')
    return redirect(url_for('index'))

@app.route('/profil/<kullanici_adi>')
def profil(kullanici_adi):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (kullanici_adi,)).fetchone()
    if not user:
        conn.close()
        flash('Kullanıcı bulunamadı!', 'error')
        return redirect(url_for('index'))
        
    konular = conn.execute("SELECT * FROM konular WHERE yazar = ? ORDER BY id DESC", (kullanici_adi,)).fetchall()
    konu_sayisi = len(konular)
    yorum_sayisi = conn.execute("SELECT COUNT(*) FROM yorumlar WHERE yazar = ?", (kullanici_adi,)).fetchone()[0]
    puan = (konu_sayisi * 10) + (yorum_sayisi * 3)
    
    rutbe = "Çırak Öğrenci"
    if puan > 50: rutbe = "Kıdemli Kalfa"
    if puan > 150: rutbe = "Üstat Hoca / Bilgin"
    if user['rol'] == 'Admin': rutbe = "Sistem Yöneticisi [Admin]"

    conn.close()
    return render_template('profil.html', user=user, konular=konular, konu_sayisi=konu_sayisi, yorum_sayisi=yorum_sayisi, puan=puan, rutbe=rutbe)

@app.route('/profil_duzenle', methods=['GET', 'POST'])
def profil_duzenle():
    if 'kullanici_adi' not in session:
        flash('Profilinizi düzenlemek için giriş yapmalısınız!', 'error')
        return redirect(url_for('giris'))
        
    mevcut_kullanici = session['kullanici_adi']
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (mevcut_kullanici,)).fetchone()
    
    # HATA ÇÖZÜMÜ: Kullanıcı veritabanında bulunamazsa oturumu temizle ve yönlendir
    if not user:
        session.clear()
        conn.close()
        flash('Kullanıcı oturumu geçersiz! Lütfen tekrar giriş yapın.', 'error')
        return redirect(url_for('giris'))
    
    if request.method == 'POST':
        yeni_kullanici_adi = request.form['kullanici_adi'].strip()
        biyografi = request.form['biyografi'].strip()
        
        avatar_file = request.files.get('profil_foto')
        yeni_avatar_adi = user['profil_foto'] if (user and user['profil_foto']) else 'default_avatar.png'
        
        if avatar_file and allowed_file(avatar_file.filename):
            yeni_avatar_adi = secure_filename(f"{yeni_kullanici_adi}_{avatar_file.filename}")
            avatar_file.save(os.path.join(app.config['AVATAR_FOLDER'], yeni_avatar_adi))
            
        try:
            if yeni_kullanici_adi != mevcut_kullanici:
                conn.execute("UPDATE kullanicilar SET kullanici_adi = ?, biyografi = ?, profil_foto = ? WHERE kullanici_adi = ?",
                             (yeni_kullanici_adi, biyografi, yeni_avatar_adi, mevcut_kullanici))
                conn.execute("UPDATE konular SET yazar = ? WHERE yazar = ?", (yeni_kullanici_adi, mevcut_kullanici))
                conn.execute("UPDATE yorumlar SET yazar = ? WHERE yazar = ?", (yeni_kullanici_adi, mevcut_kullanici))
                conn.execute("UPDATE zumreler SET kurucu = ? WHERE kurucu = ?", (yeni_kullanici_adi, mevcut_kullanici))
                conn.execute("UPDATE mesajlar SET gonderen = ? WHERE gonderen = ?", (yeni_kullanici_adi, mevcut_kullanici))
                conn.execute("UPDATE mesajlar SET alici = ? WHERE alici = ?", (yeni_kullanici_adi, mevcut_kullanici))
                session['kullanici_adi'] = yeni_kullanici_adi
            else:
                conn.execute("UPDATE kullanicilar SET biyografi = ?, profil_foto = ? WHERE kullanici_adi = ?",
                             (biyografi, yeni_avatar_adi, mevcut_kullanici))
                             
            conn.commit()
            conn.close()
            flash('Profiliniz başarıyla güncellendi!', 'success')
            return redirect(url_for('profil', kullanici_adi=session['kullanici_adi']))
        except sqlite3.IntegrityError:
            conn.close()
            flash('Bu kullanıcı adı başka bir üye tarafından kullanılıyor!', 'error')
            return redirect(url_for('profil_duzenle'))
            
    conn.close()
    return render_template('profil_duzenle.html', user=user)

@app.route('/zumreler')
def zumreler():
    conn = get_db_connection()
    liste = conn.execute("SELECT * FROM zumreler ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('zumreler.html', zumreler=liste)

@app.route('/zumre_olustur', methods=['GET', 'POST'])
def zumre_olustur():
    if 'kullanici_adi' not in session:
        flash('Zümre oluşturmak için giriş yapmalısınız!', 'error')
        return redirect(url_for('giris'))
    
    if request.method == 'POST':
        ad = request.form['ad'].strip()
        aciklama = request.form['aciklama'].strip()
        kurucu = session['kullanici_adi']
        
        conn = get_db_connection()
        conn.execute("INSERT INTO zumreler (ad, aciklama, kurucu) VALUES (?, ?, ?)", (ad, aciklama, kurucu))
        conn.commit()
        conn.close()
        flash('Zümre başarıyla kuruldu!', 'success')
        return redirect(url_for('zumreler'))
        
    return render_template('zumre_olustur.html')

@app.route('/dm/<alici>', methods=['GET', 'POST'])
def dm(alici):
    if 'kullanici_adi' not in session:
        flash('Özel mesaj göndermek için giriş yapmalısınız!', 'error')
        return redirect(url_for('giris'))
        
    gonderen = session['kullanici_adi']
    conn = get_db_connection()
    
    if request.method == 'POST':
        mesaj = request.form['mesaj'].strip()
        if mesaj:
            conn.execute("INSERT INTO mesajlar (gonderen, alici, mesaj) VALUES (?, ?, ?)", (gonderen, alici, mesaj))
            conn.commit()
            flash('Mesaj gönderildi.', 'success')
            
    mesajlar = conn.execute('''
        SELECT * FROM mesajlar 
        WHERE (gonderen = ? AND alici = ?) OR (gonderen = ? AND alici = ?) 
        ORDER BY id ASC
    ''', (gonderen, alici, alici, gonderen)).fetchall()
    
    conn.close()
    return render_template('dm.html', alici=alici, mesajlar=mesajlar)

@app.route('/admin')
def admin():
    if session.get('rol') != 'Admin':
        flash('Bu sayfaya erişim yetkiniz yok!', 'error')
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    kullanicilar = conn.execute("SELECT * FROM kullanicilar ORDER BY id DESC").fetchall()
    konular = conn.execute("SELECT * FROM konular ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('admin.html', kullanicilar=kullanicilar, konular=konular)

@app.route('/admin/sil_konu/<int:id>')
def admin_sil_konu(id):
    if session.get('rol') != 'Admin': return redirect(url_for('index'))
    conn = get_db_connection()
    conn.execute("DELETE FROM konular WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Konu silindi.', 'info')
    return redirect(url_for('admin'))

@app.route('/yeni', methods=['GET', 'POST'])
def yeni_konu():
    if 'kullanici_adi' not in session:
        flash('Konu açmak için giriş yapmalısınız!', 'error')
        return redirect(url_for('giris'))
    if request.method == 'POST':
        baslik = request.form['baslik'].strip()
        kategori = request.form['kategori']
        icerik = request.form['icerik'].strip()
        yazar = session['kullanici_adi']
        
        dosya = request.files.get('dosya')
        dosya_adi = ""
        if dosya and allowed_file(dosya.filename):
            dosya_adi = secure_filename(dosya.filename)
            dosya.save(os.path.join(app.config['UPLOAD_FOLDER'], dosya_adi))
            
        conn = get_db_connection()
        conn.execute("INSERT INTO konular (baslik, kategori, yazar, icerik, dosya_adi) VALUES (?, ?, ?, ?, ?)",
                     (baslik, kategori, yazar, icerik, dosya_adi))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('yeni_konu.html')

@app.route('/konu/<int:konu_id>', methods=['GET', 'POST'])
def detay(konu_id):
    conn = get_db_connection()
    if request.method == 'POST':
        if 'kullanici_adi' not in session:
            flash('Yorum yapmak için giriş yapmalısınız!', 'error')
            return redirect(url_for('giris'))
        yorum_metni = request.form['yorum'].strip()
        yazar = session['kullanici_adi']
        if yorum_metni:
            conn.execute("INSERT INTO yorumlar (konu_id, yazar, yorum) VALUES (?, ?, ?)", (konu_id, yazar, yorum_metni))
            conn.commit()
            
    konu = conn.execute("SELECT * FROM konular WHERE id = ?", (konu_id,)).fetchone()
    yorumlar = conn.execute("SELECT * FROM yorumlar WHERE konu_id = ? ORDER BY id ASC", (konu_id,)).fetchall()
    conn.close()
    if not konu: return "Konu bulunamadı!", 404
    return render_template('detay.html', konu=konu, yorumlar=yorumlar)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
