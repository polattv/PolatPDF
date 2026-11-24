"""GitHub'daki (polattv/PolatPDF) son sürümü (Release) denetler; yeniyse kurulum dosyasını indirip sessizce çalıştırır."""
import glob, json, os, re, subprocess, sys, tempfile, urllib.request

DEPO = "polattv/PolatPDF"
SURUM_DOSYASI = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "surum.txt")


def _sayi(s):
    return tuple(int(p) for p in re.findall(r"\d+", s))  # "v1.2.0-beta" → (1, 2, 0)


def _indir(url, zaman=30):
    istek = urllib.request.Request(url, headers={"User-Agent": "PolatPDF"})  # GitHub API User-Agent ister
    with urllib.request.urlopen(istek, timeout=zaman) as y:
        return y.read()


def yerel_surum():
    try:
        with open(SURUM_DOSYASI, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0"


def son_surum(zaman=30):
    """(sürüm, kurulum_url) — sürüm ve dosya aynı Release'ten gelir, biri yüklenmeden diğeri görünmez."""
    r = json.loads(_indir(f"https://api.github.com/repos/{DEPO}/releases/latest", zaman))
    url = next((a["browser_download_url"] for a in r.get("assets", []) if a["name"].lower().endswith(".exe")), None)
    return r["tag_name"].lstrip("vV"), url


def yeni_var_mi(zaman=30):
    """(yeni_mi, sürüm, url). url None ise sürüm var ama kurulum dosyası yüklenmemiş. İnternet yoksa hata fırlatır."""
    surum, url = son_surum(zaman)
    return _sayi(surum) > _sayi(yerel_surum()), surum, url


def acik_pencere_sayisi():
    """Çalışan PolatPDF.exe sayısı (bu pencere dahil)."""
    cikti = subprocess.run(["tasklist", "/FI", "IMAGENAME eq PolatPDF.exe", "/FO", "CSV", "/NH"], capture_output=True,
                           text=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    return cikti.lower().count('"polatpdf.exe"')


def eski_kurulumlari_sil():
    """Önceki güncellemelerden geçici klasörde kalan kurulum dosyalarını siler (her biri ~40 MB)."""
    for yol in glob.glob(os.path.join(tempfile.gettempdir(), "PolatPDF-Kurulum*.exe")):
        try:
            os.remove(yol)
        except OSError:
            pass  # kurulum hâlâ çalışıyor (uygulamayı o yeniden açtı): bir sonraki açılışta silinir


def kurulumu_baslat(url):
    """Kurulumu indirir ve arkada başlatır; çağıran hemen kapanmalı ki dosyalar kilitli kalmasın."""
    fd, yol = tempfile.mkstemp(prefix="PolatPDF-Kurulum-", suffix=".exe")  # eski kurulum kilitliyse çakışmasın
    with os.fdopen(fd, "wb") as f:
        f.write(_indir(url))
    subprocess.Popen([yol, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS)


if __name__ == "__main__":
    assert _sayi("v1.10.0") > _sayi("1.9.3") and not _sayi("1.0") > _sayi("1.0")
    assert _sayi("v1.1.0-beta") == (1, 1, 0) and isinstance(acik_pencere_sayisi(), int)
    print("yerel", yerel_surum())
