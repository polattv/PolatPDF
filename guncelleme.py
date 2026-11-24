"""GitHub'daki (polattv/PolatPDF) son sürümü denetler ve uygulama dosyalarını onunla değiştirir."""
import io, os, tempfile, urllib.request, zipfile

DEPO = "polattv/PolatPDF"
KLASOR = os.path.dirname(os.path.abspath(__file__))
SURUM_DOSYASI = os.path.join(KLASOR, "surum.txt")


def _sayi(s):
    return tuple(int(p) for p in s.strip().split("."))


def _indir(url):
    with urllib.request.urlopen(url, timeout=20) as y:
        return y.read()


def yerel_surum():
    try:
        with open(SURUM_DOSYASI, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0"


def uzak_surum():
    return _indir(f"https://raw.githubusercontent.com/{DEPO}/main/surum.txt").decode("utf-8").strip()


def yeni_var_mi():
    """(yeni_mi, uzak_surum). İnternet yoksa hata fırlatır."""
    uzak = uzak_surum()
    return _sayi(uzak) > _sayi(yerel_surum()), uzak


def guncelle():
    """Depodaki dosyaları indirip uygulama klasörüne koyar. Güncellenen dosya adlarını döner."""
    veri = _indir(f"https://github.com/{DEPO}/archive/refs/heads/main.zip")
    yazilanlar = []
    with zipfile.ZipFile(io.BytesIO(veri)) as z:
        for ad in z.namelist():
            parca = ad.split("/")
            if len(parca) != 2 or not parca[1]:  # yalnızca kök klasördeki dosyalar; alt klasör/yol oyunu yok
                continue
            hedef = os.path.join(KLASOR, parca[1])
            fd, gecici = tempfile.mkstemp(dir=KLASOR)
            with os.fdopen(fd, "wb") as f:
                f.write(z.read(ad))
            os.replace(gecici, hedef)  # yarıda kesilirse eski dosya bozulmadan kalır
            yazilanlar.append(parca[1])
    return yazilanlar


if __name__ == "__main__":
    assert _sayi("1.10.0") > _sayi("1.9.3") and not _sayi("1.0") > _sayi("1.0")
    print("yerel", yerel_surum())
