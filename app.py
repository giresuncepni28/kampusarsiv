import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kampusarsiv_kalici_hafiza_v9'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mov', 'avi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(os.path.join(UPLOAD_FOLDER, 'dosyalar'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'videolar'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'resimler'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'avatarlar'), exist_ok=True)

DATABASE = 'database.db'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Kalıcı Hafıza Tabloları
    conn.execute('''
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT UNIQUE NOT NULL,
            sifre TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'Öğrenci',
            bio TEXT DEFAULT 'Henüz biyografi eklenmedi.',
            avatar TEXT DEFAULT '/static/uploads/avatarlar/default.png'
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS takipler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            takip_eden_id INTEGER NOT NULL,
            takip_edilen_id INTEGER NOT NULL,
            UNIQUE(takip_eden_id, takip_edilen_id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS forum_konulari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            icerik TEXT NOT NULL,
            yazar TEXT NOT NULL,
            kategori TEXT DEFAULT 'Genel',
            dosya_adi TEXT DEFAULT '',
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS videolar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            yazar TEXT NOT NULL,
            video_dosya TEXT NOT NULL,
            izlenme INTEGER DEFAULT 0,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS forum_yanitlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konu_id INTEGER NOT NULL,
            yazar TEXT NOT NULL,
            mesaj TEXT NOT NULL,
            medya_dosya TEXT DEFAULT '',
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (konu_id) REFERENCES forum_konulari (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS oy_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_id INTEGER NOT NULL,
            hedef_id INTEGER NOT NULL,
            hedef_tur TEXT NOT NULL,
            UNIQUE(kullanici_id, hedef_id, hedef_tur)
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS zumreler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT NOT NULL,
            brans TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            olusturan TEXT NOT NULL
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS zumre_mesajlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zumre_id INTEGER NOT NULL,
            kullanici_adi TEXT NOT NULL,
            mesaj TEXT NOT NULL,
            medya_dosya TEXT DEFAULT '',
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zumre_id) REFERENCES zumreler (id)
        )
    ''')

    # Sabit Admin Hesabı Kalıcılığı
    admin_user = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", ('yigittalhaozer',)).fetchone()
    if not admin_user:
        hashed_sifre = generate_password_hash('talha333')
        conn.execute("INSERT INTO kullanicilar (kullanici_adi, sifre, rol, bio) VALUES (?, ?, ?, ?)",
                     ('yigittalhaozer', hashed_sifre, 'Admin', 'KampüsArşiv Sistem Yöneticisi'))
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = get_db_connection()
    son_konular = conn.execute("SELECT * FROM forum_konulari ORDER BY id DESC LIMIT 5").fetchall()
    son_videolar = conn.execute("SELECT * FROM videolar ORDER BY id DESC LIMIT 4").fetchall()
    conn.close()
    return render_template('index.html', son_konular=son_konular, son_videolar=son_videolar)

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
            flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
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
            flash('Giriş başarılı!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'error')
            
    return render_template('giris.html')

@app.route('/cikis')
def cikis():
    session.clear()
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('index'))

@app.route('/profil/<string:kullanici_adi>')
def profil_goruntule(kullanici_adi):
    conn = get_db_connection()
    hedef_user = conn.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (kullanici_adi,)).fetchone()
    if not hedef_user:
        conn.close()
        flash('Kullanıcı bulunamadı.', 'error')
        return redirect(url_for('index'))
        
    takipci_sayisi = conn.execute("SELECT COUNT(*) FROM takipler WHERE takip_edilen_id = ?", (hedef_user['id'],)).fetchone()[0]
    takip_edilen_sayisi = conn.execute("SELECT COUNT(*) FROM takipler WHERE takip_eden_id = ?", (hedef_user['id'],)).fetchone()[0]
    
    takipte_mi = False
    if 'user_id' in session:
        kontrol = conn.execute("SELECT * FROM takipler WHERE takip_eden_id = ? AND takip_edilen_id = ?",
                               (session['user_id'], hedef_user['id'])).fetchone()
        if kontrol:
            takipte_mi = True
            
    user_konular = conn.execute("SELECT * FROM forum_konulari WHERE yazar = ? ORDER BY id DESC", (kullanici_adi,)).fetchall()
    user_videolar = conn.execute("SELECT * FROM videolar WHERE yazar = ? ORDER BY id DESC", (kullanici_adi,)).fetchall()
    conn.close()
    return render_template('profil.html', hedef_user=hedef_user, takipci_sayisi=takipci_sayisi, takip_edilen_sayisi=takip_edilen_sayisi, takipte_mi=takipte_mi, user_konular=user_konular, user_videolar=user_videolar)

@app.route('/takip/<int:hedef_id>')
def takip_et_birak(hedef_id):
    if 'user_id' not in session:
        flash('İşlem için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    user_id = session['user_id']
    if user_id == hedef_id:
        flash('Kendinizi takip edemezsiniz.', 'error')
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    hedef = conn.execute("SELECT kullanici_adi FROM kullanicilar WHERE id = ?", (hedef_id,)).fetchone()
    kontrol = conn.execute("SELECT * FROM takipler WHERE takip_eden_id = ? AND takip_edilen_id = ?", (user_id, hedef_id)).fetchone()
    
    if kontrol:
        conn.execute("DELETE FROM takipler WHERE takip_eden_id = ? AND takip_edilen_id = ?", (user_id, hedef_id))
        flash(f'{hedef["kullanici_adi"]} takipten çıkıldı.', 'info')
    else:
        conn.execute("INSERT INTO takipler (takip_eden_id, takip_edilen_id) VALUES (?, ?)", (user_id, hedef_id))
        flash(f'{hedef["kullanici_adi"]} takip edilmeye başlandı!', 'success')
        
    conn.commit()
    conn.close()
    return redirect(url_for('profil_goruntule', kullanici_adi=hedef['kullanici_adi']))

@app.route('/profil/duzenle', methods=['GET', 'POST'])
def profil_duzenle():
    if 'user_id' not in session:
        flash('Giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    conn = get_db_connection()
    if request.method == 'POST':
        bio = request.form.get('bio', '').strip()
        avatar_dosya = request.files.get('avatar_dosya')
        
        avatar_yolu = None
        if avatar_dosya and allowed_file(avatar_dosya.filename):
            filename = secure_filename(avatar_dosya.filename)
            dosya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], 'avatarlar', filename)
            avatar_dosya.save(dosya_yolu)
            avatar_yolu = f'/static/uploads/avatarlar/{filename}'
            
        if avatar_yolu:
            conn.execute("UPDATE kullanicilar SET bio = ?, avatar = ? WHERE id = ?", (bio, avatar_yolu, session['user_id']))
        else:
            conn.execute("UPDATE kullanicilar SET bio = ? WHERE id = ?", (bio, session['user_id']))
            
        conn.commit()
        flash('Profil güncellendi!', 'success')
        
    user = conn.execute("SELECT * FROM kullanicilar WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    return render_template('profil_duzenle.html', user=user)

@app.route('/videolar')
def videolar():
    conn = get_db_connection()
    tum_videolar = conn.execute("SELECT * FROM videolar ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('videolar.html', videolar=tum_videolar)

@app.route('/video/yukle', methods=['GET', 'POST'])
def video_yukle():
    if 'user_id' not in session:
        flash('Video yüklemek için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    if request.method == 'POST':
        baslik = request.form['baslik'].strip()
        aciklama = request.form['aciklama'].strip()
        video_dosya = request.files.get('video_dosya')
        
        if video_dosya and allowed_file(video_dosya.filename):
            filename = secure_filename(video_dosya.filename)
            dosya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], 'videolar', filename)
            video_dosya.save(dosya_yolu)
            db_dosya_yolu = f'/static/uploads/videolar/{filename}'
            
            conn = get_db_connection()
            conn.execute("INSERT INTO videolar (baslik, aciklama, yazar, video_dosya) VALUES (?, ?, ?, ?)",
                         (baslik, aciklama, session['kullanici_adi'], db_dosya_yolu))
            conn.commit()
            conn.close()
            flash('Video başarıyla yüklendi!', 'success')
            return redirect(url_for('videolar'))
        else:
            flash('Geçerli bir video dosyası seçin!', 'error')
            
    return render_template('video_yukle.html')

@app.route('/video/<int:video_id>')
def video_izle(video_id):
    conn = get_db_connection()
    conn.execute("UPDATE videolar SET izlenme = izlenme + 1 WHERE id = ?", (video_id,))
    conn.commit()
    video = conn.execute("SELECT * FROM videolar WHERE id = ?", (video_id,)).fetchone()
    conn.close()
    return render_template('video_izle.html', video=video)

@app.route('/forum')
def forum():
    kategori = request.args.get('kategori', 'Tümü')
    conn = get_db_connection()
    if kategori != 'Tümü':
        konular = conn.execute("SELECT * FROM forum_konulari WHERE kategori = ? ORDER BY id DESC", (kategori,)).fetchall()
    else:
        konular = conn.execute("SELECT * FROM forum_konulari ORDER BY id DESC").fetchall()
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
        dosya = request.files.get('dosya')
        
        dosya_adi = ''
        if dosya and allowed_file(dosya.filename):
            filename = secure_filename(dosya.filename)
            dosya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], 'dosyalar', filename)
            dosya.save(dosya_yolu)
            dosya_adi = f'/static/uploads/dosyalar/{filename}'
            
        conn = get_db_connection()
        conn.execute("INSERT INTO forum_konulari (baslik, icerik, yazar, kategori, dosya_adi) VALUES (?, ?, ?, ?, ?)",
                     (baslik, icerik, session['kullanici_adi'], kategori, dosya_adi))
        conn.commit()
        conn.close()
        flash('Konu ve dosya paylaşıldı!', 'success')
        return redirect(url_for('forum'))
    return render_template('forum_yeni.html')

@app.route('/forum/konu/<int:konu_id>', methods=['GET', 'POST'])
def forum_detay(konu_id):
    conn = get_db_connection()
    konu = conn.execute("SELECT * FROM forum_konulari WHERE id = ?", (konu_id,)).fetchone()
    
    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Yorum yapmak için giriş yapmalısınız.', 'error')
            return redirect(url_for('giris'))
            
        mesaj = request.form.get('mesaj', '').strip()
        medya = request.files.get('medya')
        
        medya_dosya = ''
        if medya and allowed_file(medya.filename):
            filename = secure_filename(medya.filename)
            medya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], 'resimler', filename)
            medya.save(medya_yolu)
            medya_dosya = f'/static/uploads/resimler/{filename}'
            
        if mesaj or medya_dosya:
            conn.execute("INSERT INTO forum_yanitlar (konu_id, yazar, mesaj, medya_dosya) VALUES (?, ?, ?, ?)",
                         (konu_id, session['kullanici_adi'], mesaj, medya_dosya))
            conn.commit()
            
    yanitlar = conn.execute("SELECT * FROM forum_yanitlar WHERE konu_id = ? ORDER BY id ASC", (konu_id,)).fetchall()
    conn.close()
    return render_template('forum_detay.html', konu=konu, yanitlar=yanitlar)

@app.route('/forum/oy/<int:konu_id>/<string:tip>')
def forum_oy(konu_id, tip):
    if 'user_id' not in session:
        flash('Oy kullanmak için giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    kontrol = conn.execute("SELECT * FROM oy_kayitlari WHERE kullanici_id = ? AND hedef_id = ? AND hedef_tur = 'konu'",
                             (user_id, konu_id)).fetchone()
                             
    if kontrol:
        flash('Bu konuya zaten oy verdiniz!', 'info')
    else:
        conn.execute("INSERT INTO oy_kayitlari (kullanici_id, hedef_id, hedef_tur) VALUES (?, ?, 'konu')", (user_id, konu_id))
        if tip == 'like':
            conn.execute("UPDATE forum_konulari SET likes = likes + 1 WHERE id = ?", (konu_id,))
        else:
            conn.execute("UPDATE forum_konulari SET dislikes = dislikes + 1 WHERE id = ?", (konu_id,))
        conn.commit()
        flash('Oyunuz eklendi!', 'success')
        
    conn.close()
    return redirect(url_for('forum_detay', konu_id=konu_id))

@app.route('/zumreler')
def zumreler():
    conn = get_db_connection()
    tum_zumreler = conn.execute("SELECT * FROM zumreler").fetchall()
    conn.close()
    return render_template('zumreler.html', zumreler=tum_zumreler)

@app.route('/zumre/olustur', methods=['GET', 'POST'])
def zumre_olustur():
    if 'user_id' not in session:
        flash('Giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    if request.method == 'POST':
        baslik = request.form['baslik'].strip()
        brans = request.form.get('brans', 'Genel')
        aciklama = request.form['aciklama'].strip()
        
        conn = get_db_connection()
        conn.execute("INSERT INTO zumreler (baslik, brans, aciklama, olusturan) VALUES (?, ?, ?, ?)",
                     (baslik, brans, aciklama, session['kullanici_adi']))
        conn.commit()
        conn.close()
        flash('Zümre oluşturuldu!', 'success')
        return redirect(url_for('zumreler'))
    return render_template('zumre_olustur.html')

@app.route('/zumre/<int:zumre_id>', methods=['GET', 'POST'])
def zumre_detay(zumre_id):
    if 'user_id' not in session:
        flash('Giriş yapmalısınız.', 'error')
        return redirect(url_for('giris'))
        
    conn = get_db_connection()
    zumre = conn.execute("SELECT * FROM zumreler WHERE id = ?", (zumre_id,)).fetchone()
    
    if request.method == 'POST':
        mesaj = request.form.get('mesaj', '').strip()
        medya = request.files.get('medya')
        
        medya_dosya = ''
        if medya and allowed_file(medya.filename):
            filename = secure_filename(medya.filename)
            medya_yolu = os.path.join(app.config['UPLOAD_FOLDER'], 'resimler', filename)
            medya.save(medya_yolu)
            medya_dosya = f'/static/uploads/resimler/{filename}'
            
        if mesaj or medya_dosya:
            conn.execute("INSERT INTO zumre_mesajlar (zumre_id, kullanici_adi, mesaj, medya_dosya) VALUES (?, ?, ?, ?)",
                         (zumre_id, session['kullanici_adi'], mesaj, medya_dosya))
            conn.commit()
            
    mesajlar = conn.execute("SELECT * FROM zumre_mesajlar WHERE zumre_id = ? ORDER BY id ASC", (zumre_id,)).fetchall()
    conn.close()
    return render_template('zumre_detay.html', zumre=zumre, mesajlar=mesajlar)

if __name__ == '__main__':
    app.run(debug=True)
