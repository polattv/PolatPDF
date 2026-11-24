"""Polat PDF teması — PolaTv (IPTV) uygulamasının renkleri, koyu yüzeyleri ve beyaz çizgi simgeleri.
Renkleri değiştirmek için sadece buraya bak (IPTV: ui/theme/Theme.kt)."""
import json, os
import tkinter as tk
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk

AD = "Polat PDF"
AYAR_DOSYASI = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PDFDuzenleyici", "ayarlar.json")


def ayar_oku():
    try:
        with open(AYAR_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ayar_yaz(**degerler):
    ayar = {**ayar_oku(), **degerler}
    os.makedirs(os.path.dirname(AYAR_DOSYASI), exist_ok=True)
    with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(ayar, f, ensure_ascii=False)


ACIK = ayar_oku().get("tema") == "acik"  # renkler açılışta seçilir: tema değişikliği yeniden açınca geçerli
if ACIK:
    ZEMIN, YUZEY, YUZEY2, USTUNDE = "#E6E7EE", "#F5F5F8", "#E2E3EB", "#D3D5E0"
    CERCEVE, YAZI, YAZI2 = "#C3C5D2", "#1B1B24", "#4A4A5C"
    VURGU, VURGU2, VURGU_ACIK = "#FF4D6D", "#C9184A", "#C9184A"
    FARK_EKSI, FARK_ARTI = "#C1121F", "#1B7F3B"
else:
    ZEMIN, YUZEY, YUZEY2, USTUNDE = "#0A0A10", "#13131B", "#1C1C27", "#26263A"
    CERCEVE, YAZI, YAZI2 = "#34344A", "#F2F2F7", "#C9C9DA"
    VURGU, VURGU2, VURGU_ACIK = "#FF4D6D", "#A4133C", "#FF8FA3"  # IPTV AccentStart, AccentEnd, secondary
    FARK_EKSI, FARK_ARTI = "#FF7B8A", "#6FDC8C"
YAZI_TIPI = ("Segoe UI", 10)
KALIN = ("Segoe UI Semibold", 10)

# Windows 11'in Segoe Fluent Icons yazı tipindeki çizgi simgeler (IPTV'deki beyaz simgelerle aynı tarz)
SIMGE_DOSYASI = r"C:\Windows\Fonts\SegoeIcons.ttf"
SIMGELER = {"ac": 0xE8E5, "kaydet": 0xE74E, "geri": 0xE7A7, "ileri": 0xE7A6, "onceki": 0xE76B, "sonraki": 0xE76C,
            "uzaklas": 0xE71F, "yakinlas": 0xE8A3, "dondur": 0xE7AD, "sil": 0xE74D, "pdf_ekle": 0xE8F4,
            "bol": 0xE8C6, "birlestir": 0xE8C8, "ara": 0xE721, "yukari": 0xE70E, "asagi": 0xE70D,
            "duzenle": 0xE8AC, "yazi": 0xE8D2, "degistir": 0xE932, "sec": 0xE8B0, "not": 0xE90A,
            "vurgu": 0xE7E6, "alti": 0xE8DC, "ustu": 0xEDE0, "kalem": 0xEC87, "dikdortgen": 0xE739,
            "daire": 0xEA3A, "cizgi": 0xE738, "ok": 0xE72A, "damga": 0xE8EC, "imza": 0xEE56, "resim": 0xEB9F, "form": 0xE8A1,
            "doldur": 0xE70F, "karart": 0xE73B, "her_yerde": 0xED1A, "renk": 0xE790,
            "donustur": 0xE8AB, "guncelle": 0xE895, "tam_ekran": 0xE740, "yazdir": 0xE749,
            "sikistir": 0xE73F, "sola_dondur": 0xE7A7, "cikar": 0xE8B7, "bos": 0xE7C3, "filigran": 0xE8D2, "ocr": 0xEE6F, "karsilastir": 0xE8F1}

_onbellek = {}


def simge(ad, boyut=18, renk=YAZI):
    """Simgeyi Tk resmi olarak verir. Yazı tipi yoksa None (düğme yalnız yazıyla görünür)."""
    anahtar = (ad, boyut, renk)
    if anahtar not in _onbellek:
        try:
            f = ImageFont.truetype(SIMGE_DOSYASI, boyut)
        except OSError:
            return None
        im = Image.new("RGBA", (boyut + 4, boyut + 4), (0, 0, 0, 0))
        ImageDraw.Draw(im).text(((boyut + 4) / 2, (boyut + 4) / 2), chr(SIMGELER[ad]), font=f, fill=renk, anchor="mm")
        _onbellek[anahtar] = ImageTk.PhotoImage(im)
    return _onbellek[anahtar]


# ---------- logo: "Belge P" — kıvrık köşeli sayfadan oluşan kalın P, derinlikli mercan karo üstünde ----------
# Marka renkleri temadan bağımsız: açık temada da logo aynı kalsın
L_ACIK, L_KOYU, L_KIVRIM, L_GOLGE = "#FF6B84", "#A4133C", "#FF8FA3", "#6E0A28"


def _rgb(h):
    import numpy as np
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)


def _gradyan(s, c1, c2, aci=45):
    """c1'den c2'ye doğrusal geçiş (aci=45: sol üstten sağ alta, 90: yukarıdan aşağı)."""
    import math
    import numpy as np
    y, x = np.mgrid[0:s, 0:s] / (s - 1)
    a = math.radians(aci)
    t = np.clip((x * math.cos(a) + y * math.sin(a)) / (abs(math.cos(a)) + abs(math.sin(a))), 0, 1)[..., None]
    return Image.fromarray((_rgb(c1) * (1 - t) + _rgb(c2) * t).astype("uint8"), "RGB").convert("RGBA")


def _maske(s, ciz):
    m = Image.new("L", (s, s), 0)
    ciz(ImageDraw.Draw(m), s)
    return m


def _boya(im, maske, dolgu):
    """dolgu (renk ya da RGBA resim) maskeden geçirilip im'in üstüne konur."""
    kat = Image.new("RGBA", im.size, dolgu) if isinstance(dolgu, str) else dolgu.copy()
    kat.putalpha(ImageChops.multiply(kat.getchannel("A"), maske))
    im.alpha_composite(kat)


def _golge(im, maske, s, dy=0.022, bulanik=0.025, guc=0.45, kirp=None):
    g = Image.new("L", im.size, 0)
    g.paste(maske.filter(ImageFilter.GaussianBlur(s * bulanik)), (0, int(s * dy)))
    g = g.point(lambda v: int(v * guc))
    if kirp is not None:  # gölge karonun dışına taşmasın
        g = ImageChops.darker(g, kirp)
    _boya(im, g, "#3A0012")


def _karo(s, kucuk):
    """Derinlikli mercan karo: gradyan + üstte parlaklık + altta koyulaşma. (resim, karo maskesi)."""
    import numpy as np
    pay = 0 if kucuk else s * 0.03  # küçükte kenar boşluğu yok: görev çubuğunda iri dursun
    karo = _maske(s, lambda d, s: d.rounded_rectangle((pay, pay, s - 1 - pay, s - 1 - pay), radius=s * 0.23, fill=255))
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    _boya(im, karo, _gradyan(s, L_ACIK, L_KOYU, 60))
    parlak = np.linspace(1, 0, s)[:, None] ** 2.2 * np.ones((1, s))  # üst yarıda yumuşak parlaklık
    _boya(im, Image.fromarray((np.minimum(parlak * 70, 255) * (np.asarray(karo) / 255)).astype(np.uint8)), "#FFFFFF")
    kayik = Image.new("L", (s, s), 0)
    kayik.paste(karo, (0, -int(s * 0.03)))
    alt = np.clip(np.asarray(karo, float) - np.asarray(kayik, float), 0, 255) * 0.35  # alt kenarda iç gölge
    _boya(im, Image.fromarray(alt.astype(np.uint8)).filter(ImageFilter.GaussianBlur(s * 0.01)), L_GOLGE)
    return im, karo


def logo(boyut=256):
    """Uygulama logosu "Belge P": kalın P harfi, sağ üst köşesi kıvrık sayfa köşesi. 4 kat büyük çizilip
    küçültülür (pürüzsüz kenar); 40 pikselin altında daha kalın, sade biçim (görev çubuğu, başlık çubuğu)."""
    s, kucuk = boyut * 4, boyut < 40
    im, karo = _karo(s, kucuk)
    x0, y0, x1, y1, ay = 0.27, 0.17, 0.76, 0.84, 0.62  # P'nin dış kutusu; ay: kasenin altı
    sap, kat = (0.205 if kucuk else 0.185), 0.14
    ic = (x0 + sap, y0 + 0.17, x1 - (0.175 if kucuk else 0.16), ay - (0.15 if kucuk else 0.13))

    def p(d, s):
        d.rounded_rectangle((x0 * s, y0 * s, x1 * s, ay * s), radius=0.2 * s, corners=(False, False, True, False), fill=255)
        d.rounded_rectangle((x0 * s, y0 * s, (x0 + sap) * s, y1 * s), radius=0.04 * s, corners=(False, False, True, True),
                            fill=255)
        d.polygon([((x1 - kat) * s, y0 * s - 2), (x1 * s + 2, y0 * s - 2), (x1 * s + 2, (y0 + kat) * s)], fill=0)
        d.rounded_rectangle([v * s for v in ic], radius=0.05 * s, corners=(False, True, True, False), fill=0)
    m = _maske(s, p)
    kivrim = _maske(s, lambda d, s: d.polygon([((x1 - kat) * s, y0 * s), ((x1 - kat) * s, (y0 + kat) * s),
                                               (x1 * s, (y0 + kat) * s)], fill=255))
    _golge(im, m, s, kirp=karo)
    _boya(im, m, _gradyan(s, "#FFFFFF", "#FFE3E9", 90))
    _golge(im, kivrim, s, dy=0.01, bulanik=0.012, guc=0.4)
    _boya(im, kivrim, _gradyan(s, L_KIVRIM, "#FFC2CE", 45))
    return im.resize((boyut, boyut), Image.LANCZOS)


def uygula(pen):
    """Koyu temayı bütün tk bileşenlerine varsayılan olarak verir. Bileşenler oluşturulmadan ÖNCE çağrılmalı."""
    for anahtar, deger in {"*Background": YUZEY, "*Foreground": YAZI, "*activeBackground": USTUNDE,
                           "*activeForeground": YAZI, "*selectBackground": VURGU, "*selectForeground": "white",
                           "*insertBackground": YAZI, "*highlightThickness": 0, "*Font": YAZI_TIPI,
                           "*Entry.Background": YUZEY2, "*Entry.relief": "flat", "*Spinbox.Background": YUZEY2,
                           "*Spinbox.relief": "flat", "*Spinbox.buttonBackground": YUZEY2, "*Text.Background": YUZEY2,
                           "*Listbox.Background": YUZEY2, "*Button.relief": "flat", "*Checkbutton.selectColor": YUZEY2,
                           "*Menu.Background": YUZEY2, "*Menu.activeBackground": VURGU2, "*Menu.relief": "flat",
                           "*TCombobox*Listbox.Background": YUZEY2}.items():
        pen.option_add(anahtar, deger)
    pen.configure(bg=YUZEY)
    try:
        from tkinter import ttk
        st = ttk.Style(pen)
        st.theme_use("clam")
        st.configure("TCombobox", fieldbackground=YUZEY2, background=YUZEY2, foreground=YAZI, arrowcolor=YAZI,
                     bordercolor=CERCEVE, lightcolor=YUZEY2, darkcolor=YUZEY2)
        st.map("TCombobox", fieldbackground=[("readonly", YUZEY2)], foreground=[("readonly", YAZI)])
        st.configure("Treeview", background=YUZEY, fieldbackground=YUZEY, foreground=YAZI, borderwidth=0,
                     rowheight=24)
        st.map("Treeview", background=[("selected", VURGU2)], foreground=[("selected", "white")])
        st.configure("TProgressbar", background=VURGU, troughcolor=YUZEY2, bordercolor=YUZEY2)
    except tk.TclError:
        pass
    # başlık / görev çubuğu küçük boyut kullanır: o boyutlar için çizilmiş sade biçim de verilsin
    pen._polat_logo = [ImageTk.PhotoImage(logo(b)) for b in (64, 32, 16)]  # referans tutulmazsa simge kaybolur
    pen.iconphoto(True, *pen._polat_logo)
    try:  # Windows başlık çubuğu da temaya uysun (Windows 10/11)
        import ctypes
        pen.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(pen.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(0 if ACIK else 1)), 4)
        renk = int(ZEMIN[5:7] + ZEMIN[3:5] + ZEMIN[1:3], 16)  # COLORREF: BGR
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(renk)), 4)  # başlık rengi
    except Exception:
        pass  # eski Windows: başlık çubuğu varsayılan kalır


def dugme(kap, simge_adi, yazi, komut, sol=True):
    """IPTV tarzı düz düğme: koyu yüzey, üstüne gelince açılır, seçiliyken mercan."""
    resim = simge(simge_adi) if simge_adi else None
    b = tk.Button(kap, text=(" " + yazi if resim and yazi else yazi), image=resim or "", compound="left",
                  command=komut, bg=YUZEY2, fg=YAZI, activebackground=VURGU2, activeforeground="white",
                  relief="flat", bd=0, padx=8, pady=5, cursor="hand2", anchor="w" if sol else "center", font=YAZI_TIPI)
    b.normal = YUZEY2
    b.bind("<Enter>", lambda e: b.config(bg=USTUNDE) if b.normal != VURGU else None)
    b.bind("<Leave>", lambda e: b.config(bg=b.normal))
    return b


def secili_yap(b, secili):
    b.normal = VURGU if secili else YUZEY2
    b.config(bg=b.normal, fg="white" if secili else YAZI)

