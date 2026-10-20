# GeoLab ko internet par dalna (PythonAnywhere, free)

Is ke baad aap ki website `https://AAPKA-USERNAME.pythonanywhere.com` par khulegi.
Neeche jahan `USERNAME` likha hai wahan apna PythonAnywhere username likhein.

## 0. Pehle apne computer par check karein

```bash
pytest
python app.py        # phir http://127.0.0.1:5000/ kholein
```

## 1. Account

1. https://www.pythonanywhere.com par jaa kar **Create a Beginner account** (free) banayein.

## 2. Project ka zip banayein

1. `PythonProject` folder ki **copy** banayein (original ko na chhedein).
2. Copy mein se yeh folders delete kar dein, kyunke hosting ko in ki zaroorat nahi:
   `.venv`, `.idea`, `.pytest_cache`, `_backup`, `_removed`, `__pycache__`
3. **`instance` folder bhi delete karein.** Is mein aap ke computer ka `geolab.db` hai
   (aap ke test users aur unke password hashes). Server par naya khali database khud ban jaye ga.
4. Baqi sab kuch rehne dein. Khaas tor par `triangle_centers.db` aur `.etc_cache/`,
   kyunke inhi se centers ki lookup kaam karti hai.
5. Copy folder par right click > **Send to > Compressed (zipped) folder**.

## 3. Upload karein

1. PythonAnywhere mein **Files** tab kholein.
2. **Upload a file** se zip upload karein (yeh `/home/USERNAME/` mein jaye ga).

## 4. Unzip aur packages

**Consoles** tab > **Bash** kholein, phir:

```bash
unzip PythonProject.zip -d ~/geolab
ls ~/geolab
```

Agar `ls` mein `app.py` nazar na aaye aur sirf ek folder dikhe, to usi folder ke andar jaa kar
yehi path aage use karein (jaise `~/geolab/PythonProject`).

```bash
mkvirtualenv geolab --python=python3.10
pip install -r ~/geolab/requirements.txt
```

(Python 3.10 ya is se naya koi bhi version theek hai.)

## 5. Secret key banayein

Login sessions isi se mehfooz hote hain. Bash mein yeh chalayein aur jo lambi line aaye usey copy kar lein:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 6. Web app banayein

1. **Web** tab > **Add a new web app** > **Manual configuration** > wohi Python version chunein.
2. **Virtualenv** wale box mein likhein: `/home/USERNAME/.virtualenvs/geolab`
3. **Source code** aur **Working directory** mein likhein: `/home/USERNAME/geolab`
   (ya jo folder `app.py` wala hai).
4. **WSGI configuration file** ka link kholein. Us ka saara purana text mita kar yeh likhein
   (`PASTE-YAHAN-APNI-KEY` ki jagah step 5 wali key paste karein):

```python
import os
import sys

path = '/home/USERNAME/geolab'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['SECRET_KEY'] = 'PASTE-YAHAN-APNI-KEY'
os.environ['GEOLAB_PROTECT_SCENES'] = '1'

from app import app as application
```

   - `SECRET_KEY` na lagayi to site purani, sab ko maloom wali default key use karegi, jo khatarnak hai.
   - `GEOLAB_PROTECT_SCENES=1` se scenes sirf login kiye hue log save ya delete kar sakte hain.
     Dekhne (load) ki ijazat sab ko rehti hai.

5. Save karein, phir Web tab par wapas jaa kar bara hara **Reload** button dabayein.
6. `https://USERNAME.pythonanywhere.com` kholein. `/register` se apna account banayein, phir
   `/login`, `/solver`, `/geometry`, `/app` aur `/api` bhi check karein.

(Optional, thori tezi ke liye) Web tab ke **Static files** mein URL `/static/` aur
Directory `/home/USERNAME/geolab/static` jod sakte hain.

## 7. Baad mein tabdeeli karni ho to

Badli hui file Files tab se dobara upload karein (ya Bash mein `unzip -o`), phir Web tab par **Reload** dabayein.
Dobara zip upload karte waqt `instance` folder shamil na karein, warna server ka database (asli users) mit sakta hai.

## Free plan ki hadein, jin ka dhyan rakhein

- **Bahar ke sites:** free plan sirf chuni hui websites tak jaane deta hai. Is liye `/info/<id>`
  ka live ETC fetch block ho sakta hai. Jo centers `.etc_cache` / database mein pehle se hain woh
  phir bhi kaam karenge.
- **Har 3 mahine:** free web app expire ho jati hai. Web tab par **Run until 3 months from today**
  wala button dabana padta hai.
- **Scenes sab ko nazar aate hain:** `GEOLAB_PROTECT_SCENES=1` ke baad bhi koi bhi `/api/scenes`
  se scene dekh sakta hai, aur login kiya hua koi bhi user kisi ka bhi scene badal ya mita sakta hai
  (har scene 2 MB tak). Agar har user ke alag scenes chahiye to isey code mein badalna padega.
- **Debug band rakhein:** `FLASK_DEBUG` kabhi set na karein. Public site par debugger khatarnak hai.
- **HTTPS:** PythonAnywhere `https://` khud deta hai, is liye login ke password raste mein mehfooz rehte hain.
