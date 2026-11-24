"""Polat PDF teması — PolaTv (IPTV) uygulamasının renkleri, koyu yüzeyleri ve beyaz çizgi simgeleri.
Renkleri değiştirmek için sadece buraya bak (IPTV: ui/theme/Theme.kt)."""
import tkinter as tk
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk

AD = "Polat PDF"
ZEMIN, YUZEY, YUZEY2, USTUNDE = "#0A0A10", "#13131B", "#1C1C27", "#26263A"
CERCEVE, YAZI, YAZI2 = "#34344A", "#F2F2F7", "#C9C9DA"
VURGU, VURGU2, VURGU_ACIK = "#FF4D6D", "#A4133C", "#FF8FA3"  # IPTV AccentStart, AccentEnd, secondary
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
            "sol_kapat": 0xE8A0, "sol_ac": 0xE89F, "sag_kapat": 0xEA5B, "sag_ac": 0xEA49}

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


def logo(boyut=256):
    """Uygulama logosu: IPTV'deki gibi mercan gradyanlı yuvarlak kare, üstünde beyaz belge."""
    s = boyut * 4  # pürüzsüz kenar için büyük çizip küçült
    yatay = Image.linear_gradient("L").resize((s, s))
    maske = ImageChops.add(yatay, yatay.rotate(90), scale=2)  # sol üstten sağ alta çapraz geçiş
    renkli = Image.composite(Image.new("RGB", (s, s), VURGU2), Image.new("RGB", (s, s), VURGU), maske)
    sekil = Image.new("L", (s, s), 0)
    ImageDraw.Draw(sekil).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=255)
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    im.paste(renkli, (0, 0), sekil)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1, kat = s * 0.27, s * 0.17, s * 0.73, s * 0.83, s * 0.13  # belge ve kıvrık köşesi
    d.polygon([(x0, y0), (x1 - kat, y0), (x1, y0 + kat), (x1, y1), (x0, y1)], fill="white")
    d.polygon([(x1 - kat, y0), (x1 - kat, y0 + kat), (x1, y0 + kat)], fill=VURGU_ACIK)
    try:
        f = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", int(s * 0.15))
    except OSError:
        f = ImageFont.load_default()
    d.text((s / 2, s * 0.62), "PDF", font=f, fill=VURGU2, anchor="mm")
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
    except tk.TclError:
        pass
    pen._polat_logo = ImageTk.PhotoImage(logo(64))  # referans tutulmazsa simge kaybolur
    pen.iconphoto(True, pen._polat_logo)
    try:  # Windows başlık çubuğu da koyu olsun (Windows 10/11)
        import ctypes
        pen.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(pen.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)  # koyu mod
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

