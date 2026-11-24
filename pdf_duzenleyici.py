"""Polat PDF — PyMuPDF + tkinter ile PDF görüntüleyici/düzenleyici (tema: tema.py, PolaTv renkleri).

Kullanım: pythonw pdf_duzenleyici.py [dosya.pdf]     |     python pdf_duzenleyici.py --test
"""
import bisect, json, os, sys, time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import pymupdf
from PIL import ImageTk
import guncelleme
import pdf_islemleri as pi
import tema

KENAR = 10            # ana görünümde sayfanın kenar boşluğu (piksel)
KUCUK_EN = 130        # küçük resim genişliği
GECMIS_SINIRI = 300 * 1024 * 1024  # geri al için en fazla bu kadar bellek
AYAR_KLASORU = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PDFDuzenleyici")
SON_YOLU = os.path.join(AYAR_KLASORU, "son_acilanlar.json")

IPUCU = {"sec": "Seç: bir notun / işaretin üstüne tıklayın; içeriğini görün, düzenleyin ya da silin.",
         "yazi": "Yazı: yazının gideceği yere tıklayın (ya da kutu çizin).",
         "not": "Not: yapışkan notun gideceği yere tıklayın.",
         "vurgu": "Vurgula: vurgulanacak yazının üstünden fareyle kutu çizin.",
         "alti": "Altını çiz: yazının üstünden fareyle kutu çizin.",
         "ustu": "Üstünü çiz: yazının üstünden fareyle kutu çizin.",
         "kalem": "Kalem: fareyle serbest çizin.",
         "dikdortgen": "Dikdörtgen: fareyle çizin.", "daire": "Daire / elips: fareyle çizin.",
         "cizgi": "Çizgi: başlangıçtan bitişe sürükleyin.", "ok": "Ok: başlangıçtan ok ucuna sürükleyin.",
         "damga": "Damga: damganın gideceği kutuyu çizin.",
         "resim": "Resim / İmza: tıklayın (doğal boyutta) ya da kutu çizin (kutuya sığdırılır). Eklenen resim "
                  "Düzenle aracıyla taşınır, köşesinden büyütülür; çift tıklayınca arka planı temizlenir.",
         "duzenle": "Yazıyı düzenle: tıkla = seç · sürükle = taşı · köşedeki kare = büyüt/küçült · çift tıkla / Enter = "
                    "metni değiştir · boş yerden kutu çiz = çoklu seçim · oklar = kaydır · Delete = sil",
         "degistir": "Beyazla + yaz: kutu çizin; alan beyazla kapatılıp yerine yeni yazı yazılır (taranmış belgeler için).",
         "karart": "Karart: KALICI silinecek alanı çizin (yazı, resim, not, form alanı — geri getirilemez).",
         "form": "Form alanı: yeni alanın kutusunu çizin."}
DAMGALAR = ["ÖDENDİ", "ONAYLANDI", "REDDEDİLDİ", "GİZLİDİR", "TASLAK", "ASLI GİBİDİR", "KOPYADIR"]
HIZALAR = {"Sola": 0, "Ortala": 1, "Sağa": 2, "İki yana": 3}
NOKTA_ARACLARI = {"yazi", "not", "sec", "duzenle"}  # tek tıklama yeterli


def son_acilanlar():
    try:
        with open(SON_YOLU, encoding="utf-8") as f:
            return [y for y in json.load(f) if os.path.exists(y)]
    except (OSError, ValueError):
        return []


def son_acilana_ekle(yol):
    liste = [yol] + [y for y in son_acilanlar() if os.path.normcase(y) != os.path.normcase(yol)]
    try:
        os.makedirs(AYAR_KLASORU, exist_ok=True)
        with open(SON_YOLU, "w", encoding="utf-8") as f:
            json.dump(liste[:10], f, ensure_ascii=False)
    except OSError:
        pass  # liste kaydedilemezse program yine çalışır


class Uygulama:
    def __init__(self, ilk_dosya=None):
        try:
            from tkinterdnd2 import TkinterDnD, DND_FILES
            self.pen = TkinterDnD.Tk()
            self.pen.drop_target_register(DND_FILES)
            self.pen.dnd_bind("<<Drop>>", lambda e: self.ac(self.pen.tk.splitlist(e.data)[0]))
        except Exception:  # kütüphane yoksa sürükle-bırak olmadan çalışır
            self.pen = tk.Tk()
        tema.uygula(self.pen)  # bileşenlerden önce: varsayılan renkler hepsine geçsin
        self.pen.title(tema.AD)
        self.pen.geometry("1280x880")
        self.doc = self.yol = self.sifre = None
        self.sayfa, self.zoom, self.img = 0, 1.3, None
        self.degisti, self.mod, self.bas, self.kutu = False, None, None, None
        self.gecmis, self.ileri = [], []
        self.bulunan, self.bul_i, self.bul_metni = [], -1, ""
        self.kucukler, self.kucuk_y, self.kucuk_is, self.kucuk_surukle = [], [], None, None
        self.secili_resim = None  # Düzenle aracında seçili resim: {xref, bbox}
        self.renk = (0.85, 0, 0)
        self.karartma_onayli = False
        self.kalem_noktalari = []
        self.secili, self.tasima, self.olcekleme = [], None, None  # Yazıyı düzenle: seçim, taşıma, büyütme
        self.boyut = tk.IntVar(value=11)
        self.hiza = tk.StringVar(value="Sola")
        self.sayfa_yazi = tk.StringVar()
        self.arama = tk.StringVar()
        self.arayuzu_kur()
        self.bilgi("PDF açmak için 📂 Aç (Ctrl+O) ya da dosyayı pencereye sürükleyin. "
                   "Sayfa: PageUp/PageDown. Yakınlaştır: Ctrl + fare tekerleği.")
        if ilk_dosya:
            self.pen.after(100, lambda: self.ac(ilk_dosya))

    # ---------- arayüz ----------
    def arayuzu_kur(self):
        p = self.pen
        menu = tk.Menu(p)
        dosya = tk.Menu(menu, tearoff=0)
        dosya.add_command(label="Aç…", accelerator="Ctrl+O", command=self.ac)
        self.son_menu = tk.Menu(dosya, tearoff=0, postcommand=self.son_menuyu_doldur)
        dosya.add_cascade(label="Son açılanlar", menu=self.son_menu)
        dosya.add_separator()
        dosya.add_command(label="Kaydet (üstüne)", command=self.kaydet)
        dosya.add_command(label="Farklı kaydet…", accelerator="Ctrl+S", command=self.farkli_kaydet)
        dosya.add_command(label="Yazdır…", accelerator="Ctrl+P", command=self.yazdir_penceresi)
        dosya.add_separator()
        dosya.add_command(label="Birleştir…", command=self.birlestir_penceresi)
        dosya.add_command(label="Böl…", command=self.bol_penceresi)
        self.donustur_menu = tk.Menu(dosya, tearoff=0)
        self.donustur_menu.add_command(label="Word'e (.docx)…", command=lambda: self.disa_aktar("word"))
        self.donustur_menu.add_command(label="PowerPoint'e (.pptx)…", command=lambda: self.disa_aktar("powerpoint"))
        dosya.add_cascade(label="Dönüştür", menu=self.donustur_menu)
        dosya.add_separator()
        dosya.add_command(label="Çıkış", command=self.kapat)
        menu.add_cascade(label="Dosya", menu=dosya)
        duzen = tk.Menu(menu, tearoff=0)
        duzen.add_command(label="Geri al", accelerator="Ctrl+Z", command=self.geri_al)
        duzen.add_command(label="İleri al", accelerator="Ctrl+Y", command=self.ileri_al)
        duzen.add_separator()
        duzen.add_command(label="Kopyala", accelerator="Ctrl+C", command=self.kopyala)
        duzen.add_command(label="Yapıştır", accelerator="Ctrl+V", command=self.yapistir)
        duzen.add_separator()
        duzen.add_command(label="Bul", accelerator="Ctrl+F", command=lambda: self.arama_kutusu.focus_set())
        duzen.add_command(label="Sonrakini bul", accelerator="F3", command=lambda: self.bul(1))
        menu.add_cascade(label="Düzen", menu=duzen)
        form = tk.Menu(menu, tearoff=0)
        form.add_command(label="Formu doldur…", command=self.form_penceresi)
        form.add_command(label="Yeni form alanı ekle", command=lambda: self.mod_sec("form"))
        menu.add_cascade(label="Form", menu=form)
        guv = tk.Menu(menu, tearoff=0)
        guv.add_command(label="Alan karart (kalıcı sil)", command=lambda: self.mod_sec("karart"))
        guv.add_command(label="Aranan yazıyı her yerde karart…", command=self.bulunanlari_karart)
        menu.add_cascade(label="Güvenlik", menu=guv)
        yardim = tk.Menu(menu, tearoff=0)
        yardim.add_command(label="Güncellemeleri denetle", command=self.guncelle)
        yardim.add_command(label=f"Sürüm {guncelleme.yerel_surum()}", state="disabled")
        menu.add_cascade(label="Yardım", menu=yardim)
        p.config(menu=menu)

        ust = tk.Frame(p, padx=8, pady=6, bg=tema.ZEMIN)
        ust.pack(fill="x")
        self.durum = tk.Label(p, anchor="w", padx=8, pady=3, fg=tema.YAZI2, bg=tema.ZEMIN)
        self.durum.pack(fill="x", side="bottom")

        def dugme(simge_adi, yazi, komut):
            b = tema.dugme(ust, simge_adi, yazi, komut, sol=False)
            b.pack(side="left", padx=2)
            return b

        def bosluk(en=10):
            tk.Frame(ust, width=en, bg=tema.ZEMIN).pack(side="left")

        # marka: IPTV'deki BrandMark gibi logo + ad
        self.marka = ImageTk.PhotoImage(tema.logo(28))
        tk.Label(ust, image=self.marka, bg=tema.ZEMIN).pack(side="left")
        tk.Label(ust, text=" " + tema.AD, font=("Segoe UI Semibold", 13), fg=tema.YAZI, bg=tema.ZEMIN).pack(side="left")
        bosluk(18)
        dugme("ac", "Aç", self.ac)
        dugme("kaydet", "Farklı kaydet", self.farkli_kaydet)
        dugme("yazdir", "Yazdır", self.yazdir_penceresi)
        dugme("geri", "", self.geri_al)
        dugme("ileri", "", self.ileri_al)
        bosluk()
        dugme("onceki", "", lambda: self.git(self.sayfa - 1))
        tk.Label(ust, textvariable=self.sayfa_yazi, width=8, bg=tema.ZEMIN, fg=tema.YAZI).pack(side="left")
        dugme("sonraki", "", lambda: self.git(self.sayfa + 1))
        dugme("uzaklas", "", lambda: self.yakinlas(1 / 1.2))
        dugme("yakinlas", "", lambda: self.yakinlas(1.2))
        dugme("tam_ekran", "", self.tam_ekran)
        bosluk()
        dugme("dondur", "Döndür", self.dondur)
        dugme("sil", "Sil", self.sil)
        dugme("pdf_ekle", "PDF ekle", self.birlestir)
        dugme("bol", "Böl", self.bol_penceresi)
        dugme("birlestir", "Birleştir", self.birlestir_penceresi)
        d = dugme("donustur", "Dönüştür", None)
        d.config(command=lambda: self.donustur_menu.tk_popup(d.winfo_rootx(), d.winfo_rooty() + d.winfo_height()))
        dugme("guncelle", "Güncelle", self.guncelle)
        bosluk()
        arama = tk.Frame(ust, bg=tema.YUZEY2, padx=6)
        arama.pack(side="left", fill="y", padx=2)
        tk.Label(arama, image=tema.simge("ara", 16) or "", text="" if tema.simge("ara") else "Ara", bg=tema.YUZEY2
                 ).pack(side="left")
        self.arama_kutusu = tk.Entry(arama, textvariable=self.arama, width=20, bg=tema.YUZEY2, bd=0)
        self.arama_kutusu.pack(side="left", padx=4, ipady=3)
        self.arama_kutusu.bind("<Return>", lambda e: self.bul(1))
        self.arama_kutusu.bind("<Shift-Return>", lambda e: self.bul(-1))
        dugme("yukari", "", lambda: self.bul(-1))
        dugme("asagi", "", lambda: self.bul(1))

        govde = tk.PanedWindow(p, orient="horizontal", sashwidth=4, bg=tema.ZEMIN, bd=0)
        govde.pack(fill="both", expand=True)
        # sol: küçük resimler
        sol = tk.Frame(govde)
        self.kucuk_tuval = tk.Canvas(sol, bg=tema.YUZEY, width=KUCUK_EN + 30, highlightthickness=0)
        ks = tk.Scrollbar(sol, orient="vertical", command=self.kucuk_tuval.yview)
        self.kucuk_tuval.configure(yscrollcommand=ks.set)
        ks.pack(side="right", fill="y")
        self.kucuk_tuval.pack(fill="both", expand=True)
        govde.add(sol, minsize=120)
        # sağ: sayfa
        sag = tk.Frame(govde)
        self.tuval = tk.Canvas(sag, bg=tema.ZEMIN, highlightthickness=0, cursor="xterm")
        dik = tk.Scrollbar(sag, orient="vertical", command=self.tuval.yview)
        yat = tk.Scrollbar(sag, orient="horizontal", command=self.tuval.xview)
        self.tuval.configure(yscrollcommand=dik.set, xscrollcommand=yat.set)
        dik.pack(side="right", fill="y")
        yat.pack(side="bottom", fill="x")
        self.tuval.pack(fill="both", expand=True)
        govde.add(sag, stretch="always")
        panel = self.panel_kur(govde)
        govde.add(panel, minsize=200, stretch="never")
        # tam ekranda gizlenecekler: (bileşen, geri getirme)
        self.tam = False
        self.gizlenenler = [(ust, lambda: ust.pack(fill="x", before=govde)),
                            (self.durum, lambda: self.durum.pack(fill="x", side="bottom", before=govde)),
                            (dik, lambda: dik.pack(side="right", fill="y", before=yat)),  # köşe eskisi gibi kalsın
                            (yat, lambda: yat.pack(side="bottom", fill="x", before=self.tuval)),
                            (sol, lambda: govde.add(sol, before=sag, minsize=120)),
                            (panel, lambda: govde.add(panel, after=sag, minsize=200, stretch="never"))]
        self.menu, self.govde, self.tekerlek, self.son_gecis = menu, govde, 0, 0

        t, k = self.tuval, self.kucuk_tuval
        t.bind("<ButtonPress-1>", self.bas_)
        t.bind("<B1-Motion>", self.surukle_)
        t.bind("<ButtonRelease-1>", self.birak_)
        t.bind("<Motion>", self.uzerinde)
        t.bind("<Double-Button-1>", self.duzenle_cift)
        t.bind("<Configure>", self.ortala)  # pencere büyüyünce / tam ekranda yeniden ortala
        t.bind("<MouseWheel>", self.tekerlek_)
        t.bind("<Control-MouseWheel>", lambda e: self.yakinlas(1.1 if e.delta > 0 else 1 / 1.1))
        k.bind("<MouseWheel>", lambda e: k.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        k.bind("<ButtonPress-1>", self.kucuk_bas)
        k.bind("<B1-Motion>", self.kucuk_surukle_)
        k.bind("<ButtonRelease-1>", self.kucuk_birak)
        for tus, f in {"<Next>": lambda e: self.git(self.sayfa + 1), "<Prior>": lambda e: self.git(self.sayfa - 1),
                       "<Control-o>": lambda e: self.ac(), "<Control-s>": lambda e: self.farkli_kaydet(),
                       "<Control-z>": lambda e: self.geri_al(), "<Control-y>": lambda e: self.ileri_al(),
                       "<Control-c>": lambda e: self.kopyala(), "<Control-v>": lambda e: self.yapistir(),
                       "<Control-p>": lambda e: self.yazdir_penceresi(),
                       "<Control-f>": lambda e: (self.tam and self.tam_ekran(), self.arama_kutusu.focus_set()),
                       "<F3>": lambda e: self.bul(1),
                       "<Control-plus>": lambda e: self.yakinlas(1.2), "<Control-minus>": lambda e: self.yakinlas(1 / 1.2),
                       "<Delete>": lambda e: self.secilileri_sil(), "<Return>": lambda e: self.enter_tusu(),
                       "<Left>": lambda e: self.ok_tusu(-1, 0, e), "<Right>": lambda e: self.ok_tusu(1, 0, e),
                       "<Up>": lambda e: self.ok_tusu(0, -1, e), "<Down>": lambda e: self.ok_tusu(0, 1, e),
                       "<F11>": lambda e: self.tam_ekran(),
                       "<Escape>": lambda e: self.tam_ekran() if self.tam else
                       self.secimi_birak() if self.secili else self.mod and self.mod_sec(self.mod)
                       }.items():
            p.bind(tus, f)
        p.protocol("WM_DELETE_WINDOW", self.kapat)

    def panel_kur(self, ana):
        """Sağdaki araç paneli: gruplu araçlar, biçim ayarları, seçili yazının bilgisi."""
        ARKA = tema.YUZEY
        panel = tk.Frame(ana, bg=ARKA, padx=8, pady=8)
        self.mod_dugmeleri = {}

        def bolum(baslik):
            tk.Label(panel, text=baslik.upper(), bg=ARKA, fg=tema.VURGU_ACIK, font=("Segoe UI Semibold", 9),
                     anchor="w").pack(fill="x", pady=(6, 3))
            g = tk.Frame(panel, bg=ARKA)
            g.pack(fill="x")
            return g

        def grup(baslik, araclar, sutun=2):
            g = bolum(baslik)
            for i, (ad, simge_adi, yazi) in enumerate(araclar):
                komut = ad if callable(ad) else (lambda ad=ad: self.mod_sec(ad))
                b = tema.dugme(g, simge_adi, yazi, komut)
                b.grid(row=i // sutun, column=i % sutun, sticky="ew", padx=2, pady=2)
                if not callable(ad):
                    self.mod_dugmeleri[ad] = b
            for c in range(sutun):
                g.columnconfigure(c, weight=1, uniform="sutun")

        grup("Yazıyı düzenle", [("duzenle", "duzenle", "Yazıyı düzenle"), ("yazi", "yazi", "Yazı ekle"),
                                ("degistir", "degistir", "Beyazla + yaz")], 1)
        grup("Yorum ve işaret", [("sec", "sec", "Seç"), ("not", "not", "Not"), ("vurgu", "vurgu", "Vurgula"),
                                 ("alti", "alti", "Altını çiz"), ("ustu", "ustu", "Üstünü çiz"),
                                 ("kalem", "kalem", "Kalem"), ("dikdortgen", "dikdortgen", "Dikdörtgen"),
                                 ("daire", "daire", "Daire"), ("cizgi", "cizgi", "Çizgi"), ("ok", "ok", "Ok")])
        grup("Belge", [("damga", "damga", "Damga"), ("resim", "resim", "Resim / İmza"), ("form", "form", "Form alanı"),
                       (self.form_penceresi, "doldur", "Formu doldur"), ("karart", "karart", "Karart"),
                       (self.bulunanlari_karart, "her_yerde", "Her yerde")])

        b = bolum("Biçim")
        tk.Label(b, text="Renk", bg=ARKA, fg=tema.YAZI2).grid(row=0, column=0, sticky="w", pady=3)
        self.renk_dugmesi = tk.Button(b, width=6, bg="#d90000", activebackground="#d90000", relief="flat",
                                      cursor="hand2", command=self.renk_sec)
        self.renk_dugmesi.grid(row=0, column=1, sticky="w", pady=3)
        tk.Label(b, text="Yazı boyutu", bg=ARKA, fg=tema.YAZI2).grid(row=1, column=0, sticky="w", pady=3)
        tk.Spinbox(b, from_=6, to=48, width=5, textvariable=self.boyut, bd=0).grid(row=1, column=1, sticky="w")
        tk.Label(b, text="Hizalama", bg=ARKA, fg=tema.YAZI2).grid(row=2, column=0, sticky="w", pady=3)
        hiza = tk.OptionMenu(b, self.hiza, *HIZALAR)
        hiza.config(bg=tema.YUZEY2, activebackground=tema.USTUNDE, relief="flat", bd=0, highlightthickness=0,
                    cursor="hand2")
        hiza["menu"].config(bg=tema.YUZEY2, fg=tema.YAZI, activebackground=tema.VURGU2, bd=0)
        hiza.grid(row=2, column=1, sticky="w")
        b.columnconfigure(0, minsize=90)

        s = bolum("Seçili")
        self.secim_etiketi = tk.Label(s, text="—", bg=ARKA, fg=tema.YAZI2, justify="left", anchor="w",
                                      wraplength=190)
        self.secim_etiketi.pack(fill="x")
        self.secim_rengi = tk.Label(s, text="      ", bg=ARKA)
        self.secim_rengi.pack(anchor="w", pady=(2, 0))
        self.temizle_dugmesi = tema.dugme(s, "resim", "Arka planı temizle", lambda: self.resim_arka_plani())
        return panel

    def secim_bilgisi(self):
        """Paneldeki 'Seçili' kutusunu günceller (yazı ya da resim)."""
        self.temizle_dugmesi.pack_forget()
        if self.secili_resim and self.doc:
            r, b = self.secili_resim, self.secili_resim["bbox"]
            bilgi = next((i for i in self.doc[self.sayfa].get_image_info(xrefs=True) if i["xref"] == r["xref"]), {})
            self.secim_etiketi.config(text=f"Resim\n{bilgi.get('width', '?')} × {bilgi.get('height', '?')} piksel\n"
                                           f"Sayfada: {b.width / 72 * 2.54:.1f} × {b.height / 72 * 2.54:.1f} cm")
            self.secim_rengi.config(bg=self.secim_etiketi.cget("bg"))
            return self.temizle_dugmesi.pack(fill="x", pady=(6, 0))
        if not self.secili:
            self.secim_etiketi.config(text="—")
            return self.secim_rengi.config(bg=self.secim_etiketi.cget("bg"))
        sp = self.secili[0]["spans"][0]
        boyutlar = sorted({round(p["size"], 1) for l in self.secili for p in l["spans"]})
        yazi_tipi = sp["font"].split("+")[-1]  # gömülü alt kümelerin "ABCDEF+" önekini at
        kalin = "kalın" if sp["flags"] & 16 else "normal"
        renk = "#%06x" % sp["color"]
        metin = pi.satir_metni(self.secili[0]).replace("\xa0", " ").strip()
        self.secim_etiketi.config(text=(f"{len(self.secili)} satır\n" if len(self.secili) > 1 else "")
                                  + f"“{metin[:40]}{'…' if len(metin) > 40 else ''}”\n"
                                  f"Yazı tipi: {yazi_tipi} ({kalin})\n"
                                  f"Boyut: {', '.join(f'{v:g}' for v in boyutlar)} pt\nRenk: {renk}")
        self.secim_rengi.config(bg=renk)

    def bilgi(self, m):
        self.durum.config(text=m)

    def belge_var(self):
        if not self.doc:
            self.bilgi("Önce bir PDF açın.")
        return bool(self.doc)

    # ---------- çizim ----------
    def ciz(self):
        t = self.tuval
        t.delete("all")
        if not self.doc:
            self.sayfa_yazi.set("")
            return
        self.sayfa = max(0, min(self.sayfa, self.doc.page_count - 1))
        s = self.doc[self.sayfa]
        pix = s.get_pixmap(matrix=pymupdf.Matrix(self.zoom, self.zoom), annots=True)
        self.img = tk.PhotoImage(data=pix.tobytes("ppm"))  # referans tutulmazsa resim kaybolur
        t.create_image(KENAR, KENAR, image=self.img, anchor="nw")
        self.ortala()
        for n, (i, r) in enumerate(self.bulunan):  # arama sonuçları (PDF'e yazılmaz, sadece ekranda)
            if i == self.sayfa:
                g = pi.gorunume(s, r)
                t.create_rectangle(*[KENAR + v * self.zoom for v in g], width=2,
                                   outline="#ff6a00" if n == self.bul_i else "#e6b800")
        self.secim_ciz()
        self.sayfa_yazi.set(f"{self.sayfa + 1} / {self.doc.page_count}")
        ad = os.path.basename(self.yol) if self.yol else ""
        self.pen.title(f"{'● ' if self.degisti else ''}{ad} — {tema.AD}")
        self.kucuk_secimi()

    def ortala(self, _=None):
        """Pencere sayfadan genişse sayfa ortada dursun. Sayfa resmi hep (KENAR, KENAR)'da; ortalama, kaydırma
        alanını sola doğru genişleterek yapılır, böylece tıklama/koordinat hesapları değişmez."""
        if not self.img:
            return
        icerik_en, icerik_boy = self.img.width() + 2 * KENAR, self.img.height() + 2 * KENAR
        en = max(self.tuval.winfo_width(), icerik_en)
        x0 = -(en - icerik_en) / 2
        self.tuval.configure(scrollregion=(x0, 0, x0 + en, icerik_boy))
        if en > icerik_en:
            self.tuval.xview_moveto(0)

    def kucukleri_ciz(self):
        """Küçük resimleri parça parça çizer; büyük belgede pencere donmasın."""
        if self.kucuk_is:
            self.pen.after_cancel(self.kucuk_is)
        k = self.kucuk_tuval
        k.delete("all")
        self.kucukler, self.kucuk_y = [], []
        if not self.doc:
            return
        y = [8]

        def parca(i):
            for i in range(i, min(i + 8, self.doc.page_count)):
                s = self.doc[i]
                o = KUCUK_EN / s.rect.width
                pix = s.get_pixmap(matrix=pymupdf.Matrix(o, o), annots=True)
                im = tk.PhotoImage(data=pix.tobytes("ppm"))
                self.kucukler.append(im)
                self.kucuk_y.append(y[0])
                k.create_image(15, y[0], image=im, anchor="nw", tags=(f"k{i}",))
                k.create_text(15 + KUCUK_EN / 2, y[0] + pix.height + 9, text=str(i + 1), fill="white")
                y[0] += pix.height + 26
            k.configure(scrollregion=(0, 0, KUCUK_EN + 30, y[0]))
            self.kucuk_secimi()
            if i + 1 < self.doc.page_count:
                self.kucuk_is = self.pen.after(1, parca, i + 1)
            else:
                self.kucuk_is = None

        parca(0)

    def kucuk_secimi(self):
        k = self.kucuk_tuval
        k.delete("secim")
        if self.sayfa < len(self.kucuk_y):
            x0, y0, x1, y1 = k.bbox(f"k{self.sayfa}")
            k.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline=tema.VURGU, width=3, tags=("secim",))
            gy0, gy1 = k.yview()
            toplam = float(k.cget("scrollregion").split()[3])
            if not (gy0 * toplam <= y0 and y1 <= gy1 * toplam):  # seçili sayfa görünmüyorsa kaydır
                k.yview_moveto(max(0, (y0 - 20) / toplam))

    def kucuk_no(self, e):
        y = self.kucuk_tuval.canvasy(e.y)
        return max(0, min(bisect.bisect_right(self.kucuk_y, y) - 1, self.doc.page_count - 1))

    def kucuk_bas(self, e):
        if self.doc and self.kucuk_y:
            self.kucuk_surukle = self.kucuk_no(e)

    def kucuk_surukle_(self, e):
        if self.kucuk_surukle is None:
            return
        k = self.kucuk_tuval
        k.delete("hedef")
        j = self.kucuk_no(e)
        if j != self.kucuk_surukle and j < len(self.kucuk_y):
            y = self.kucuk_y[j] - 5 if j < self.kucuk_surukle else k.bbox(f"k{j}")[3] + 5
            k.create_line(5, y, KUCUK_EN + 25, y, fill=tema.VURGU, width=4, tags=("hedef",))
            self.bilgi(f"{self.kucuk_surukle + 1}. sayfa {j + 1}. sıraya taşınacak — bırakın.")

    def kucuk_birak(self, e):
        if self.kucuk_surukle is None:
            return
        i, j = self.kucuk_surukle, self.kucuk_no(e)
        self.kucuk_surukle = None
        self.kucuk_tuval.delete("hedef")
        if i == j:
            self.git(i)
        else:
            self.degisiklik(lambda: setattr(self, "sayfa", pi.konuma_tasi(self.doc, i, j)), sayfalar=True)
            self.bilgi(f"{i + 1}. sayfa {j + 1}. sıraya taşındı.")

    # ---------- değişiklik, geri al ----------
    def degisiklik(self, islem, sayfalar=False):
        """Belgeyi değiştiren her işlem buradan geçer: önce geri al için kopya alınır."""
        once = pi.anlik_goruntu(self.doc)
        try:
            islem()
        except Exception as e:
            self.geri_yukle(once)  # yarım kalan işlem belgeyi bozmasın
            messagebox.showerror("Hata", str(e))
            return False
        self.gecmis.append(once)
        while len(self.gecmis) > 1 and sum(map(len, self.gecmis)) > GECMIS_SINIRI:
            self.gecmis.pop(0)
        self.ileri.clear()
        self.degisti = True
        self.bulunan = []  # sayfalar değişmiş olabilir; eski arama sonuçları yanlış yeri gösterir
        self.ciz()
        if sayfalar:
            self.kucukleri_ciz()
        else:
            self.kucuk_yenile(self.sayfa)
        return True

    def kucuk_yenile(self, i):
        if i >= len(self.kucuk_y) or self.kucuk_is:  # henüz çizilmemiş: baştan çiz
            return self.kucukleri_ciz()
        s = self.doc[i]
        o = KUCUK_EN / s.rect.width
        im = tk.PhotoImage(data=s.get_pixmap(matrix=pymupdf.Matrix(o, o), annots=True).tobytes("ppm"))
        if (im.height(), im.width()) != (self.kucukler[i].height(), self.kucukler[i].width()):
            return self.kucukleri_ciz()  # boyutu değişti (döndürme): hepsini yeniden diz
        self.kucukler[i] = im
        self.kucuk_tuval.itemconfigure(f"k{i}", image=im)

    def geri_yukle(self, veri):
        self.secili, self.secili_resim = [], None  # eski belgenin seçimi, yeni belgede yanlış yeri gösterir
        eski = self.doc
        self.doc = pi.goruntuden_ac(veri, self.sifre)
        eski.close()

    def geri_al(self):
        if not self.belge_var():
            return
        if not self.gecmis:
            return self.bilgi("Geri alınacak bir şey yok.")
        self.ileri.append(pi.anlik_goruntu(self.doc))
        self.geri_yukle(self.gecmis.pop())
        self.degisti, self.bulunan = True, []
        self.ciz()
        self.kucukleri_ciz()
        self.bilgi(f"Geri alındı. ({len(self.gecmis)} adım daha geri alınabilir)")

    def ileri_al(self):
        if not self.belge_var():
            return
        if not self.ileri:
            return self.bilgi("İleri alınacak bir şey yok.")
        self.gecmis.append(pi.anlik_goruntu(self.doc))
        self.geri_yukle(self.ileri.pop())
        self.degisti, self.bulunan = True, []
        self.ciz()
        self.kucukleri_ciz()
        self.bilgi("İleri alındı.")

    # ---------- dosya ----------
    def kaydedilsin_mi(self):
        """Kaydedilmemiş değişiklik varsa sorar. Devam edilebilirse True."""
        if not self.degisti:
            return True
        c = messagebox.askyesnocancel("Kaydedilmemiş değişiklik", "Değişiklikler kaydedilsin mi?")
        if c is None:
            return False
        return self.farkli_kaydet() if c else True

    def ac(self, yol=None):
        if not self.kaydedilsin_mi():
            return
        yol = yol or filedialog.askopenfilename(filetypes=[("PDF", "*.pdf"), ("Tümü", "*.*")])
        if not yol:
            return
        try:
            doc = pymupdf.open(yol)
        except Exception as e:
            return messagebox.showerror("Açılamadı", str(e))
        sifre = None
        if doc.needs_pass:
            sifre = simpledialog.askstring("Şifre", "Bu PDF şifreli. Şifreyi girin:", show="*", parent=self.pen)
            if not sifre or not doc.authenticate(sifre):
                doc.close()
                return messagebox.showerror("Açılamadı", "Şifre yanlış.")
        if self.doc:
            self.doc.close()
        self.doc, self.yol, self.sifre, self.sayfa, self.degisti = doc, yol, sifre, 0, False
        self.gecmis, self.ileri, self.bulunan = [], [], []
        son_acilana_ekle(yol)
        self.ciz()
        self.kucukleri_ciz()
        self.bilgi(f"Açıldı: {yol}")

    def son_menuyu_doldur(self):
        self.son_menu.delete(0, "end")
        liste = son_acilanlar()
        for y in liste:
            self.son_menu.add_command(label=y, command=lambda y=y: self.ac(y))
        if not liste:
            self.son_menu.add_command(label="(boş)", state="disabled")

    def kaydet_yola(self, yol):
        try:
            self.doc = pi.kaydet_ve_ac(self.doc, yol, self.sifre)
        except Exception as e:
            messagebox.showerror("Kaydedilemedi", f"{e}\n\nDosya değiştirilmedi.")
            return False
        self.yol, self.degisti = yol, False
        son_acilana_ekle(yol)
        self.ciz()
        self.bilgi(f"Kaydedildi: {yol}")
        return True

    def kaydet(self):
        if not self.belge_var():
            return False
        if not messagebox.askyesno("Üstüne kaydet", f"Asıl dosyanın üstüne yazılacak:\n{self.yol}\n\nEmin misiniz?"):
            return False
        return self.kaydet_yola(self.yol)

    def farkli_kaydet(self):
        if not self.belge_var():
            return False
        ad = os.path.splitext(os.path.basename(self.yol))[0] + "_duzenlendi.pdf"
        yol = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=ad,
                                           initialdir=os.path.dirname(self.yol), filetypes=[("PDF", "*.pdf")])
        return self.kaydet_yola(yol) if yol else False

    def guncelle(self):
        """GitHub'da yeni sürüm varsa kurulumunu indirir, uygulamayı kapatır; kurulum bitince uygulama yeniden açılır."""
        self.bilgi("Güncelleme denetleniyor…")
        self.pen.config(cursor="watch")
        self.pen.update()
        try:
            yeni, uzak, url = guncelleme.yeni_var_mi()
            self.bilgi("")
            if not yeni:
                return messagebox.showinfo("Güncelle", f"Polat PDF güncel (sürüm {guncelleme.yerel_surum()}).")
            if not url:
                return messagebox.showinfo("Güncelle", f"Sürüm {uzak} yayımlanmış ama kurulum dosyası henüz "
                                           "yüklenmemiş. Biraz sonra yeniden deneyin.")
            if not getattr(sys, "frozen", False):
                return messagebox.showinfo("Güncelle", f"Yeni sürüm var: {uzak}. Kaynak koddan çalışıyorsunuz; "
                                           "kurulu Polat PDF'i güncelleyin ya da git pull yapın.")
            if guncelleme.acik_pencere_sayisi() > 1:  # kurulum diğer pencereleri zorla kapatır, kaydedilmemiş iş gider
                return messagebox.showwarning("Güncelle", "Başka Polat PDF pencereleri açık. Önce onları kaydedip "
                                              "kapatın, sonra yeniden Güncelle'ye basın.")
            if not (messagebox.askyesno("Güncelle", f"Yeni sürüm var: {uzak}\n(şu an {guncelleme.yerel_surum()})\n\n"
                                        "Kurulsun mu? Polat PDF kapanıp yeniden açılacak.") and self.kaydedilsin_mi()):
                return self.bilgi("")
            self.bilgi("Güncelleme indiriliyor…")
            self.pen.update()
            guncelleme.kurulumu_baslat(url)
        except Exception as e:
            self.bilgi("Güncellenemedi.")
            return messagebox.showerror("Güncellenemedi", f"İnternet bağlantısını denetleyin.\n\n{e}")
        finally:
            self.pen.config(cursor="")
        self.pen.destroy()  # kurulum dosyaları değiştirebilsin

    def kapat(self):
        if self.kaydedilsin_mi():
            self.pen.destroy()

    # ---------- gezinme, arama ----------
    def tam_ekran(self):
        """F11 / Esc: menü, araç çubuğu, yan paneller ve kaydırma çubukları gizlenir; yalnızca sayfa kalır."""
        self.tam = not self.tam
        if self.tam:  # kullanıcının ayarladığı yan panel genişlikleri
            self.genislikler = {w: w.winfo_width() for w, _ in self.gizlenenler if w.winfo_manager() == "panedwindow"}
        self.pen.attributes("-fullscreen", self.tam)
        self.pen.config(menu="" if self.tam else self.menu)
        for w, geri in (self.gizlenenler if self.tam else reversed(self.gizlenenler)):
            if not self.tam:
                geri()
            elif w.winfo_manager() == "panedwindow":
                w.master.forget(w)
            else:
                w.pack_forget()
        if not self.tam:
            for w, en in self.genislikler.items():
                self.govde.paneconfigure(w, width=en)
        self.tuval.focus_set()

    def tekerlek_(self, e):
        """Touchpad küçük adımlar gönderir: 120'ye (bir tık) ulaşana kadar biriktir."""
        self.tekerlek += e.delta
        n = int(self.tekerlek / 120)
        if n:
            self.tekerlek -= n * 120
            self.kaydir(-n)

    def kaydir(self, adim):
        """Aşağı/yukarı kaydırır; sayfanın sonuna (başına) gelince sonraki (önceki) sayfaya geçer."""
        if not self.doc:
            return
        t = self.tuval
        ust, alt = t.yview()
        sinirda = (adim > 0 and alt >= 1 and self.sayfa < self.doc.page_count - 1) or \
                  (adim < 0 and ust <= 0 and self.sayfa > 0)
        if sinirda:
            if time.monotonic() - self.son_gecis < 0.3:  # hızlı kaydırmada sayfalar art arda atlanmasın
                return
            self.son_gecis = time.monotonic()
            self.git(self.sayfa + (1 if adim > 0 else -1))
            t.yview_moveto(0 if adim > 0 else 1)
        else:
            t.yview_scroll(adim, "units")

    def git(self, n):
        if self.belge_var():
            if n != self.sayfa:
                self.secili, self.secili_resim, self.secili_metin = [], None, ""
            self.sayfa = n
            self.ciz()

    def yakinlas(self, k):
        self.zoom = max(0.3, min(5, self.zoom * k))
        self.ciz()

    def bul(self, yon):
        if not self.belge_var():
            return
        metin = self.arama.get().strip()
        if not metin:
            return self.arama_kutusu.focus_set()
        if metin != self.bul_metni or not self.bulunan:
            self.bul_metni, self.bulunan, self.bul_i = metin, pi.ara(self.doc, metin), -1
            if not self.bulunan:
                self.ciz()
                return self.bilgi(f"“{metin}” bulunamadı.")
            # bulunduğumuz sayfadan başla
            self.bul_i = next((n - 1 for n, (i, _) in enumerate(self.bulunan) if i >= self.sayfa), -1)
            if yon < 0:
                self.bul_i += 1
        self.bul_i = (self.bul_i + yon) % len(self.bulunan)
        i, r = self.bulunan[self.bul_i]
        self.sayfa = i
        self.ciz()
        g = pi.gorunume(self.doc[i], r)  # bulunan yeri ekrana getir
        toplam = float(self.tuval.cget("scrollregion").split()[3])
        self.tuval.yview_moveto(max(0, (KENAR + g.y0 * self.zoom - 150) / toplam))
        self.bilgi(f"“{metin}”: {self.bul_i + 1} / {len(self.bulunan)} (sayfa {i + 1}). Sonraki: Enter / F3")

    # ---------- sayfa işlemleri ----------
    def dondur(self):
        if self.belge_var():
            s = self.doc[self.sayfa]
            self.degisiklik(lambda: s.set_rotation((s.rotation + 90) % 360))

    def sil(self):
        if not self.belge_var():
            return
        if self.doc.page_count == 1:
            return self.bilgi("Tek sayfa var, silinemez.")
        if messagebox.askyesno("Sayfa sil", f"{self.sayfa + 1}. sayfa silinsin mi?"):
            self.degisiklik(lambda: self.doc.delete_page(self.sayfa), sayfalar=True)

    def birlestir(self):
        if not self.belge_var():
            return
        yol = filedialog.askopenfilename(title="Araya eklenecek PDF", filetypes=[("PDF", "*.pdf")])
        if not yol:
            return
        try:
            diger = pymupdf.open(yol)
        except Exception as e:
            return messagebox.showerror("Eklenemedi", str(e))
        with diger:
            if diger.needs_pass:
                return messagebox.showerror("Eklenemedi", "Şifreli PDF araya eklenemez.")
            n = diger.page_count
            if self.degisiklik(lambda: self.doc.insert_pdf(diger, start_at=self.sayfa + 1), sayfalar=True):
                self.bilgi(f"{n} sayfa, {self.sayfa + 1}. sayfadan sonra eklendi.")
                self.git(self.sayfa + 1)

    def pencere(self, baslik):
        w = tk.Toplevel(self.pen, padx=14, pady=12)
        w.title(baslik)
        w.transient(self.pen)
        w.resizable(False, False)
        return w

    def yazdir_penceresi(self):
        """Yazıcı, sayfalar ve kopya sayısı seçilip açık belge (kaydedilmemiş değişiklikleriyle) yazdırılır."""
        if not self.belge_var():
            return
        try:
            adlar, varsayilan = pi.yazicilar()
        except Exception as e:
            return messagebox.showerror("Yazdır", f"Yazıcılar okunamadı.\n\n{e}")
        if not adlar:
            return messagebox.showerror("Yazdır", "Bilgisayarda kurulu yazıcı yok.")
        from tkinter import ttk
        n = self.doc.page_count
        w = self.pencere("Yazdır")
        YONLER = {"Otomatik (sayfaya göre)": 0, "Dikey": 1, "Yatay": 2}
        RENKLER = {"Renkli": 2, "Siyah-beyaz": 1}
        CIFTLER = {"Tek taraf": 1, "Çift taraf — uzun kenardan çevir": 2, "Çift taraf — kısa kenardan çevir": 3}
        yazici, tur = tk.StringVar(value=varsayilan), tk.StringVar(value="tumu")
        aralik, kopya = tk.StringVar(value=f"1-{n}"), tk.IntVar(value=1)
        kagit, yon, renk, cift = tk.StringVar(), tk.StringVar(value="Otomatik (sayfaya göre)"), tk.StringVar(), \
            tk.StringVar()
        sigdir = tk.BooleanVar(value=True)
        oz = {}  # seçili yazıcının devmode'u ve yetenekleri

        def satir(r, yazi, deger, secenekler):
            tk.Label(w, text=yazi).grid(row=r, column=0, sticky="w", pady=3)
            k = ttk.Combobox(w, textvariable=deger, values=secenekler, state="readonly", width=40)
            k.grid(row=r, column=1, columnspan=2, sticky="w")
            return k

        yazici_kutusu = satir(0, "Yazıcı", yazici, adlar)
        kagit_kutusu = satir(1, "Kâğıt", kagit, [])
        satir(2, "Yön", yon, list(YONLER))
        renk_kutusu = satir(3, "Renk", renk, list(RENKLER))
        cift_kutusu = satir(4, "Baskı", cift, list(CIFTLER))
        tk.Checkbutton(w, text="Sayfaya sığdır (kapalıysa gerçek boyut)", variable=sigdir,
                       selectcolor=tema.YUZEY2, activebackground=tema.YUZEY).grid(row=5, column=0, columnspan=3,
                                                                                  sticky="w", pady=(6, 0))
        for i, (deger, yazi) in enumerate([("tumu", f"Bütün sayfalar ({n})"), ("bu", f"Bu sayfa ({self.sayfa + 1})"),
                                           ("aralik", "Sayfalar:")], start=6):
            tk.Radiobutton(w, text=yazi, variable=tur, value=deger, selectcolor=tema.YUZEY2,
                           activebackground=tema.YUZEY).grid(row=i, column=0, columnspan=2, sticky="w")
        tk.Entry(w, textvariable=aralik, width=20).grid(row=8, column=1, sticky="w")
        tk.Label(w, text="Kopya").grid(row=9, column=0, sticky="w", pady=6)
        tk.Spinbox(w, from_=1, to=99, width=5, textvariable=kopya).grid(row=9, column=1, sticky="w")
        alt = tk.Frame(w, pady=10)
        alt.grid(row=10, column=0, columnspan=3, sticky="e")

        def goster():
            """Kutuları seçili yazıcının devmode'una göre doldurur."""
            dm = oz["devmode"]
            kagit.set(next((ad for no, ad in oz["kagitlar"] if no == dm.PaperSize), ""))
            if yon.get() != "Otomatik (sayfaya göre)":
                yon.set("Yatay" if dm.Orientation == 2 else "Dikey")
            renk.set("Siyah-beyaz" if not oz["renkli"] or dm.Color == 1 else "Renkli")
            cift.set(next((ad for ad, no in CIFTLER.items() if no == dm.Duplex), "Tek taraf") if oz["cift_taraf"]
                     else "Tek taraf")
            renk_kutusu.config(state="readonly" if oz["renkli"] else "disabled")
            cift_kutusu.config(state="readonly" if oz["cift_taraf"] else "disabled")

        def yazici_degisti(_=None):
            try:
                oz.update(pi.yazici_ozellikleri(yazici.get()))
            except Exception as e:
                oz.clear()
                return messagebox.showerror("Yazıcı", f"Yazıcı ayarları okunamadı.\n\n{e}", parent=w)
            kagit_kutusu.config(values=[ad for _, ad in oz["kagitlar"]])
            goster()

        def ayarla(pencere=False):
            """Kutulardaki seçimleri devmode'a yazar; pencere=True ise yazıcının kendi ayar penceresini açar."""
            yon_no = YONLER[yon.get()]
            return pi.ayarlari_uygula(
                yazici.get(), oz["devmode"], int(w.frame(), 16), pencere,
                kagit=next((no for no, ad in oz["kagitlar"] if ad == kagit.get()), None),
                yon=yon_no or 1,  # otomatikte kâğıt dik, yatay sayfalar döndürülür
                renk=RENKLER[renk.get()] if oz["renkli"] else None,
                cift=CIFTLER[cift.get()] if oz["cift_taraf"] else None)

        def ozellikler():
            if oz and ayarla(pencere=True):
                if yon.get() == "Otomatik (sayfaya göre)" and oz["devmode"].Orientation == 2:
                    yon.set("Yatay")  # kullanıcı sürücü penceresinde yatay seçtiyse otomatik kalmasın
                goster()

        def tamam():
            if not oz:
                return messagebox.showerror("Yazıcı", "Yazıcı ayarları okunamadı.", parent=w)
            try:
                sayfalar = (range(n) if tur.get() == "tumu" else [self.sayfa] if tur.get() == "bu" else
                            [i for a, b in pi.aralik_coz(aralik.get(), n) for i in range(a, b + 1)])
                adet = max(1, min(99, int(kopya.get())))
            except (ValueError, tk.TclError) as e:
                return messagebox.showerror("Hatalı seçim", str(e), parent=w)
            otomatik = YONLER[yon.get()] == 0
            ayarla()
            w.destroy()
            self.bilgi(f"Yazıcıya gönderiliyor: {yazici.get()}…")
            self.pen.config(cursor="watch")
            self.pen.update()
            ad = os.path.basename(self.yol) if self.yol else tema.AD
            try:
                pi.yazdir(self.doc, yazici.get(), list(sayfalar), adet, ad, devmode=oz["devmode"], dondur=otomatik,
                          sigdir=sigdir.get())
            except Exception as e:
                self.bilgi("Yazdırılamadı.")
                return messagebox.showerror("Yazdırılamadı", str(e))
            finally:
                self.pen.config(cursor="")
            self.bilgi(f"{len(sayfalar)} sayfa × {adet} kopya yazıcıya gönderildi: {yazici.get()} ({kagit.get()})")

        yazici_kutusu.bind("<<ComboboxSelected>>", yazici_degisti)
        yazici_degisti()
        tema.dugme(alt, None, "Yazıcı özellikleri…", ozellikler, sol=False).pack(side="left", padx=(0, 16))
        tema.dugme(alt, "yazdir", "Yazdır", tamam, sol=False).pack(side="left", padx=4)
        tema.dugme(alt, None, "İptal", w.destroy, sol=False).pack(side="left")
        w.bind("<Return>", lambda e: tamam())
        w.grab_set()

    def metin_sec(self, s, rect):
        """Araç seçili değilken çizilen kutudaki kelimeleri işaretler; Ctrl+C ile kopyalanır."""
        self.tuval.delete("metin")
        kelimeler = s.get_text("words", clip=rect, sort=True)  # (x0, y0, x1, y1, kelime, ...)
        # PDF'te aynı satırdaki parçalar ayrı bloklarda olabilir: göründükleri satıra göre, soldan sağa grupla
        satirlar = []
        for k in sorted(kelimeler, key=lambda k: (k[1] + k[3]) / 2):
            orta = (k[1] + k[3]) / 2
            if satirlar and abs(orta - satirlar[-1][0]) < (k[3] - k[1]) / 2:
                satirlar[-1][1].append(k)
            else:
                satirlar.append([orta, [k]])
            self.tuval.create_rectangle(*self.kanvas_kutusu(s, k[:4]), outline=tema.VURGU, tags=("metin",))
        self.secili_metin = "\n".join(" ".join(k[4] for k in sorted(v, key=lambda k: k[0])) for _, v in satirlar)
        self.bilgi(f"{len(kelimeler)} kelime seçildi. Ctrl+C ile kopyalayın." if kelimeler
                   else "Bu alanda seçilebilir yazı yok (taranmış sayfalarda yazı resimdir).")

    def disa_aktar(self, tur):
        """Açık belgeyi (kaydedilmemiş değişiklikleriyle) Word ya da PowerPoint dosyasına çevirir."""
        if not self.belge_var():
            return
        uzanti, ad, islev = {"word": (".docx", "Word", pi.word_e),
                             "powerpoint": (".pptx", "PowerPoint", pi.powerpoint_e)}[tur]
        yol = filedialog.asksaveasfilename(defaultextension=uzanti, filetypes=[(ad, "*" + uzanti)],
                                           initialfile=os.path.splitext(os.path.basename(self.yol))[0] + uzanti,
                                           initialdir=os.path.dirname(self.yol))
        if not yol:
            return
        self.bilgi(f"{ad} dosyası hazırlanıyor, biraz sürebilir…")
        self.pen.config(cursor="watch")
        self.pen.update()
        try:
            islev(self.doc, yol)
        except Exception as e:
            self.bilgi("Dönüştürülemedi.")
            return messagebox.showerror("Dönüştürülemedi", f"{ad} kurulu ve açılabilir olmalı.\n\n{e}")
        finally:
            self.pen.config(cursor="")
        self.bilgi(f"Kaydedildi: {yol}")
        if messagebox.askyesno("Dönüştürüldü", f"{os.path.basename(yol)} kaydedildi.\n\nAçılsın mı?"):
            os.startfile(yol)

    def bol_penceresi(self):
        """Açık belgeyi ayrı dosyalara böler: her sayfa / her N sayfa / yazılan aralıklar."""
        if not self.belge_var():
            return
        n = self.doc.page_count
        w = self.pencere("Böl")
        tk.Label(w, text=f"{os.path.basename(self.yol)} — {n} sayfa", font=tema.KALIN).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        tur = tk.StringVar(value="aralik")
        her = tk.IntVar(value=2)
        aralik = tk.StringVar(value=f"{self.sayfa + 1}")
        secenekler = [("tek", "Her sayfa ayrı dosya", None),
                      ("her", "Her", tk.Spinbox(w, from_=1, to=max(1, n), width=5, textvariable=her)),
                      ("aralik", "Aralıklar:", tk.Entry(w, textvariable=aralik, width=24))]
        for i, (deger, yazi, alan) in enumerate(secenekler, start=1):
            tk.Radiobutton(w, text=yazi, variable=tur, value=deger, selectcolor=tema.YUZEY2,
                           activebackground=tema.YUZEY).grid(row=i, column=0, sticky="w", pady=3)
            if alan:
                alan.grid(row=i, column=1, sticky="w", padx=4)
        tk.Label(w, text="sayfada bir", fg=tema.YAZI2).grid(row=2, column=2, sticky="w")
        tk.Label(w, text="ör. 1-3, 4, 5-9 → üç dosya.  Tek aralık yazarsanız o sayfaları çıkarmış olursunuz.",
                 fg=tema.YAZI2, wraplength=360, justify="left").grid(row=4, column=0, columnspan=3, sticky="w")
        alt = tk.Frame(w, pady=10)
        alt.grid(row=5, column=0, columnspan=3, sticky="e")

        def tamam():
            try:
                parcalar = (pi.esit_parcalar(n, 1) if tur.get() == "tek" else
                            pi.esit_parcalar(n, max(1, int(her.get()))) if tur.get() == "her" else
                            pi.aralik_coz(aralik.get(), n))
            except (ValueError, tk.TclError) as e:
                return messagebox.showerror("Hatalı aralık", str(e), parent=w)
            klasor = filedialog.askdirectory(title="Dosyalar hangi klasöre kaydedilsin?",
                                             initialdir=os.path.dirname(self.yol), parent=w)
            if not klasor:
                return
            ad = os.path.splitext(os.path.basename(self.yol))[0]
            var = [f for f in (os.path.join(klasor, f"{ad}_{a + 1}.pdf" if a == b else f"{ad}_{a + 1}-{b + 1}.pdf")
                               for a, b in parcalar) if os.path.exists(f)]
            if var and not messagebox.askyesno("Üstüne yazılsın mı?", f"{len(var)} dosya zaten var, örneğin:\n"
                                               f"{os.path.basename(var[0])}\n\nÜstüne yazılsın mı?", parent=w):
                return
            try:
                yollar = pi.bol(self.doc, parcalar, klasor, ad)
            except Exception as e:
                return messagebox.showerror("Bölünemedi", str(e), parent=w)
            w.destroy()
            self.bilgi(f"{len(yollar)} dosyaya bölündü: {klasor}")
            if messagebox.askyesno("Bölündü", f"{len(yollar)} dosya kaydedildi.\n\nKlasör açılsın mı?"):
                os.startfile(klasor)

        tema.dugme(alt, "bol", "Böl ve kaydet", tamam, sol=False).pack(side="left", padx=4)
        tema.dugme(alt, None, "İptal", w.destroy, sol=False).pack(side="left")
        w.grab_set()

    def birlestir_penceresi(self):
        """Birden çok PDF'i seçilen sırayla tek dosyada birleştirir. Açık belge (değişiklikleriyle) de eklenebilir."""
        w = self.pencere("Birleştir")
        tk.Label(w, text="Dosyalar bu sırayla birleştirilecek:", font=tema.KALIN).grid(row=0, column=0, sticky="w")
        liste = tk.Listbox(w, width=60, height=12, bd=0, activestyle="none", selectbackground=tema.VURGU)
        liste.grid(row=1, column=0, rowspan=5, sticky="nsew", pady=6)
        kaynaklar = []  # liste satırlarıyla aynı sırada: dosya yolu ya da açık belge
        if self.doc:
            kaynaklar.append(self.doc)
            liste.insert("end", f"● {os.path.basename(self.yol)} (açık belge{', kaydedilmemiş değişikliklerle' if self.degisti else ''})")

        def ekle():
            for y in filedialog.askopenfilenames(title="Eklenecek PDF'ler", filetypes=[("PDF", "*.pdf")], parent=w):
                kaynaklar.append(y)
                liste.insert("end", os.path.basename(y))

        def sec():
            s = liste.curselection()
            return s[0] if s else None

        def kaldir():
            i = sec()
            if i is not None:
                liste.delete(i)
                kaynaklar.pop(i)

        def tasi(yon):
            i = sec()
            if i is None or not 0 <= i + yon < len(kaynaklar):
                return
            kaynaklar[i], kaynaklar[i + yon] = kaynaklar[i + yon], kaynaklar[i]
            yazi = liste.get(i)
            liste.delete(i)
            liste.insert(i + yon, yazi)
            liste.selection_set(i + yon)

        yan = tk.Frame(w, padx=8)
        yan.grid(row=1, column=1, sticky="n", pady=6)
        for simge_adi, yazi, komut in [("pdf_ekle", "Dosya ekle…", ekle), ("sil", "Listeden çıkar", kaldir),
                                       ("yukari", "Yukarı", lambda: tasi(-1)), ("asagi", "Aşağı", lambda: tasi(1))]:
            tema.dugme(yan, simge_adi, yazi, komut).pack(fill="x", pady=2)

        def tamam():
            if len(kaynaklar) < 2:
                return messagebox.showinfo("Birleştir", "En az iki dosya ekleyin.", parent=w)
            ilk = kaynaklar[0]
            ad = os.path.splitext(os.path.basename(self.yol if ilk is self.doc else ilk))[0] + "_birlesik.pdf"
            yol = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=ad, filetypes=[("PDF", "*.pdf")],
                                               parent=w)
            if not yol:
                return
            if self.doc and os.path.normcase(os.path.abspath(yol)) == os.path.normcase(os.path.abspath(self.yol)):
                return messagebox.showerror("Birleştir", "Açık belgenin üstüne kaydedilemez; başka bir ad seçin.",
                                            parent=w)
            try:
                n = pi.birlestir(kaynaklar, yol)
            except Exception as e:
                return messagebox.showerror("Birleştirilemedi", str(e), parent=w)
            w.destroy()
            self.bilgi(f"{len(kaynaklar)} dosya birleştirildi ({n} sayfa): {yol}")
            if messagebox.askyesno("Birleştirildi", f"{n} sayfalık dosya kaydedildi.\n\nŞimdi açılsın mı?"):
                self.ac(yol)

        alt = tk.Frame(w, pady=6)
        alt.grid(row=6, column=0, columnspan=2, sticky="e")
        tema.dugme(alt, "birlestir", "Birleştir ve kaydet", tamam, sol=False).pack(side="left", padx=4)
        tema.dugme(alt, None, "İptal", w.destroy, sol=False).pack(side="left")
        w.grab_set()
        if not self.doc:
            w.after(50, ekle)

    # ---------- fareyle çalışan araçlar ----------
    def mod_sec(self, m):
        if not self.belge_var():
            return
        self.mod = None if self.mod == m else m
        self.secimi_birak()
        for ad, b in self.mod_dugmeleri.items():
            tema.secili_yap(b, ad == self.mod)
        self.tuval.config(cursor=("hand2" if self.mod == "sec" else "crosshair") if self.mod else "xterm")
        self.bilgi(IPUCU.get(self.mod, "Araç kapatıldı."))

    def renk_sec(self):
        from tkinter import colorchooser
        rgb, onalti = colorchooser.askcolor(color=self.renk_dugmesi.cget("bg"), title="Renk")
        if rgb:
            self.renk = tuple(v / 255 for v in rgb)
            self.renk_dugmesi.config(bg=onalti)

    def nokta(self, e):
        return self.tuval.canvasx(e.x), self.tuval.canvasy(e.y)

    def pdf_noktasi(self, e):
        x, y = self.nokta(e)
        return pi.noktadan(self.doc[self.sayfa], (x - KENAR) / self.zoom, (y - KENAR) / self.zoom)

    def kanvas_kutusu(self, s, bbox):
        return [KENAR + v * self.zoom for v in pi.gorunume(s, bbox)]

    def secim_var(self):
        return bool(self.secili or self.secili_resim)

    def secim_kutusu(self):
        """Seçili satırların ya da resmin ekrandaki toplam kutusu [x0, y0, x1, y1]."""
        s = self.doc[self.sayfa]
        if self.secili_resim:
            return self.kanvas_kutusu(s, self.secili_resim["bbox"])
        k = [self.kanvas_kutusu(s, l["bbox"]) for l in self.secili]
        return [min(b[0] for b in k), min(b[1] for b in k), max(b[2] for b in k), max(b[3] for b in k)]

    def secim_ciz(self):
        self.tuval.delete("secili")
        self.secim_bilgisi()
        if not (self.secim_var() and self.doc):
            return
        s = self.doc[self.sayfa]
        for l in self.secili:
            self.tuval.create_rectangle(*self.kanvas_kutusu(s, l["bbox"]), outline=tema.VURGU, dash=(5, 3),
                                        tags=("secili",))
        x0, y0, x1, y1 = self.secim_kutusu()
        self.tuval.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline=tema.VURGU, width=2, tags=("secili",))
        self.tuval.create_rectangle(x1 - 2, y1 - 2, x1 + 8, y1 + 8, fill=tema.VURGU, outline="white",
                                    tags=("secili", "tutamac"))

    def tutamacta_mi(self, c):
        if not self.secim_var():
            return False
        _, _, x1, y1 = self.secim_kutusu()
        return abs(c[0] - x1 - 3) <= 9 and abs(c[1] - y1 - 3) <= 9

    def secimi_birak(self):
        self.secili, self.secili_resim, self.tasima, self.olcekleme = [], None, None, None
        self.secim_ciz()

    def odak_yazida(self):
        return isinstance(self.pen.focus_get(), (tk.Entry, tk.Spinbox))

    def secilileri_sil(self):
        if not self.secim_var() or self.odak_yazida():
            return
        s, sec, resim = self.doc[self.sayfa], self.secili, self.secili_resim
        self.secili, self.secili_resim = [], None
        if resim:
            if self.degisiklik(lambda: pi.resmi_sil(s, resim["xref"])):
                self.bilgi("Resim silindi.")
        elif self.degisiklik(lambda: pi.yazilari_sil(s, sec)):
            self.bilgi(f"{len(sec)} satır silindi.")

    def resmi_sec(self, xref, yaklasik=None):
        """Sayfadaki resmi xref'iyle (aynı resim birkaç kez varsa yaklaşık kutusuna en yakın olanı) seçer."""
        aday = [r for r in pi.resimler(self.doc[self.sayfa]) if r["xref"] == xref]
        if yaklasik is not None and aday:
            aday.sort(key=lambda r: abs(r["bbox"].x0 - yaklasik.x0) + abs(r["bbox"].y0 - yaklasik.y0))
        self.secili, self.secili_resim = [], (aday[0] if aday else None)
        self.secim_ciz()

    def resim_degistir(self, yeni_kutu, veri=None, mesaj=""):
        """Seçili resmi yeni kutuya taşır/boyutlandırır ya da (veri ile) içeriğini değiştirir; seçili kalır."""
        s, r = self.doc[self.sayfa], self.secili_resim
        self.secili_resim, sonuc = None, []
        if self.degisiklik(lambda: sonuc.append(pi.resmi_yerlestir(s, r["xref"], yeni_kutu, veri))):
            self.resmi_sec(sonuc[0], yeni_kutu)
            self.bilgi(mesaj)

    def donustur(self, kx=0, ky=0, olcek=1, merkez=(0, 0), mesaj=""):
        """Seçili satırları / resmi taşır, büyütür; sonra aynı şey yeni yerinde seçili kalır."""
        if self.secili_resim:
            b = self.secili_resim["bbox"]
            yeni = pymupdf.Rect(pi.donusmus(b.tl, kx, ky, olcek, merkez), pi.donusmus(b.br, kx, ky, olcek, merkez))
            return self.resim_degistir(yeni.normalize(), mesaj=mesaj.replace("satır", "resim"))
        s, sec = self.doc[self.sayfa], self.secili
        self.secili = []
        if not self.degisiklik(lambda: pi.satirlari_donustur(s, sec, kx, ky, olcek, merkez)):
            return
        self.yeniden_sec(sec, kx, ky, olcek, merkez)
        self.bilgi(mesaj)

    def yeniden_sec(self, sec, kx=0, ky=0, olcek=1, merkez=(0, 0)):
        """Taşınan / yapıştırılan satırları yeni yerlerinde seçer."""
        hedef = [pymupdf.Rect(pi.donusmus(l["bbox"][:2], kx, ky, olcek, merkez),
                              pi.donusmus(l["bbox"][2:], kx, ky, olcek, merkez)).normalize() for l in sec]
        self.secili = [l for l in pi.satirlar(self.doc[self.sayfa])
                       if any((pymupdf.Rect(l["bbox"]) & h).get_area() > 0.4 * pymupdf.Rect(l["bbox"]).get_area()
                              for h in hedef)]
        self.secim_ciz()

    def kopyala(self):
        """Seçili satırları uygulama içi panoya (biçimleriyle) ve Windows panosuna (düz yazı) alır."""
        if self.odak_yazida() or not self.doc:
            return
        if not self.mod and getattr(self, "secili_metin", ""):
            self.pen.clipboard_clear()
            self.pen.clipboard_append(self.secili_metin)
            return self.bilgi("Seçili yazı kopyalandı.")
        if self.mod != "duzenle" or not self.secili:
            return self.bilgi("Kopyalamak için araç seçmeden yazının üstünden kutu çizin; eklediğiniz yazıyı biçimiyle "
                              "kopyalamak için “Yazıyı düzenle” aracıyla seçin.")
        self.pano = list(self.secili)
        self.pen.clipboard_clear()
        self.pen.clipboard_append("\n".join(pi.satir_metni(l) for l in self.pano).replace("\xa0", " "))
        self.bilgi(f"{len(self.pano)} satır kopyalandı. Ctrl+V ile farenin olduğu yere yapıştırın.")

    def yapistir(self):
        """Kopyalanan satırları fare sayfanın üstündeyse oraya, değilse biraz kaydırarak yapıştırır."""
        if self.odak_yazida() or not self.doc or not getattr(self, "pano", None):
            return
        s, sec, t = self.doc[self.sayfa], self.pano, self.tuval
        cx, cy = t.winfo_pointerx() - t.winfo_rootx(), t.winfo_pointery() - t.winfo_rooty()
        if 0 <= cx < t.winfo_width() and 0 <= cy < t.winfo_height():
            p = pi.noktadan(s, (t.canvasx(cx) - KENAR) / self.zoom, (t.canvasy(cy) - KENAR) / self.zoom)
            kx, ky = p.x - min(l["bbox"][0] for l in sec), p.y - min(l["bbox"][1] for l in sec)
        else:
            kx = ky = 12
        if not self.degisiklik(lambda: pi.satirlari_yaz(s, sec, kx, ky)):
            return
        if self.mod != "duzenle":
            self.mod_sec("duzenle")
        self.yeniden_sec(sec, kx, ky)
        self.bilgi(f"{len(sec)} satır yapıştırıldı. Oklarla ya da sürükleyerek yerini ayarlayabilirsiniz.")

    def ekran_vektoru(self, dx, dy):
        """Ekranda (görünen sayfada) dx, dy kadar kayma → PDF koordinatında kayma."""
        s = self.doc[self.sayfa]
        a, b = pi.noktadan(s, 0, 0), pi.noktadan(s, dx, dy)
        return b.x - a.x, b.y - a.y

    def sayfa_icinde(self, kutu, dx, dy):
        """Ekrandaki kayma (dx, dy), kutuyu sayfanın dışına çıkarmayacak kadar kısılır.
        Zaten taşmış bir kutu içeri doğru hareket edebilir, daha dışarı gidemez."""
        x0, y0, x1, y1 = kutu
        sag, alt = KENAR + self.img.width(), KENAR + self.img.height()
        dx = max(min(0, KENAR - x0), min(dx, max(0, sag - x1)))
        dy = max(min(0, KENAR - y0), min(dy, max(0, alt - y1)))
        return dx, dy

    def ok_tusu(self, dx, dy, e):
        if self.odak_yazida():
            return
        if self.mod != "duzenle" or not self.secim_var():  # seçili satır yoksa oklar sayfada gezinir
            return self.kaydir(dy) if dy else self.git(self.sayfa + dx) if self.doc else None
        adim = 10 if e.state & 1 else 1  # Shift ile 10
        cx, cy = self.sayfa_icinde(self.secim_kutusu(), dx * adim * self.zoom, dy * adim * self.zoom)
        if not (cx or cy):
            return self.bilgi("Sayfanın kenarına gelindi.")
        kx, ky = self.ekran_vektoru(cx / self.zoom, cy / self.zoom)
        self.donustur(kx, ky, mesaj=f"{len(self.secili) or 1} satır kaydırıldı.")

    def enter_tusu(self):
        if self.mod != "duzenle" or self.odak_yazida():
            return
        if self.secili_resim:
            self.resim_arka_plani()
        elif len(self.secili) == 1:
            self.satiri_duzenle(self.secili[0])

    def satiri_duzenle(self, l):
        s = self.doc[self.sayfa]
        eski = pi.satir_metni(l).replace("\xa0", " ")
        yeni = simpledialog.askstring("Yazıyı düzenle", "Yeni metin (boş bırakırsanız satır silinir):",
                                      initialvalue=eski, parent=self.pen)
        if yeni is not None and yeni != eski:
            self.secimi_birak()
            self.degisiklik(lambda: pi.satir_degistir(s, l, yeni, HIZALAR[self.hiza.get()] % 3))
            self.tuval.delete("uzerinde")

    def duzenle_cift(self, e):
        if self.mod != "duzenle" or not self.doc:
            return
        s, p = self.doc[self.sayfa], self.pdf_noktasi(e)
        l = pi.satir_bul(s, p)
        if l:
            return self.satiri_duzenle(l)
        r = pi.resim_bul(s, p)
        if r:
            self.resmi_sec(r["xref"], r["bbox"])
            return self.resim_arka_plani()
        self.bilgi("Burada düzenlenebilir yazı ya da resim yok. Sayfa taranmış olabilir; "
                   "o durumda ⬜ Beyazla + yaz aracını kullanın.")

    def tasi_bas(self, e):
        s, c = self.doc[self.sayfa], self.nokta(e)
        if self.tutamacta_mi(c):  # köşeden tut: büyüt / küçült
            x0, y0, x1, y1 = self.secim_kutusu()
            self.olcekleme = {"sol": x0, "ust": y0, "en": max(1, x1 - x0), "boy": max(1, y1 - y0), "olcek": 1}
            return
        p = self.pdf_noktasi(e)
        secimde = (self.secili_resim["bbox"].contains(p) if self.secili_resim else
                   any((pymupdf.Rect(l["bbox"]) + (-2, -2, 2, 2)).contains(p) for l in self.secili))
        if not secimde:  # önce yazı, yoksa resim seçilir
            l = pi.satir_bul(s, p)
            r = None if l else pi.resim_bul(s, p)
            self.secili, self.secili_resim = ([l] if l else []), r
            self.secim_ciz()
        if self.secim_var():
            self.tasima = {"bas": c, "kutu": self.secim_kutusu(), "kayma": (0, 0)}
        else:  # boş yer: seçim kutusu
            self.bas = c
            self.kutu = self.tuval.create_rectangle(*c, *c, outline=tema.VURGU, dash=(3, 3))

    def tasi_surukle(self, n):
        if self.olcekleme:
            o = self.olcekleme
            sag, alt = KENAR + self.img.width(), KENAR + self.img.height()
            tavan = min(max(1, (sag - o["sol"]) / o["en"]), max(1, (alt - o["ust"]) / o["boy"]))  # sayfadan taşmasın
            o["olcek"] = max(0.2, min(6, tavan, max((n[0] - o["sol"]) / o["en"], (n[1] - o["ust"]) / o["boy"])))
            self.tuval.delete("secili")
            self.tuval.create_rectangle(o["sol"], o["ust"], o["sol"] + o["en"] * o["olcek"],
                                        o["ust"] + o["boy"] * o["olcek"], outline=tema.VURGU, width=2, dash=(4, 2),
                                        tags=("secili",))
            self.bilgi(f"Boyut: %{o['olcek'] * 100:.0f}")
        else:  # seçili satırların çerçeveleri fareyle birlikte gider; sayfa kenarında durur
            t = self.tasima
            dx, dy = self.sayfa_icinde(t["kutu"], n[0] - t["bas"][0], n[1] - t["bas"][1])
            self.tuval.move("secili", dx - t["kayma"][0], dy - t["kayma"][1])
            t["kayma"] = (dx, dy)

    def tasi_birak(self, e):
        s, z = self.doc[self.sayfa], self.zoom
        if self.olcekleme:
            o, self.olcekleme = self.olcekleme, None
            if abs(o["olcek"] - 1) < 0.02:
                return self.secim_ciz()
            merkez = pi.noktadan(s, (o["sol"] - KENAR) / z, (o["ust"] - KENAR) / z)
            return self.donustur(olcek=o["olcek"], merkez=merkez, mesaj=f"Boyut %{o['olcek'] * 100:.0f} yapıldı.")
        if self.tasima:
            (x0, y0), (x1, y1) = self.tasima["bas"], self.nokta(e)
            dx, dy = self.tasima["kayma"]
            self.tasima = None
            if abs(x1 - x0) + abs(y1 - y0) < 3:  # sadece tıklama: seçim kalsın
                ne = "Resim" if self.secili_resim else f"{len(self.secili)} satır"
                cift = "arka planı temizle" if self.secili_resim else "düzenle"
                return self.bilgi(f"{ne} seçili. Sürükle: taşı · köşedeki kare: büyüt/küçült · "
                                  f"çift tıkla / Enter: {cift} · oklar: kaydır · Delete: sil")
            if not (dx or dy):
                return self.secim_ciz()
            kx, ky = self.ekran_vektoru(dx / z, dy / z)
            return self.donustur(kx, ky, mesaj=f"{len(self.secili) or 1} satır taşındı.")
        if self.bas:  # seçim kutusu bitti
            (x0, y0), (x1, y1) = self.bas, self.nokta(e)
            self.bas = None
            self.tuval.delete(self.kutu)
            self.kutu = None
            self.secili_resim = None
            self.secili = pi.kutudaki_satirlar(s, pi.gorunumden(s, *[(v - KENAR) / z for v in (x0, y0, x1, y1)]))
            self.secim_ciz()
            self.bilgi(f"{len(self.secili)} satır seçildi. Birini tutup sürükleyin; köşedeki kare ile büyütün."
                       if self.secili else "Seçilen alanda yazı yok.")

    def uzerinde(self, e):
        """Yazıyı düzenle aracında fare altındaki satırı çerçeveler, imleci duruma göre değiştirir."""
        self.tuval.delete("uzerinde")
        if self.mod != "duzenle" or not self.doc or self.tasima or self.olcekleme:
            return
        if self.tutamacta_mi(self.nokta(e)):
            return self.tuval.config(cursor="size_nw_se")
        s, p = self.doc[self.sayfa], self.pdf_noktasi(e)
        l = pi.satir_bul(s, p)
        kutu = l["bbox"] if l else (pi.resim_bul(s, p) or {}).get("bbox")
        self.tuval.config(cursor="fleur" if kutu else "crosshair")
        if kutu:
            self.tuval.create_rectangle(*self.kanvas_kutusu(s, kutu), outline=tema.VURGU, width=1,
                                        tags=("uzerinde",))

    def bas_(self, e):
        if not self.doc:
            return
        self.tuval.delete("metin")  # araçsız sürükleme = yazı seçimi (birak_ → metin_sec)
        self.secili_metin = ""
        if self.mod == "duzenle":
            return self.tasi_bas(e)
        self.bas = self.nokta(e)
        if self.mod == "kalem":
            self.kalem_noktalari = [self.bas]
            self.kutu = self.tuval.create_line(*self.bas, *self.bas, fill=tema.VURGU, width=2)
        elif self.mod in ("cizgi", "ok"):
            self.kutu = self.tuval.create_line(*self.bas, *self.bas, fill=tema.VURGU, width=2,
                                               arrow="last" if self.mod == "ok" else None)
        elif self.mod not in NOKTA_ARACLARI or self.mod == "yazi":
            self.kutu = self.tuval.create_rectangle(*self.bas, *self.bas, outline=tema.VURGU, dash=(4, 2), width=2)

    def surukle_(self, e):
        n = self.nokta(e)
        if self.tasima or self.olcekleme:
            return self.tasi_surukle(n)
        if not self.bas or not self.kutu:
            return
        if self.mod == "kalem":
            self.kalem_noktalari.append(n)
            self.tuval.coords(self.kutu, *[v for p in self.kalem_noktalari for v in p])
        else:
            self.tuval.coords(self.kutu, *self.bas, *n)

    def birak_(self, e):
        if self.mod == "duzenle":
            return self.tasi_birak(e)
        if not self.bas:
            return
        (cx0, cy0), (cx1, cy1), z = self.bas, self.nokta(e), self.zoom
        self.bas = None
        if self.kutu:
            self.tuval.delete(self.kutu)
            self.kutu = None
        s = self.doc[self.sayfa]
        g = s.rect  # ekranda görülen sayfa boyutu
        x0, y0, x1, y1 = [(v - KENAR) / z for v in (cx0, cy0, cx1, cy1)]
        kutu = lambda: pi.gorunumden(s, x0, y0, x1, y1)
        kucuk = abs(x1 - x0) < 5 or abs(y1 - y0) < 5
        mod = self.mod
        if not mod:
            return None if kucuk else self.metin_sec(s, kutu())
        if mod == "sec":
            return self.not_penceresi(s, pi.noktadan(s, x0, y0))
        if mod == "not":
            metin = simpledialog.askstring("Not ekle", "Not:", parent=self.pen)
            if metin:
                self.degisiklik(lambda: pi.not_ekle(s, pi.noktadan(s, x0, y0), metin))
            return
        if mod == "yazi":
            if kucuk:  # tıklama: tıklanan yerden sayfanın sağ altına kadar
                x1, y1 = g.width - 20, g.height - 20
            metin = simpledialog.askstring("Yazı ekle", "Yazılacak metin:", parent=self.pen)
            if metin:
                sonuc = []
                self.degisiklik(lambda: sonuc.append(pi.yazi_ekle(s, kutu(), metin, self.boyut.get(), hiza=HIZALAR[self.hiza.get()])))
                if sonuc and sonuc[0] is None:
                    self.geri_al()
                    self.ileri.pop()  # başarısız deneme "ileri al" listesinde kalmasın
                    self.bilgi("Yazı kutuya sığmadı; daha büyük bir kutu çizin.")
            return
        if mod == "kalem":
            noktalar = [pi.noktadan(s, (px - KENAR) / z, (py - KENAR) / z) for px, py in self.kalem_noktalari]
            if len(noktalar) > 1:
                self.degisiklik(lambda: pi.kalem(s, noktalar, self.renk))
            return
        if mod in ("cizgi", "ok"):
            if abs(x1 - x0) + abs(y1 - y0) > 5:
                self.degisiklik(lambda: pi.sekil(s, mod, pi.noktadan(s, x0, y0), pi.noktadan(s, x1, y1), self.renk))
            return
        if mod == "resim":
            return self.resim_koy(s, x0, y0, None if kucuk else kutu())
        if kucuk:
            return self.bilgi("Alan çok küçük; fareyi basılı tutup bir kutu çizin.")
        if mod in pi.ISARETLER:
            self.degisiklik(lambda: pi.isaretle(s, kutu(), mod, self.renk))
        elif mod in ("dikdortgen", "daire"):
            self.degisiklik(lambda: pi.sekil(s, mod, pi.noktadan(s, x0, y0), pi.noktadan(s, x1, y1), self.renk))
        elif mod == "damga":
            metin = self.secimli_sor("Damga", "Damga yazısı (listeden seçin ya da yazın):", DAMGALAR)
            if metin:
                self.degisiklik(lambda: pi.damga(s, kutu(), metin.upper(), self.renk))
        elif mod == "degistir":
            metin = simpledialog.askstring("Değiştir", "Yeni metin (boş bırakırsanız alan sadece silinir):",
                                           parent=self.pen)
            if metin is not None:
                sonuc = []
                self.degisiklik(lambda: sonuc.append(pi.degistir(s, kutu(), metin, self.boyut.get(), HIZALAR[self.hiza.get()])))
                if sonuc and sonuc[0] is None:
                    self.bilgi("Alan silindi ama yeni yazı kutuya sığmadı; Yazı aracıyla ekleyin ya da Geri alın.")
        elif mod == "karart":
            if not self.karartma_uyarisi():
                return
            if self.degisiklik(lambda: pi.karart(s, [kutu()])):
                self.bilgi("Alan kalıcı olarak karartıldı. Kaydetmeden önce Geri al ile geri alınabilir.")
        elif mod == "form":
            self.form_alani_sor(s, kutu())

    # ---------- resim ----------
    def resim_koy(self, s, x, y, kutu):
        """Resim seç → arka plan penceresi → ekle → Düzenle aracında seçili hale getir.
        kutu None ise tıklanan yere doğal boyutunda (sayfanın en fazla üçte biri) konur."""
        yol = filedialog.askopenfilename(title="Resim / imza seçin",
                                         filetypes=[("Resim", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"), ("Tümü", "*.*")])
        if not yol:
            return
        from PIL import Image, ImageOps
        try:
            with Image.open(yol) as im:
                im = ImageOps.exif_transpose(im).convert("RGBA")  # telefon fotoğrafı yan durmasın
        except Exception as e:
            return messagebox.showerror("Resim açılamadı", str(e))
        im = self.arka_plan_penceresi(im, ilk_ekleme=True)
        if im is None:
            return
        en, boy = im.size
        if kutu is None:  # 96 dpi kabulüyle doğal boyut, sayfaya sığacak kadar
            g = s.rect
            o = min(0.75, g.width / 3 / en, g.height / 3 / boy)
            x, y = min(x, g.width - en * o), min(y, g.height - boy * o)
            kutu = pi.gorunumden(s, x, y, x + en * o, y + boy * o)
        else:
            kutu = pi.oranli_kutu(kutu, *((boy, en) if s.rotation in (90, 270) else (en, boy)))
        sonuc = []
        if self.degisiklik(lambda: sonuc.append(pi.resim_ekle(s, kutu, veri=pi.png_baytlari(im)))):
            self.mod_sec("duzenle")
            self.resmi_sec(sonuc[0], kutu)
            self.bilgi("Resim eklendi. Sürükleyerek taşıyın, köşedeki kare ile büyütün/küçültün; "
                       "çift tıklayınca arka planı temizlenir.")

    def resim_arka_plani(self):
        """Seçili resmin arka planını temizler (önizlemeli pencereyle)."""
        r = self.secili_resim
        if not r:
            return
        try:
            im = pi.resim_pil(self.doc, r["xref"])
        except Exception as e:
            return messagebox.showerror("Resim okunamadı", str(e))
        temiz = self.arka_plan_penceresi(im)
        if temiz is not None:
            self.resim_degistir(r["bbox"], pi.png_baytlari(temiz), "Arka plan temizlendi.")

    def arka_plan_penceresi(self, im, ilk_ekleme=False):
        """Önizlemeli arka plan temizleme. Seçilen sonucu (PIL RGBA) ya da iptalde None döner.
        ilk_ekleme: 'Olduğu gibi ekle' seçeneği de gösterilir."""
        from PIL import Image
        w = self.pencere("Arka planı temizle")
        onizleme = im.copy()
        onizleme.thumbnail((420, 300))
        tk.Label(w, text="Düz renkli arka plan (beyaz kağıt, duvar, masa) şeffaf yapılır.", fg=tema.YAZI2
                 ).pack(anchor="w")
        resim_etiketi = tk.Label(w, bg=tema.ZEMIN)
        resim_etiketi.pack(pady=8)
        tolerans = tk.IntVar(value=40)
        kenardan = tk.BooleanVar(value=True)
        temizle = tk.BooleanVar(value=not ilk_ekleme)
        ayar = tk.Frame(w)
        ayar.pack(fill="x")
        tk.Checkbutton(ayar, text="Arka planı temizle", variable=temizle, selectcolor=tema.YUZEY2,
                       command=lambda: guncelle()).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(ayar, text="Hassasiyet", fg=tema.YAZI2).grid(row=1, column=0, sticky="w")
        tk.Scale(ayar, from_=5, to=150, orient="horizontal", variable=tolerans, length=260, showvalue=False,
                 troughcolor=tema.YUZEY2, sliderrelief="flat", bg=tema.VURGU, activebackground=tema.VURGU_ACIK,
                 bd=0, sliderlength=18, command=lambda _: geciktir()).grid(row=1, column=1)
        tk.Checkbutton(ayar, text="Sadece kenara bağlı zemin (fotoğraf için; kapalıysa imzanın harf içleri de "
                                  "temizlenir)", variable=kenardan, selectcolor=tema.YUZEY2, wraplength=380,
                       justify="left", command=lambda: guncelle()).grid(row=2, column=0, columnspan=2, sticky="w")
        bekleyen = [None]

        def dama(boyut):  # şeffaf yerleri göstermek için damalı zemin
            d = Image.new("RGBA", boyut, "#3a3a4a")
            kare = Image.new("RGBA", (8, 8), "#2a2a36")
            for yy in range(0, boyut[1], 8):
                for xx in range((yy // 8) % 2 * 8, boyut[0], 16):
                    d.paste(kare, (xx, yy))
            return d

        zemin = dama(onizleme.size)

        def guncelle():
            bekleyen[0] = None
            g = pi.arka_plani_temizle(onizleme, tolerans.get(), kenardan.get()) if temizle.get() else onizleme
            resim_etiketi.img = ImageTk.PhotoImage(Image.alpha_composite(zemin, g))
            resim_etiketi.config(image=resim_etiketi.img)

        def geciktir():  # sürgü sürüklenirken her adımda değil, durunca hesapla
            if bekleyen[0]:
                w.after_cancel(bekleyen[0])
            bekleyen[0] = w.after(120, guncelle)

        sonuc = [None]

        def bitir(kullan):
            if kullan:
                sonuc[0] = pi.arka_plani_temizle(im, tolerans.get(), kenardan.get()) if temizle.get() else im
            w.destroy()

        alt = tk.Frame(w, pady=10)
        alt.pack(fill="x")
        tema.dugme(alt, None, "İptal", lambda: bitir(False), sol=False).pack(side="right")
        tema.dugme(alt, "resim", "Ekle" if ilk_ekleme else "Uygula", lambda: bitir(True), sol=False
                   ).pack(side="right", padx=6)
        guncelle()
        w.bind("<Return>", lambda e: bitir(True))
        w.bind("<Escape>", lambda e: bitir(False))
        w.grab_set()
        self.pen.wait_window(w)
        return sonuc[0]

    # ---------- yardımcı pencereler ----------
    def secimli_sor(self, baslik, soru, secenekler):
        """Açılır listeli soru penceresi; yazılan ya da seçilen değeri, iptalde None döner."""
        from tkinter import ttk
        w = tk.Toplevel(self.pen)
        w.title(baslik)
        w.transient(self.pen)
        w.resizable(False, False)
        tk.Label(w, text=soru, padx=10, pady=6).pack(anchor="w")
        deger = tk.StringVar(value=secenekler[0] if secenekler else "")
        kutu = ttk.Combobox(w, textvariable=deger, values=secenekler, width=34)
        kutu.pack(padx=10)
        kutu.focus_set()
        sonuc = [None]

        def tamam(_=None):
            sonuc[0] = deger.get().strip() or None
            w.destroy()

        alt = tk.Frame(w, pady=8)
        alt.pack()
        tk.Button(alt, text="Tamam", width=10, command=tamam).pack(side="left", padx=4)
        tk.Button(alt, text="İptal", width=10, command=w.destroy).pack(side="left", padx=4)
        w.bind("<Return>", tamam)
        w.bind("<Escape>", lambda e: w.destroy())
        w.grab_set()
        self.pen.wait_window(w)
        return sonuc[0]

    def karartma_uyarisi(self):
        if self.karartma_onayli:
            return True
        self.karartma_onayli = messagebox.askyesno(
            "Karartma — kalıcı silme",
            "Karartılan alandaki yazı, resim, not ve form alanları dosyadan GERÇEKTEN silinir; "
            "siyah kutunun altından kopyalanamaz ya da geri getirilemez.\n\n"
            "Kaydetmeden önce Geri al (Ctrl+Z) ile vazgeçebilirsiniz. Asıl dosyayı korumak için "
            "Farklı kaydet kullanın.\n\nDevam edilsin mi?", icon="warning")
        return self.karartma_onayli

    def bulunanlari_karart(self):
        if not self.belge_var():
            return
        metin = simpledialog.askstring("Her yerde karart", "Karartılacak yazı (ör. TC kimlik no, IBAN, ad):",
                                       initialvalue=self.arama.get().strip(), parent=self.pen)
        if not metin:
            return
        n = len(pi.ara(self.doc, metin))
        if not n:
            return messagebox.showinfo("Bulunamadı", f"“{metin}” belgede bulunamadı.")
        if not messagebox.askyesno(
                "Karart", f"“{metin}” {n} yerde bulundu. Hepsi KALICI olarak karartılsın mı?\n\n"
                "Dikkat: arama Türkçe büyük/küçük harf eşlerini (İ/i, I/ı) her zaman yakalamaz. "
                "Farklı yazılışları da ayrıca arayın.", icon="warning"):
            return
        if self.degisiklik(lambda: pi.metni_karart(self.doc, metin), sayfalar=True):
            self.bilgi(f"“{metin}” {n} yerde karartıldı.")

    def not_penceresi(self, s, nokta):
        a = pi.not_bul(s, nokta)
        if not a:
            return self.bilgi("Burada not ya da işaret yok. (Form alanları için: 📝 Formu doldur)")
        xref, tur = a.xref, a.type[1]
        info = a.info
        w = tk.Toplevel(self.pen)
        w.title(f"{tur} — {info.get('title') or ''}")
        w.transient(self.pen)
        tk.Label(w, text=f"Tür: {tur}    Yazan: {info.get('title') or '-'}    Tarih: {info.get('modDate') or '-'}",
                 padx=8, pady=4).pack(anchor="w")
        yazi = tk.Text(w, width=50, height=8, wrap="word")
        yazi.insert("1.0", info.get("content") or "")
        yazi.pack(padx=8, fill="both", expand=True)
        alt = tk.Frame(w, pady=6)
        alt.pack()

        def kaydet():
            icerik = yazi.get("1.0", "end-1c")
            w.destroy()
            if icerik != (info.get("content") or ""):
                def islem():
                    n = s.load_annot(xref)
                    n.set_info(content=icerik)
                    n.update()
                self.degisiklik(islem)

        def sil():
            w.destroy()
            self.degisiklik(lambda: s.delete_annot(s.load_annot(xref)))
            self.bilgi(f"{tur} silindi.")

        tk.Button(alt, text="Kaydet", width=10, command=kaydet).pack(side="left", padx=4)
        tk.Button(alt, text="🗑 Sil", width=10, command=sil).pack(side="left", padx=4)
        tk.Button(alt, text="Kapat", width=10, command=w.destroy).pack(side="left", padx=4)
        w.grab_set()

    def form_alani_sor(self, s, rect):
        turler = {"Metin kutusu": "metin", "Onay kutusu": "onay", "Açılır liste": "liste"}
        tur = self.secimli_sor("Form alanı", "Alan türü:", list(turler))
        if tur not in turler:
            return
        ad = simpledialog.askstring("Form alanı", "Alanın adı (ör. ad_soyad, tarih):", parent=self.pen)
        if ad is None:
            return
        secim = None
        if turler[tur] == "liste":
            s_ = simpledialog.askstring("Açılır liste", "Seçenekler (virgülle ayırın):", parent=self.pen)
            secim = [x.strip() for x in (s_ or "").split(",") if x.strip()] or None
        sonuc = []
        if self.degisiklik(lambda: sonuc.append(pi.form_alani_ekle(self.doc, s, turler[tur], rect, ad, secim))):
            self.bilgi(f"“{sonuc[0]}” alanı eklendi. Doldurmak için 📝 Formu doldur.")

    def form_penceresi(self):
        if not self.belge_var():
            return
        from tkinter import ttk
        if pi.xfa_formu_mu(self.doc):
            messagebox.showwarning("Form", "Bu form Acrobat'a özel (XFA) bir form; burada doldurulamayabilir. "
                                           "Görünen standart alanlar listelenecek.")
        alanlar = pi.form_alanlari(self.doc)
        if not alanlar:
            return messagebox.showinfo("Form", "Bu PDF'te doldurulabilir form alanı yok.\n"
                                               "Eklemek için: ☐ Form alanı aracı.")
        w = tk.Toplevel(self.pen)
        w.title("Formu doldur")
        w.transient(self.pen)
        w.geometry("560x600")
        tuval = tk.Canvas(w, highlightthickness=0)
        kay = tk.Scrollbar(w, orient="vertical", command=tuval.yview)
        ic = tk.Frame(tuval)
        ic.bind("<Configure>", lambda e: tuval.configure(scrollregion=tuval.bbox("all")))
        tuval.create_window((0, 0), window=ic, anchor="nw")
        tuval.configure(yscrollcommand=kay.set)
        alt = tk.Frame(w, pady=6)
        alt.pack(side="bottom", fill="x")
        kay.pack(side="right", fill="y")
        tuval.pack(fill="both", expand=True)
        degiskenler = {}
        for n, (i, a) in enumerate(alanlar):
            tk.Label(ic, text=f"s.{i + 1}  {a.field_label or a.field_name}", anchor="w", width=28).grid(
                row=n, column=0, sticky="w", padx=6, pady=3)
            if a.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                v = tk.BooleanVar(value=a.field_value not in (None, "", "Off", False))
                tk.Checkbutton(ic, variable=v, text=a.on_state() if a.field_type ==
                               pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON else "").grid(row=n, column=1, sticky="w")
            elif a.field_type in (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, pymupdf.PDF_WIDGET_TYPE_LISTBOX):
                sec = pi.secenekler(a)
                gorunen = {g: k for k, g in sec}
                mevcut = next((g for k, g in sec if k == a.field_value), a.field_value or "")
                v = tk.StringVar(value=mevcut)
                ttk.Combobox(ic, textvariable=v, values=[g for _, g in sec], width=32).grid(row=n, column=1, sticky="w")
                v.gorunen = gorunen  # gösterilen metni kayıt değerine çevirmek için
            else:
                v = tk.StringVar(value=a.field_value or "")
                tk.Entry(ic, textvariable=v, width=35).grid(row=n, column=1, sticky="w")
            degiskenler[a.xref] = v
        ilk = {x: v.get() for x, v in degiskenler.items()}

        def uygula():
            yeni = {}
            for x, v in degiskenler.items():
                d = v.get()
                if d != ilk[x]:
                    yeni[x] = getattr(v, "gorunen", {}).get(d, d)
            w.destroy()
            if not yeni:
                return self.bilgi("Formda değişiklik yok.")
            duz = []
            if self.degisiklik(lambda: duz.extend(pi.form_doldur(self.doc, yeni)), sayfalar=True):
                if duz:
                    messagebox.showinfo(
                        "Form dolduruldu",
                        "Şu alanlarda ş, ğ, ı veya İ harfi olduğu için alan, sayfaya kalıcı yazı olarak çevrildi "
                        "(PDF formlarının standart yazı tipi bu harfleri gösteremiyor):\n\n• " + "\n• ".join(duz))
                self.bilgi(f"Form dolduruldu ({len(yeni)} alan).")

        tk.Button(alt, text="Uygula", width=12, command=uygula).pack(side="left", padx=8)
        tk.Button(alt, text="İptal", width=12, command=w.destroy).pack(side="left")
        tk.Label(alt, text="Değişiklikler Geri al ile geri alınabilir.", fg=tema.YAZI2).pack(side="left", padx=8)
        w.grab_set()


if __name__ == "__main__":
    if "--test" in sys.argv:
        pi.test()
    else:
        Uygulama(next((a for a in sys.argv[1:] if not a.startswith("--")), None)).pen.mainloop()
