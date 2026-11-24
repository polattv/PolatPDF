"""GitHub'daki (polattv/PolatPDF) son sürümü (Release) denetler; yeniyse kurulum dosyasını indirip sessizce çalıştırır."""
import json, os, subprocess, sys, tempfile, urllib.request

DEPO = "polattv/PolatPDF"
SURUM_DOSYASI = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "surum.txt")


def _sayi(s):
    return tuple(int(p) for p in s.strip().lstrip("vV").split("."))


def _indir(url):
    istek = urllib.request.Request(url, headers={"User-Agent": "PolatPDF"})  # GitHub API User-Agent ister
    with urllib.request.urlopen(istek, timeout=30) as y:
        return y.read()


def yerel_surum():
    try:
        with open(SURUM_DOSYASI, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0"


def son_surum():
    """(sürüm, kurulum_url) — sürüm ve dosya aynı Release'ten gelir, biri yüklenmeden diğeri görünmez."""
    r = json.loads(_indir(f"https://api.github.com/repos/{DEPO}/releases/latest"))
    url = next((a["browser_download_url"] for a in r.get("assets", []) if a["name"].lower().endswith(".exe")), None)
    return r["tag_name"].lstrip("vV"), url


def yeni_var_mi():
    """(yeni_mi, sürüm, url). İnternet yoksa hata fırlatır."""
    surum, url = son_surum()
    return bool(url) and _sayi(surum) > _sayi(yerel_surum()), surum, url


def kurulumu_baslat(url):
    """Kurulumu indirir ve arkada başlatır; çağıran hemen kapanmalı ki dosyalar kilitli kalmasın."""
    yol = os.path.join(tempfile.gettempdir(), "PolatPDF-Kurulum.exe")
    with open(yol, "wb") as f:
        f.write(_indir(url))
    subprocess.Popen([yol, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS)


if __name__ == "__main__":
    assert _sayi("v1.10.0") > _sayi("1.9.3") and not _sayi("1.0") > _sayi("1.0")
    print("yerel", yerel_surum())
