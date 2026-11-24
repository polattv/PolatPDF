"""PDF işleri — arayüzden bağımsız, test edilebilir. Test: python pdf_islemleri.py"""
import difflib, math, os, sys, tempfile
import pymupdf

YAZI_TIPI = r"C:\Windows\Fonts\arial.ttf"  # yerleşik helv ş ğ ı İ çizemiyor
YAZI_ADI = "arial"


def gorunumden(page, x0, y0, x1, y1):
    """Ekranda görülen (döndürülmüş) sayfa koordinatlarını PDF'in kendi koordinatlarına çevirir."""
    r = pymupdf.Rect(x0, y0, x1, y1).normalize()
    return (r * page.derotation_matrix).normalize()


def gorunume(page, rect):
    """PDF koordinatındaki kutuyu ekranda görülen sayfa koordinatına çevirir (arama sonuçları için)."""
    return (pymupdf.Rect(rect) * page.rotation_matrix).normalize()


def noktadan(page, x, y):
    """Ekranda görülen tek bir noktayı PDF koordinatına çevirir (çizgi, ok, kalem: yön kaybolmasın)."""
    return pymupdf.Point(x, y) * page.derotation_matrix


def yazi_ekle(page, rect, metin, boyut=11, renk=(0, 0, 0), hiza=0):
    """Metni kutuya yazar; sığmazsa yazıyı küçülterek dener. Yazılan boyutu döner, sığmazsa None."""
    while boyut >= 5:
        kalan = page.insert_textbox(rect, metin, fontsize=boyut, fontname=YAZI_ADI, fontfile=YAZI_TIPI,
                                    color=renk, rotate=page.rotation, align=hiza)
        if kalan >= 0:
            return boyut
        boyut -= 1
    return None


# ---------- var olan yazıyı düzenleme ----------
FONT_KLASORU = r"C:\Windows\Fonts"
AILELER = {"narrow": ("arialn", "arialnb", "arialni", "arialnbi"),  # "ArialNarrow" "arial"dan önce bakılmalı
           "times":("times", "timesbd", "timesi", "timesbi"), "serif": ("times", "timesbd", "timesi", "timesbi"),
           "courier": ("cour", "courbd", "couri", "courbi"), "mono": ("cour", "courbd", "couri", "courbi"),
           "calibri": ("calibri", "calibrib", "calibrii", "calibriz"),
           "verdana": ("verdana", "verdanab", "verdanai", "verdanaz"),
           "tahoma": ("tahoma", "tahomabd", "tahoma", "tahomabd")}


def benzer_font(ad, bayrak):
    """PDF'teki yazı tipine en yakın Windows yazı tipi dosyası (Türkçe harfleri olan). Yoksa Arial."""
    aile = next((v for k, v in AILELER.items() if k in ad.lower()), ("arial", "arialbd", "ariali", "arialbi"))
    kalin = bool(bayrak & 16) or "bold" in ad.lower()
    italik = bool(bayrak & 2) or "italic" in ad.lower() or "oblique" in ad.lower()
    dosya = aile[kalin + 2 * italik]
    yol = os.path.join(FONT_KLASORU, dosya + ".ttf")
    return (dosya, yol) if os.path.exists(yol) else (YAZI_ADI, YAZI_TIPI)


def satirlar(page):
    """Yazı satırları; her satıra ait olduğu paragrafın kutusu ve satır sayısı da eklenir."""
    sonuc = []
    # sayfa dışına taşmış yazılar da okunsun: yoksa taşan kısım bir daha seçilemez, geri getirilemez
    for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_MEDIABOX_CLIP,
                           clip=pymupdf.INFINITE_RECT())["blocks"]:
        for l in b.get("lines", []):
            if "".join(s["text"] for s in l["spans"]).strip():
                l["paragraf"], l["paragraf_satir"] = b["bbox"], len(b["lines"])
                sonuc.append(l)
    return sonuc


def satir_bul(page, nokta):
    """Tıklanan noktadaki yazı satırı (PDF koordinatında nokta). Yoksa None."""
    for l in satirlar(page):
        if (pymupdf.Rect(l["bbox"]) + (-2, -2, 2, 2)).contains(nokta):
            return l
    return None


def satir_metni(l):
    return "".join(s["text"] for s in l["spans"])


def yeni_parcalar(l, yeni):
    """Yeni metni, eski satırın biçim parçalarına (kalın/normal, renk, boyut) dağıtır: değişmeyen harfler kendi
    biçimini korur, eklenen harfler yanındakinin biçimini alır. [(parca_no, metin)] döner."""
    eski = satir_metni(l)
    stil = [i for i, s in enumerate(l["spans"]) for _ in s["text"]]
    yeni_stil = []
    for tur, i1, i2, j1, j2 in difflib.SequenceMatcher(None, eski, yeni, autojunk=False).get_opcodes():
        if tur == "equal":
            yeni_stil += stil[i1:i2]
        elif j2 > j1:
            ref = stil[i1] if tur == "replace" else (stil[i1 - 1] if i1 else stil[0])
            yeni_stil += [ref] * (j2 - j1)
    parcalar = []
    for ch, st in zip(yeni, yeni_stil):
        if parcalar and parcalar[-1][0] == st:
            parcalar[-1][1] += ch
        else:
            parcalar.append([st, ch])
    return [tuple(p) for p in parcalar]


def yazilari_sil(page, satir_listesi):
    """Satırların yalnız yazısını siler; arka plan, çizgi ve resimler kalır."""
    for l in satir_listesi:
        r = pymupdf.Rect(l["bbox"])
        dx, dy = l["dir"]
        if abs(dx) >= abs(dy):  # komşu satırlara dokunmasın: yalnız satır yüksekliği yönünde daralt
            r += (0, r.height * 0.15, 0, -r.height * 0.15)
        else:
            r += (r.width * 0.15, 0, -r.width * 0.15, 0)
        page.add_redact_annot(r, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)


def donusmus(nokta, kx=0, ky=0, olcek=1, merkez=(0, 0)):
    """Bir noktanın taşıma + büyütme sonrası yeri (PDF koordinatında)."""
    m = pymupdf.Point(merkez)
    return m + (pymupdf.Point(nokta) - m) * olcek + (kx, ky)


def satirlari_donustur(page, satir_listesi, kx=0, ky=0, olcek=1, merkez=(0, 0)):
    """Satırları kx, ky kadar kaydırır ve merkeze göre olcek kadar büyütür/küçültür. Her parça kendi yerine
    göre, kendi biçimiyle yazılır; yazı boyutu da olcek ile çarpılır."""
    yazilari_sil(page, satir_listesi)
    satirlari_yaz(page, satir_listesi, kx, ky, olcek, merkez)


def satirlari_yaz(page, satir_listesi, kx=0, ky=0, olcek=1, merkez=(0, 0)):
    """Satırları (başka sayfadan da olabilir) kendi biçimleriyle kx, ky kaydırılmış olarak yazar: kopyala-yapıştır."""
    for l in satir_listesi:
        dx, dy = l["dir"]
        aci = round(math.degrees(math.atan2(-dy, dx)) / 90) * 90 % 360
        for sp in l["spans"]:
            if not sp["text"].strip():
                continue
            ad, yol = benzer_font(sp["font"], sp["flags"])
            page.insert_text(donusmus(sp["origin"], kx, ky, olcek, merkez), sp["text"], fontsize=sp["size"] * olcek,
                             fontname=ad, fontfile=yol, color=pymupdf.sRGB_to_pdf(sp["color"]), rotate=aci)


def satirlari_tasi(page, satir_listesi, kx, ky):
    satirlari_donustur(page, satir_listesi, kx, ky)


def kutudaki_satirlar(page, rect):
    return [l for l in satirlar(page) if pymupdf.Rect(l["bbox"]).intersects(rect)]


def sag_engeller(page, l):
    """Yatay satırın sağında, aynı yükseklikte duran en yakın engelin x'i: başka yazı ya da dik çizgi/kutu kenarı."""
    r = pymupdf.Rect(l["bbox"])
    ust, alt = r.y0 + 1, r.y1 - 1
    sinir = page.cropbox.x1 - 15
    for o in satirlar(page):
        b = pymupdf.Rect(o["bbox"])
        if o["bbox"] != l["bbox"] and b.x0 >= r.x1 - 1 and b.y0 < alt and b.y1 > ust:
            sinir = min(sinir, b.x0 - 3)
    for yol in page.get_drawings():
        for it in yol["items"]:
            if it[0] == "l" and abs(it[1].x - it[2].x) < 1:
                kenarlar = [(it[1].x, min(it[1].y, it[2].y), max(it[1].y, it[2].y))]
            elif it[0] == "re":
                k = it[1]
                kenarlar = [(k.x0, k.y0, k.y1), (k.x1, k.y0, k.y1)]
            else:
                continue
            for x, y0, y1 in kenarlar:
                if x > r.x0 + 2 and y0 < alt and y1 > ust:
                    sinir = min(sinir, x - 2)
    return sinir


def satir_degistir(page, l, yeni, hiza=0):
    """Satırın yazısını siler (arka plan, çizgi, resim kalır) ve yerine yeni yazıyı her parçanın kendi boyut,
    renk ve benzer yazı tipiyle yazar. hiza 0: aynı başlangıçtan (sağdaki engeli geçecekse en fazla %35
    küçültülür), 1: eski satırın ortasına, 2: eski satırın sağ kenarına yaslı."""
    s0 = l["spans"][0]
    r = pymupdf.Rect(l["bbox"])
    dx, dy = l["dir"]
    engeller = sag_engeller(page, l)  # silmeden önce: satırın sağındaki yazılar ve tablo çizgileri
    yazilari_sil(page, [l])
    if not yeni:
        return
    aci = round(math.degrees(math.atan2(-dy, dx)) / 90) * 90 % 360  # yazının kendi yönü
    parcalar = []
    for i, metin in yeni_parcalar(l, yeni):
        sp = l["spans"][i]
        ad, yol = benzer_font(sp["font"], sp["flags"])
        en = pymupdf.Font(fontfile=yol).text_length(metin, fontsize=sp["size"])
        parcalar.append((metin, sp, ad, yol, en))
    toplam = sum(p[4] for p in parcalar)
    duz = dx > 0.99  # normal, soldan sağa yatay yazı
    if duz and hiza in (1, 2):  # ortala: eski satırın ortası, sağa: eski satırın sağ kenarı sabit kalır
        olcek = 1
        x = (r.x0 + r.x1 - toplam) / 2 if hiza == 1 else r.x1 - toplam
        o = pymupdf.Point(x, s0["origin"][1])
    else:
        sinir = max(1, engeller - s0["origin"][0]) if duz else 0  # dik yazıda küçültme yok
        olcek = max(0.65, sinir / toplam) if sinir and toplam > sinir else 1
        o = pymupdf.Point(s0["origin"])
    for metin, sp, ad, yol, en in parcalar:
        page.insert_text(o, metin, fontsize=sp["size"] * olcek, fontname=ad, fontfile=yol,
                         color=pymupdf.sRGB_to_pdf(sp["color"]), rotate=aci)
        o += pymupdf.Point(dx, dy) * (en * olcek)


def kelime_kutulari(page, rect):
    """Kutunun içine değen kelimelerin kutuları; kelime yoksa (taranmış sayfa) kutunun kendisi."""
    return [pymupdf.Rect(w[:4]) for w in page.get_text("words") if pymupdf.Rect(w[:4]).intersects(rect)] or [rect]


ISARETLER = {"vurgu": "add_highlight_annot", "alti": "add_underline_annot",
             "ustu": "add_strikeout_annot", "dalga": "add_squiggly_annot"}


def isaretle(page, rect, tur="vurgu", renk=None):
    a = getattr(page, ISARETLER[tur])(kelime_kutulari(page, rect))
    if renk:
        a.set_colors(stroke=renk)
    a.update()
    return a


# ---------- resimler ----------
RESIM_SINIRI = 2500  # telefon fotoğrafları PDF'i şişirmesin: uzun kenar en fazla bu kadar piksel


def resimler(page):
    """Seçilebilir resimler: [{xref, bbox}]. Silinmiş resmin 1×1 hayaleti ve sayfanın çoğunu kaplayan
    zemin resmi (taranmış belge) hariç; zemin yanlışlıkla taşınmasın."""
    alan = page.rect.width * page.rect.height
    return [{"xref": i["xref"], "bbox": pymupdf.Rect(i["bbox"])} for i in page.get_image_info(xrefs=True)
            if i["xref"] > 0 and i["width"] > 1 and i["height"] > 1
            and pymupdf.Rect(i["bbox"]).get_area() < 0.8 * alan]


def resim_bul(page, nokta):
    bulunan = [r for r in resimler(page) if r["bbox"].contains(nokta)]
    return bulunan[-1] if bulunan else None  # en üstteki


def resim_kullanimi(doc, xref):
    return sum(1 for i in range(doc.page_count) for r in doc[i].get_images() if r[0] == xref)


def resim_pil(doc, xref):
    """PDF'teki resmi (şeffaflık maskesiyle birlikte) PIL RGBA resmine çevirir."""
    from PIL import Image
    pix = pymupdf.Pixmap(doc, xref)
    smask = doc.xref_get_key(xref, "SMask")
    if smask[0] == "xref":
        pix = pymupdf.Pixmap(pymupdf.Pixmap(pymupdf.csRGB, pix) if pix.n - pix.alpha != 3 else pix,
                             pymupdf.Pixmap(doc, int(smask[1].split()[0])))
    elif pix.n - pix.alpha != 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return Image.frombytes("RGBA" if pix.alpha else "RGB", (pix.width, pix.height), pix.samples).convert("RGBA")


def png_baytlari(im):
    """Resmi PDF'e eklenecek PNG baytlarına çevirir (büyükse küçültür).
    MuPDF aynı içerikli resmi tanıyıp eski nesneyi yeniden kullanıyor; o nesne taşıma/silme sırasında 1×1
    hayalete döndüyse yeni resim görünmez olur. Bu yüzden sol üst 4 pikselin şeffaflığının en düşük 3 biti
    rastgele yapılır (en fazla %3 fark, gözle görülmez); her ekleme ayrı nesne olur."""
    import io
    im = im.convert("RGBA")
    if max(im.size) > RESIM_SINIRI:
        im.thumbnail((RESIM_SINIRI, RESIM_SINIRI))
    px, rastgele = im.load(), os.urandom(4)
    for i in range(min(4, im.width)):
        r, g, b, a = px[i, 0]
        px[i, 0] = (r, g, b, (a & ~7) | (rastgele[i] & 7))
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def resim_ekle(page, rect, yol=None, veri=None):
    """Dosyadan ya da PNG baytlarından resim ekler; oranı korunur. Eklenen resmin xref'ini döner."""
    if yol and veri is None:
        from PIL import Image, ImageOps
        with Image.open(yol) as im:
            veri = png_baytlari(ImageOps.exif_transpose(im).convert("RGBA"))  # telefon fotoğrafı yan durmasın
    return page.insert_image(rect, stream=veri, rotate=page.rotation, keep_proportion=True)


def oranli_kutu(rect, en, boy):
    """rect içine, en/boy oranını koruyarak sol üstten yerleşen kutu."""
    o = min(rect.width / en, rect.height / boy)
    return pymupdf.Rect(rect.x0, rect.y0, rect.x0 + en * o, rect.y0 + boy * o)


def kendine_ayir(page, xref):
    """Resim başka sayfalarda da kullanılıyorsa (aynı imza iki sayfada, her sayfadaki logo) bu sayfayı
    resmin kendi kopyasına bağlar; böylece taşıma/silme yalnız bu sayfayı etkiler. Kullanılacak xref'i döner."""
    doc = page.parent
    if resim_kullanimi(doc, xref) <= 1:
        return xref
    adlar = [r[7] for r in page.get_images(full=True) if r[0] == xref]
    kaynak = doc.xref_get_key(page.xref, "Resources")
    if kaynak[0] == "xref":
        rx, on = int(kaynak[1].split()[0]), "XObject/"
        if sum(1 for p in doc if doc.xref_get_key(p.xref, "Resources") == kaynak) > 1:
            raise ValueError("Bu sayfanın kaynakları başka sayfalarla ortak; resim tek başına değiştirilemez.")
    else:
        rx, on = page.xref, "Resources/XObject/"
    yeni = doc.get_new_xref()
    doc.update_object(yeni, "<<>>")
    doc.xref_copy(xref, yeni)
    for ad in adlar:
        doc.xref_set_key(rx, on + ad, f"{yeni} 0 R")
    return yeni


def resmi_yerlestir(page, xref, yeni_rect, veri=None):
    """Resmi yeni kutuya taşır/boyutlandırır (veri verilirse onunla değiştirir). Yeni xref'i döner.
    veri, png_baytlari'ndan gelmeli (benzersiz olsun diye; bkz. png_baytlari)."""
    veri = veri or png_baytlari(resim_pil(page.parent, xref))
    page.delete_image(kendine_ayir(page, xref))
    return page.insert_image(yeni_rect, stream=veri, rotate=page.rotation, keep_proportion=False)


def resmi_sil(page, xref):
    page.delete_image(kendine_ayir(page, xref))


def arka_plani_temizle(im, tolerans=40, kenardan=True):
    """Düz renkli arka planı şeffaf yapar. Arka plan rengi kenar piksellerinden bulunur.
    kenardan=True: yalnız kenara bağlı bölge silinir (fotoğrafta nesnenin içindeki beyazlar kalır);
    False: o renge benzeyen her yer silinir (kağıttaki imza: harflerin içi de temizlenir)."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    im = im.convert("RGBA")
    rgb = im.convert("RGB")
    w, h = rgb.size
    kenar = ([rgb.getpixel((x, 0)) for x in range(0, w, max(1, w // 50))] +
             [rgb.getpixel((x, h - 1)) for x in range(0, w, max(1, w // 50))] +
             [rgb.getpixel((0, y)) for y in range(0, h, max(1, h // 50))] +
             [rgb.getpixel((w - 1, y)) for y in range(0, h, max(1, h // 50))])
    zemin = tuple(sorted(k[i] for k in kenar)[len(kenar) // 2] for i in range(3))  # kanal kanal ortanca
    fark = ImageChops.difference(rgb, Image.new("RGB", rgb.size, zemin)).split()
    uzaklik = ImageChops.lighter(ImageChops.lighter(fark[0], fark[1]), fark[2])  # en büyük kanal farkı
    benzer = uzaklik.point(lambda v: 255 if v <= tolerans else 0)
    if kenardan:
        # PIL'in doldurması saf Python: bağlı bölgeyi küçük kopyada bul, kenar ayrıntısını tam boyuttaki
        # 'benzer' maskesinden al (büyük fotoğrafta saniyeler yerine anında)
        o = min(1, 600 / max(w, h))
        dolu = benzer.resize((max(1, int(w * o)), max(1, int(h * o))), Image.NEAREST) if o < 1 else benzer.copy()
        kw, kh = dolu.size
        adim = max(1, min(kw, kh) // 40)
        tohumlar = ([(x, 0) for x in range(0, kw, adim)] + [(x, kh - 1) for x in range(0, kw, adim)] +
                    [(0, y) for y in range(0, kh, adim)] + [(kw - 1, y) for y in range(0, kh, adim)])
        for t in tohumlar:
            if dolu.getpixel(t) == 255:
                ImageDraw.floodfill(dolu, t, 128)
        bolge = dolu.point(lambda v: 255 if v == 128 else 0)
        if o < 1:  # büyüt, sınırı biraz genişlet; asıl kenarı 'benzer' belirler
            bolge = bolge.resize((w, h), Image.NEAREST).filter(ImageFilter.MaxFilter(int(3 / o) | 1))
        sil = ImageChops.darker(benzer, bolge)
    else:
        sil = benzer
    sil = sil.filter(ImageFilter.GaussianBlur(0.8))  # kenarlar tırtıklı olmasın
    alfa = ImageChops.multiply(im.getchannel("A"), ImageChops.invert(sil))
    im.putalpha(alfa)
    return im


def murekkep_ayir(im, hassasiyet=50):
    """Kaşe / imza fotoğrafından mürekkebi ayırır: kâğıt şeffaf olur, mürekkep kendi rengiyle kalır.
    Düz renk silmekten farkı: kâğıdın rengi her bölgede ayrı tahmin edilir (gölge, dengesiz ışık, kâğıt sarılığı
    silinir), mürekkep koyuluğuna göre yumuşak geçişle ayrılır (kenar tırtıklı olmaz) ve kenarlardaki beyaz
    karışım geri çıkarılır (beyaz hale kalmaz). hassasiyet 0-100: büyüdükçe soluk mürekkep de korunur."""
    import numpy as np
    from PIL import Image, ImageFilter
    rgb = im.convert("RGB")
    w, h = rgb.size
    # 1) kâğıdın yerel rengi: küçük kopyada mürekkebi "aydınlık en büyük" ile sil, yumuşat, büyüt
    o = min(1, 400 / max(w, h))
    kucuk = rgb.resize((max(1, int(w * o)), max(1, int(h * o))), Image.BILINEAR)
    # pencere: kaşe çizgisinden kalın (çizgi zemin sanılmasın), gölge geçişinden ince (köşede gölge kalmasın)
    k = max(3, int(min(kucuk.size) / 25) | 1)
    zemin = kucuk.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.GaussianBlur(k / 2)).resize((w, h), Image.BILINEAR)
    a = np.asarray(rgb, dtype=np.float32) / 255
    z = np.maximum(np.asarray(zemin, dtype=np.float32) / 255, 0.08)
    # 2) kâğıda göre düzeltilmiş görüntü (kâğıt = 1) ve mürekkep koyuluğu (en koyu kanal: mavi mürekkepte kırmızı)
    duz = np.clip(a / z, 0, 1)
    koyu = 1 - duz.min(axis=2)
    esik = 0.22 - hassasiyet / 100 * 0.19  # 0 → 0.22 (yalnız koyu mürekkep), 100 → 0.03 (soluk da)
    t = np.clip((koyu - esik) / 0.2, 0, 1)
    alfa = t * t * (3 - 2 * t)  # yumuşak geçiş: kenar tırtıklı olmasın
    # 3) beyaz haleyi çıkar: renk = kâğıtla karışmamış mürekkep rengi
    renk = np.clip(1 - (1 - duz) / np.maximum(alfa, 1 / 255)[..., None], 0, 1)
    sonuc = Image.fromarray(np.dstack([renk * 255, alfa * 255]).round().astype(np.uint8), "RGBA")
    # 4) toz / leke: tek tük pikseller gitsin — yalnız büyük resimde (küçükte ince harfleri aşındırır)
    if max(w, h) > 1000:
        sonuc.putalpha(sonuc.getchannel("A").filter(ImageFilter.MedianFilter(3)))
    return sonuc


def vurgula(page, rect):
    return isaretle(page, rect, "vurgu")


def not_ekle(page, nokta, metin):
    """Yapışkan not. İçerik açılır pencerede sistem yazı tipiyle gösterildiği için Türkçe sorunsuz."""
    a = page.add_text_annot(nokta, metin, icon="Comment")
    a.set_info(title=os.environ.get("USERNAME", ""))
    a.update()
    return a


def kalem(page, noktalar, renk=(0, 0, 1), kalinlik=2):
    a = page.add_ink_annot([[tuple(p) for p in noktalar]])
    a.set_colors(stroke=renk)
    a.set_border(width=kalinlik)
    a.update()
    return a


def sekil(page, tur, p1, p2, renk=(1, 0, 0), kalinlik=2):
    """tur: dikdortgen, daire, cizgi, ok. p1 → p2 yönü korunur (ok ucu p2'de)."""
    if tur in ("cizgi", "ok"):
        a = page.add_line_annot(p1, p2)
        if tur == "ok":
            a.set_line_ends(pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_OPEN_ARROW)
    else:
        r = pymupdf.Rect(p1, p2).normalize()
        a = page.add_rect_annot(r) if tur == "dikdortgen" else page.add_circle_annot(r)
    a.set_colors(stroke=renk)
    a.set_border(width=kalinlik)
    a.update()
    return a


def damga(page, rect, metin, renk=(0.8, 0, 0)):
    """Çerçeveli damga yazısı. Damga notu Türkçe harf çizemediği için sayfaya doğrudan çizilir."""
    sh = page.new_shape()
    sh.draw_rect(rect)
    sh.finish(color=renk, width=2.5)
    sh.commit()
    ic = rect + (4, 4, -4, -4)
    return yazi_ekle(page, ic, metin, max(6, min(36, ic.height * 0.6)), renk, hiza=1)


def not_bul(page, nokta):
    """Tıklanan noktadaki not (en üstteki)."""
    bulunan = [a for a in page.annots() if a.rect.contains(nokta)]
    return bulunan[-1] if bulunan else None


def karart(page, rects):
    """Kutulardaki her şeyi KALICI siler ve siyah boyar: yazı, resim pikselleri, çizimler,
    üstteki notlar ve form alanları. Sayfa genelinde bekleyen başka karartma işaretlerini de uygular."""
    rects = [pymupdf.Rect(r) for r in rects]
    degen = lambda r: any(r.intersects(k) for k in rects)
    for w in [w.xref for w in page.widgets() if degen(w.rect)]:
        page.delete_widget(page.load_widget(w))
    for a in [a.xref for a in page.annots() if degen(a.rect) and a.type[0] != pymupdf.PDF_ANNOT_REDACT]:
        page.delete_annot(page.load_annot(a))
    for r in rects:
        page.add_redact_annot(r, fill=(0, 0, 0))
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                          text=pymupdf.PDF_REDACT_TEXT_REMOVE)


def metni_karart(doc, metin):
    """Belgedeki tüm geçişleri karartır, kaç tane olduğunu döner."""
    bulunan = ara(doc, metin)
    for i in sorted({i for i, _ in bulunan}):
        karart(doc[i], [r for j, r in bulunan if j == i])
    return len(bulunan)


# ---------- formlar ----------
def xfa_formu_mu(doc):
    cat = doc.pdf_catalog()
    return bool(cat) and doc.xref_get_key(cat, "AcroForm/XFA")[0] != "null"


def form_alanlari(doc):
    """[(sayfa_no, widget)] — basma düğmeleri ve imza alanları hariç."""
    atla = (pymupdf.PDF_WIDGET_TYPE_BUTTON, pymupdf.PDF_WIDGET_TYPE_SIGNATURE)
    return [(i, w) for i in range(doc.page_count) for w in doc[i].widgets() if w.field_type not in atla]


def secenekler(w):
    """Açılır liste seçenekleri: [(kayit_degeri, gorunen)]."""
    return [(c[0], c[1]) if isinstance(c, (list, tuple)) else (c, c) for c in (w.choice_values or [])]


def form_doldur(doc, degerler):
    """degerler: {widget_xref: deger}. Onay/seçim kutusu için True/False.
    Helvetica'nın çizemediği harfleri (ş ğ ı İ) içeren değerler kalıcı yazıya çevrilir (alan silinir).
    Düzleştirilen alan adlarını döner."""
    duz = []
    for i in range(doc.page_count):
        page = doc[i]
        sonra = []
        for w in list(page.widgets()):
            if w.xref not in degerler:
                continue
            v = degerler[w.xref]
            if w.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                w.field_value = w.on_state() if v else "Off"
            else:
                v = "" if v is None else str(v)
                try:
                    v.encode("cp1252")
                except UnicodeEncodeError:
                    sonra.append((w.xref, w.field_name, pymupdf.Rect(w.rect), v))
                    continue
                w.field_value = v
            w.update()
        for xref, ad, rect, v in sonra:
            page.delete_widget(page.load_widget(xref))
            yazi_ekle(page, rect + (2, 1, -2, -1), v, max(6, min(11, rect.height * 0.65)))
            duz.append(ad)
    return duz


FORM_TURLERI = {"metin": pymupdf.PDF_WIDGET_TYPE_TEXT, "onay": pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
                "liste": pymupdf.PDF_WIDGET_TYPE_COMBOBOX}


def form_alani_ekle(doc, page, tur, rect, ad, secim=None):
    """Yeni form alanı. Ad belgede varsa sonuna sayı eklenir. Kullanılan adı döner."""
    var = {w.field_name for _, w in form_alanlari(doc)}
    ad = ad.strip() or tur
    aday, n = ad, 2
    while aday in var:
        aday, n = f"{ad}_{n}", n + 1
    w = pymupdf.Widget()
    w.field_type, w.field_name, w.rect = FORM_TURLERI[tur], aday, rect
    w.border_color, w.border_width, w.fill_color = (0.3, 0.3, 0.6), 1, (0.93, 0.95, 1)
    if tur == "liste":
        w.choice_values = secim or ["Seçenek 1"]
        w.field_value = w.choice_values[0]
    if tur == "metin":
        w.text_fontsize = 0  # kutuya göre otomatik
    page.add_widget(w)
    return aday



def degistir(page, rect, metin, boyut=11, hiza=0):
    """Alandaki her şeyi gerçekten siler (beyaz), yerine yeni metni yazar."""
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions()
    if metin:
        return yazi_ekle(page, rect, metin, boyut, hiza=hiza)
    return boyut


def sayfa_tasi(doc, i, yon):
    """yon -1: yukarı, +1: aşağı. Yeni sayfa numarasını döner."""
    return konuma_tasi(doc, i, i + yon) if 0 <= i + yon < doc.page_count else i


def konuma_tasi(doc, i, j):
    """i. sayfayı j. sıraya taşır (0'dan sayılır). Yeni sayfa numarasını (j) döner."""
    if i == j:
        return i
    if j < i:
        doc.move_page(i, j)
    else:  # move_page "şunun önüne" koyar
        doc.move_page(i, j + 1 if j + 1 < doc.page_count else -1)
    return j


def ara(doc, metin):
    """[(sayfa_no, Rect)] — PDF koordinatında."""
    return [(i, r) for i in range(doc.page_count) for r in doc[i].search_for(metin)]


def anlik_goruntu(doc):
    """Geri al için belgenin o anki hali. Şifreli belge şifreli kalır."""
    return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_KEEP)


def goruntuden_ac(veri, sifre=None):
    doc = pymupdf.open("pdf", veri)
    if doc.needs_pass:
        doc.authenticate(sifre or "")
    return doc


def aralik_cikar(doc, ilk, son, yol):
    yeni = pymupdf.open()
    yeni.insert_pdf(doc, from_page=ilk, to_page=son)
    guvenli_kaydet(yeni, yol)
    yeni.close()


def aralik_coz(metin, n):
    """'1-3, 5, 7-9' → [(0, 2), (4, 4), (6, 8)] (0'dan sayılır). Hatalıysa ValueError, Türkçe açıklamayla."""
    parcalar = []
    for p in metin.replace(";", ",").split(","):
        p = p.replace(" ", "")
        if not p:
            continue
        ilk, _, son = p.partition("-")
        if not ilk.isdigit() or (son and not son.isdigit()):
            raise ValueError(f"“{p}” anlaşılamadı. Örnek: 1-3, 5, 7-9")
        ilk, son = int(ilk), int(son or ilk)
        if not 1 <= ilk <= son <= n:
            raise ValueError(f"“{p}” geçersiz: sayfalar 1 ile {n} arasında olmalı ve başı sonundan büyük olmamalı.")
        parcalar.append((ilk - 1, son - 1))
    if not parcalar:
        raise ValueError("Hiç aralık yazılmadı.")
    return parcalar


def esit_parcalar(n, her):
    """Her 'her' sayfada bir bölme aralıkları."""
    return [(i, min(i + her, n) - 1) for i in range(0, n, her)]


def bol(doc, parcalar, klasor, ad):
    """Her aralığı ayrı dosyaya kaydeder: ad_3.pdf ya da ad_1-3.pdf. Kaydedilen yolları döner."""
    yollar = []
    for ilk, son in parcalar:
        yol = os.path.join(klasor, f"{ad}_{ilk + 1}.pdf" if ilk == son else f"{ad}_{ilk + 1}-{son + 1}.pdf")
        aralik_cikar(doc, ilk, son, yol)
        yollar.append(yol)
    return yollar


def birlestir(kaynaklar, cikti):
    """kaynaklar: dosya yolları ya da açık belgeler, bu sırayla tek dosyada birleşir. Toplam sayfa sayısını döner."""
    yeni = pymupdf.open()
    try:
        for k in kaynaklar:
            d = k if isinstance(k, pymupdf.Document) else pymupdf.open(k)
            try:
                if d.is_encrypted:  # şifresi açılmamış (açık belgede şifre girildiyse False olur)
                    raise ValueError(f"{os.path.basename(d.name or 'belge')} şifreli; önce şifresini açıp kaydedin.")
                yeni.insert_pdf(d)
            finally:
                if d is not k:
                    d.close()
        guvenli_kaydet(yeni, cikti)
        return yeni.page_count
    finally:
        yeni.close()


def word_e(doc, yol):
    """Word'ün kendi PDF dönüştürücüsüyle düzenlenebilir .docx yapar (bilgisayarda Word kurulu olmalı)."""
    import win32com.client
    with tempfile.TemporaryDirectory() as k:
        gecici = os.path.join(k, "kaynak.pdf")
        doc.save(gecici)  # kaydedilmemiş değişiklikler de girsin; asıl dosyaya dokunulmaz
        word = win32com.client.DispatchEx("Word.Application")  # ayrı örnek: kullanıcının açık Word'üne dokunmaz
        try:
            word.Visible = False
            word.DisplayAlerts = 0
            belge = word.Documents.Open(gecici, ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False)
            belge.SaveAs2(os.path.abspath(yol), FileFormat=16)  # wdFormatDocumentDefault
            belge.Close(False)
        finally:
            word.Quit(False)


def powerpoint_e(doc, yol, dpi=150):
    """Her sayfayı bir slayda resim olarak koyar (PowerPoint kurulu olmalı). Görünüm birebir korunur."""
    import win32com.client
    ilk = doc[0].rect
    # PowerPoint slayt kenarı 72–4032 punto (1–56 inç) olabilir: poster/küçük sayfa oranı korunarak sığdırılır
    o = min(4032 / max(ilk.width, ilk.height), max(1, 72 / min(ilk.width, ilk.height)))
    en, boy = ilk.width * o, ilk.height * o
    try:
        win32com.client.GetActiveObject("PowerPoint.Application")
        zaten_acik = True
    except Exception:
        zaten_acik = False
    with tempfile.TemporaryDirectory() as k:
        ppt = win32com.client.Dispatch("PowerPoint.Application")  # PowerPoint tek örnekli çalışır
        sunu = None
        try:
            sunu = ppt.Presentations.Add(WithWindow=False)
            sunu.PageSetup.SlideWidth, sunu.PageSetup.SlideHeight = en, boy
            for i, s in enumerate(doc):
                png = os.path.join(k, f"{i}.png")
                s.get_pixmap(dpi=dpi, annots=True).save(png)
                slayt = sunu.Slides.Add(i + 1, 12)  # ppLayoutBlank
                r = oranli_kutu(pymupdf.Rect(0, 0, en, boy), s.rect.width, s.rect.height)
                slayt.Shapes.AddPicture(png, False, True, r.x0, r.y0, r.width, r.height)
            sunu.SaveAs(os.path.abspath(yol), 24)  # ppSaveAsOpenXMLPresentation
        finally:
            if sunu is not None:
                sunu.Close()
            if not zaten_acik:
                ppt.Quit()  # kullanıcının açık PowerPoint'ine dokunma


def yazicilar():
    """(yazıcı adları, varsayılan yazıcı)."""
    import win32print
    adlar = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    try:
        varsayilan = win32print.GetDefaultPrinter()
    except Exception:
        varsayilan = adlar[0] if adlar else ""
    return adlar, varsayilan


def yazici_ozellikleri(yazici):
    """Yazıcının o anki ayarları ve yetenekleri: {"devmode", "kagitlar": [(no, ad)], "cift_taraf", "renkli"}."""
    import win32print as wp
    h = wp.OpenPrinter(yazici)
    try:
        bilgi = wp.GetPrinter(h, 2)
    finally:
        wp.ClosePrinter(h)
    port = bilgi["pPortName"]
    return {"devmode": bilgi["pDevMode"],
            "kagitlar": list(zip(wp.DeviceCapabilities(yazici, port, 2), wp.DeviceCapabilities(yazici, port, 16))),
            "cift_taraf": wp.DeviceCapabilities(yazici, port, 7) == 1, "renkli": wp.DeviceCapabilities(yazici, port, 32) == 1}


def ayarlari_uygula(yazici, devmode, hwnd=0, pencere=False, **alanlar):
    """devmode'a kagit (no), yon (1 dikey, 2 yatay), renk (1 s/b, 2 renkli), cift (1 tek, 2 uzun, 3 kısa kenar)
    yazar; pencere=True ise yazıcının kendi ayar penceresini açar. Tamam'a basıldıysa (ya da pencere yoksa) True."""
    import win32print as wp
    for ad, (alan, bayrak) in {"kagit": ("PaperSize", 0x2), "yon": ("Orientation", 0x1), "renk": ("Color", 0x800),
                               "cift": ("Duplex", 0x1000)}.items():
        if alanlar.get(ad):
            setattr(devmode, alan, alanlar[ad])
            devmode.Fields |= bayrak  # sürücü yalnızca işaretli alanları okur
    h = wp.OpenPrinter(yazici)
    try:  # sürücü kendi gizli ayarlarını da birleştirsin (DM_IN_BUFFER | DM_OUT_BUFFER [| DM_IN_PROMPT])
        sonuc = wp.DocumentProperties(hwnd, h, yazici, devmode, devmode, 2 | 8 | (4 if pencere else 0))
    finally:
        wp.ClosePrinter(h)
    return sonuc == 1  # IDOK


def yazdir(doc, yazici, sayfalar, kopya=1, ad="Polat PDF", dpi=300, dosya=None, devmode=None, dondur=True,
           sigdir=True):
    """Sayfaları resim olarak yazıcıya gönderir; devmode verilirse kâğıt/yön/renk/çift taraf ondan gelir.
    sigdir: kâğıdın yazdırılabilir alanına oranı korunarak sığdırılır (değilse gerçek boyut), ortalanır.
    dondur: yatay sayfa dik kâğıda (ya da tersi) döndürülerek basılır. Notlar ve işaretler de basılır."""
    import win32gui, win32ui
    from PIL import Image, ImageWin
    if devmode is None:
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(yazici)
    else:
        dc = win32ui.CreateDCFromHandle(win32gui.CreateDC("WINSPOOL", yazici, devmode))
    try:
        en, boy, yazici_dpi = dc.GetDeviceCaps(8), dc.GetDeviceCaps(10), dc.GetDeviceCaps(88)  # HORZRES, VERTRES, LOGPIXELSX
        dc.StartDoc(ad, dosya) if dosya else dc.StartDoc(ad)  # dosya: "Print to PDF" gibi yazıcıda kayıt yeri sormadan
        try:
            for _ in range(kopya):
                for i in sayfalar:
                    s = doc[i]
                    don = dondur and (s.rect.width > s.rect.height) != (en > boy)
                    sw, sh = (s.rect.height, s.rect.width) if don else (s.rect.width, s.rect.height)
                    # punto → yazıcı pikseli: alana sığacak kadar, ya da gerçek boyut (taşan kısım kesilir)
                    olcek = min(en / sw, boy / sh) if sigdir else yazici_dpi / 72
                    z = olcek * min(dpi, yazici_dpi) / yazici_dpi  # kâğıtta en fazla dpi çözünürlük: bellek şişmesin
                    pix = s.get_pixmap(matrix=pymupdf.Matrix(z, z).prerotate(90 if don else 0), annots=True)
                    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    w, h = int(sw * olcek), int(sh * olcek)
                    x, y = (en - w) // 2, (boy - h) // 2
                    dc.StartPage()
                    ImageWin.Dib(im).draw(dc.GetHandleOutput(), (x, y, x + w, y + h))
                    dc.EndPage()
            dc.EndDoc()
        except BaseException:
            dc.AbortDoc()  # yarım iş yazıcı kuyruğunda takılı kalmasın
            raise
    finally:
        dc.DeleteDC()


def guvenli_kaydet(doc, yol, **ayar):
    """Önce geçici dosyaya yazar, sonra yerine koyar: yarıda kalan kayıt dosyayı bozmaz.
    Açık dosyanın üstüne kaydediliyorsa geçici dosyanın yolunu döner; çağıran doc'u kapatıp yerine koyar.
    ayar: doc.save'e ek/üstün ayarlar (ör. şifre koymak / kaldırmak için encryption, user_pw)."""
    ayni = os.path.normcase(os.path.abspath(yol)) == os.path.normcase(os.path.abspath(doc.name or ""))
    fd, gecici = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(os.path.abspath(yol)))
    os.close(fd)
    try:
        try:
            doc.subset_fonts()  # gömülü Arial'in yalnızca kullanılan harfleri kalsın (~600 KB → birkaç KB)
        except Exception:
            pass  # fontTools yoksa dosya sadece büyük olur
        doc.save(gecici, **{"garbage": 4, "deflate": True, "encryption": pymupdf.PDF_ENCRYPT_KEEP, **ayar})  # şifre düşmesin
        if not ayni:
            os.replace(gecici, yol)
            gecici = None
        return gecici
    except BaseException:
        os.remove(gecici)
        raise


def sifre_ayari(sifre):
    """Şifre koymak (AES-256; açma ve sahip şifresi aynı) ya da sifre=None ile kaldırmak için kayıt ayarı."""
    if not sifre:
        return {"encryption": pymupdf.PDF_ENCRYPT_NONE}
    return {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "user_pw": sifre, "owner_pw": sifre}


def sikistir(doc, yol, seviye="orta", sifre=None):
    """Resimleri küçültüp yeniden sıkıştırarak kaydeder; açık belgeye dokunmaz. (önceki, sonraki) bayt döner.
    seviye: az (200 dpi), orta (150 dpi), cok (100 dpi) — ekranda okunur, yazıcıda da iyi çıkar."""
    import io
    from PIL import Image
    dpi, kalite = {"az": (200, 85), "orta": (150, 75), "cok": (100, 60)}[seviye]
    kopya = goruntuden_ac(anlik_goruntu(doc), sifre)
    try:  # shortcut: PyMuPDF rewrite_images bu sürümde resimlere dokunmuyor; elle küçültülüp JPEG yapılır
        gorulen = set()
        for s in kopya:
            for bilgi in s.get_image_info(xrefs=True):
                x, kutu = bilgi["xref"], pymupdf.Rect(bilgi["bbox"])
                if (not x or x in gorulen or kutu.is_empty or kopya.xref_get_key(x, "SMask")[0] != "null"
                        or kopya.xref_get_key(x, "Mask")[0] != "null"
                        or kopya.xref_get_key(x, "ImageMask")[1] == "true"):
                    continue  # şeffaf / maskeli resimler (imza, logo) olduğu gibi kalsın: JPEG'de kutu olurlar
                gorulen.add(x)
                pix = pymupdf.Pixmap(kopya, x)
                if pix.n - pix.alpha not in (1, 3):  # CMYK vb.
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                im = Image.frombytes("L" if pix.n == 1 else "RGB", (pix.width, pix.height), pix.samples)
                mevcut = max(pix.width, pix.height) / (max(kutu.width, kutu.height) / 72)  # döndürülmüşte de doğru
                o = min(1, dpi / mevcut)
                if o < 1:
                    im = im.resize((max(1, int(im.width * o)), max(1, int(im.height * o))), Image.LANCZOS)
                b = io.BytesIO()
                im.save(b, "JPEG", quality=kalite, optimize=True)
                if b.tell() < bilgi["size"]:  # yalnızca gerçekten küçülürse değiştir
                    s.replace_image(x, stream=b.getvalue())
        once = len(doc.tobytes(garbage=4, deflate=True, encryption=pymupdf.PDF_ENCRYPT_KEEP))  # normal kayıt boyutu
        guvenli_kaydet(kopya, yol, clean=True, use_objstms=1)
    finally:
        kopya.close()
    return once, os.path.getsize(yol)


def hedef_listesi(n, sayfalar):
    return sorted(set(sayfalar)) if sayfalar else list(range(n))


def sayfalari_dondur(doc, sayfalar, aci):
    for i in sayfalar:
        doc[i].set_rotation((doc[i].rotation + aci) % 360)


def sayfalari_sil(doc, sayfalar):
    if len(set(sayfalar)) >= doc.page_count:
        raise ValueError("Bütün sayfalar silinemez; en az bir sayfa kalmalı.")
    doc.delete_pages(sorted(set(sayfalar)))


def sayfalari_cikar(doc, sayfalar, yol):
    """Seçili sayfaları (sırasıyla) yeni bir PDF'e kaydeder."""
    yeni = pymupdf.open()
    try:
        for i in sorted(set(sayfalar)):
            yeni.insert_pdf(doc, from_page=i, to_page=i)
        guvenli_kaydet(yeni, yol)
    finally:
        yeni.close()


def bos_sayfa_ekle(doc, sonra):
    """sonra'daki sayfanın arkasına, onunla aynı boyutta boş sayfa ekler. Yeni sayfanın sırasını döner."""
    r = doc[sonra].rect
    doc.new_page(pno=sonra + 1, width=r.width, height=r.height)
    return sonra + 1


def _gorunur_kutuya_yaz(page, x0, y0, x1, y1, metin, boyut, hiza, renk=(0.25, 0.25, 0.25)):
    """Ekranda görülen sayfa koordinatındaki kutuya yazar (döndürülmüş sayfada da doğru yerde, düz okunur)."""
    while boyut >= 4:  # sığmazsa insert_textbox hiçbir şey yazmaz: sığana kadar küçült
        if page.insert_textbox(gorunumden(page, x0, y0, x1, y1), metin, fontsize=boyut, fontname=YAZI_ADI,
                               fontfile=YAZI_TIPI, color=renk, rotate=page.rotation, align=hiza) >= 0:
            return
        boyut -= 1
    raise ValueError(f"“{metin[:40]}” sayfa kenarına sığmıyor; daha kısa yazın.")


def ust_alt_bilgi(doc, sayfalar=None, filigran="", ust="", alt="", numara="", boyut=10, filigran_opaklik=0.15):
    """Seçili (yoksa bütün) sayfalara çapraz filigran, üst bilgi, alt bilgi ve sayfa numarası basar.
    numara: '' yok, ya da '{n}' / 'Sayfa {n} / {N}' gibi biçim (sağ alta yazılır)."""
    hedef = hedef_listesi(doc.page_count, sayfalar)
    font = pymupdf.Font(fontfile=YAZI_TIPI)
    for i in hedef:
        s = doc[i]
        en, boy, k = s.rect.width, s.rect.height, 28  # görünen boyut, kenar boşluğu
        if ust:
            _gorunur_kutuya_yaz(s, k, k / 2, en - k, k / 2 + boyut * 2, ust, boyut, 1)
        if alt:
            _gorunur_kutuya_yaz(s, k, boy - k / 2 - boyut * 2, en - k, boy - k / 2, alt, boyut, 1)
        if numara:
            yazi = numara.replace("{n}", str(i + 1)).replace("{N}", str(doc.page_count))
            _gorunur_kutuya_yaz(s, k, boy - k / 2 - boyut * 2, en - k, boy - k / 2, yazi, boyut, 2)
        if filigran:
            fs = min(en, boy) / max(4, len(filigran)) * 1.6  # sayfanın çaprazına sığacak kadar büyük
            uzunluk = font.text_length(filigran, fontsize=fs)
            merkez = pymupdf.Point(en / 2, boy / 2) * s.derotation_matrix
            aci = math.degrees(math.atan2(boy, en))  # sol alttan sağ üste
            s.insert_text(merkez - (uzunluk / 2, -fs / 3), filigran, fontsize=fs, fontname=YAZI_ADI,
                          fontfile=YAZI_TIPI, color=(0.6, 0.6, 0.6), fill_opacity=filigran_opaklik,
                          morph=(merkez, pymupdf.Matrix(aci + s.rotation)))
    return len(hedef)


def resimlerden_pdf(yollar, yol):
    """Her resmi (telefon fotoğrafı da) A4 sayfaya, oranı korunarak ve yönüne göre dik/yatay sayfaya koyar."""
    from PIL import Image, ImageOps
    yeni = pymupdf.open()
    try:
        for r in yollar:
            with Image.open(r) as im:
                im = ImageOps.exif_transpose(im)
                yatay = im.width > im.height
                veri = png_baytlari(im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB"))
            a4 = pymupdf.paper_rect("a4-l" if yatay else "a4")
            s = yeni.new_page(width=a4.width, height=a4.height)
            s.insert_image(a4 + (20, 20, -20, -20), stream=veri, keep_proportion=True)
        guvenli_kaydet(yeni, yol)
        return yeni.page_count
    finally:
        yeni.close()


def resimlere(doc, klasor, ad, bicim="png", dpi=150, sayfalar=None):
    """Sayfaları resim dosyası olarak kaydeder (ad_1.png, ...). Kaydedilen yolları döner."""
    yollar = []
    for i in hedef_listesi(doc.page_count, sayfalar):
        y = os.path.join(klasor, f"{ad}_{i + 1}.{bicim}")
        pix = doc[i].get_pixmap(dpi=dpi, annots=True)
        pix.save(y, jpg_quality=90) if bicim == "jpg" else pix.save(y)
        yollar.append(y)
    return yollar


TESSDATA = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "tessdata")


def taranmis_mi(page):
    """Sayfada seçilebilir yazı yok ama resim var: taranmış / fotoğraf sayfası."""
    return not page.get_text().strip() and bool(page.get_images())


def ocr_yap(doc, sayfalar=None, hepsi=False, ilerleme=None):
    """Yazısı olmayan sayfalardaki yazıyı (Türkçe + İngilizce) tanır ve sayfaya görünmez yazı olarak ekler:
    sayfa aynı görünür, ama arama, seçme ve kopyalama çalışır. hepsi=True: yazısı olan sayfalar da taranır.
    Tanınan sayfa sayısını döner."""
    hedef, font, n = hedef_listesi(doc.page_count, sayfalar), pymupdf.Font(fontfile=YAZI_TIPI), 0
    for k, i in enumerate(hedef):
        if ilerleme:
            ilerleme(k + 1, len(hedef))
        s = doc[i]
        if not hepsi and s.get_text().strip():
            continue
        donus = s.rotation
        s.set_rotation(0)  # döndürülmüş sayfada OCR yan duran görüntüyü okuyamaz: sayfanın kendi yönünde tanı
        try:
            bloklar = s.get_text("dict", textpage=s.get_textpage_ocr(language="tur+eng", dpi=300, full=True,
                                                                     tessdata=TESSDATA))["blocks"]
            ocr_yaz(s, bloklar, font)
        finally:
            s.set_rotation(donus)
        n += 1
    return n


def ocr_yaz(s, bloklar, font):
    """OCR sonucunu görünmez yazı olarak sayfaya yazar; her kelime kendi kutusunun genişliğine sığdırılır."""
    for b in bloklar:
        for l in b.get("lines", []):
            dx, dy = l["dir"]
            aci = round(math.degrees(math.atan2(-dy, dx)) / 90) * 90 % 360
            for sp in l["spans"]:
                metin = sp["text"].strip()
                if not metin:
                    continue
                kutu = pymupdf.Rect(sp["bbox"])
                en = kutu.width if aci in (0, 180) else kutu.height
                boyut = min(sp["size"] * 1.2, en / max(font.text_length(metin, fontsize=1), 0.01))
                s.insert_text(sp["origin"], metin, fontsize=max(boyut, 1), fontname=YAZI_ADI, fontfile=YAZI_TIPI,
                              render_mode=3, rotate=aci)  # 3: görünmez yazı (taramanın üstünde)


def kelimeleri_satirla(kelimeler):
    """get_text('words') kelimelerini sayfada göründükleri satırlara (yukarıdan aşağı, soldan sağa) dizer.
    PDF'te aynı satırdaki parçalar ayrı bloklarda olabilir; bu yüzden konuma göre gruplanır."""
    satirlar = []
    for k in sorted(kelimeler, key=lambda k: (k[1] + k[3]) / 2):
        orta = (k[1] + k[3]) / 2
        if satirlar and abs(orta - satirlar[-1][0]) < (k[3] - k[1]) / 2:
            satirlar[-1][1].append(k)
        else:
            satirlar.append([orta, [k]])
    return [sorted(v, key=lambda k: k[0]) for _, v in satirlar]


def hucre_degeri(metin):
    """'9.200,00' / '-1.234,5' / '56,15' → sayı (Excel'de hesaplanabilsin); vergi no, tarih, 0'la başlayan
    numaralar ve diğer her şey yazı olarak kalır."""
    import re
    m = (metin or "").strip()
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?|-?\d+,\d+", m):
        return float(m.replace(".", "").replace(",", "."))
    if re.fullmatch(r"-?[1-9]\d{0,8}", m):  # 10+ haneli (vergi/TC no, telefon) yazı kalsın: numaradır, tutar değil
        return int(m)
    return m


def excele(doc, yol, sayfalar=None):
    """Sayfalardaki tabloları Excel'e aktarır (her PDF sayfası bir çalışma sayfası). Tablo bulunamayan sayfada
    yazılar satır satır, aralarındaki geniş boşluklardan sütunlara bölünerek yazılır. Yazılan satır sayısını döner."""
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.utils import get_column_letter
    kitap = Workbook()
    kitap.remove(kitap.active)
    toplam = 0
    for i in hedef_listesi(doc.page_count, sayfalar):
        s, sayfa = doc[i], kitap.create_sheet(f"Sayfa {i + 1}")
        satirlar = []
        for t in s.find_tables().tables:
            satirlar += [[(h or "").replace("\n", " ") for h in r] for r in t.extract()] + [[]]
        if not satirlar:  # çizgisiz tablo (banka ekstresi vb.): geniş boşluk = yeni sütun
            for satir in kelimeleri_satirla(s.get_text("words")):
                hucreler, onceki = [], None
                for k in satir:
                    bosluk = (k[3] - k[1]) * 0.9  # yaklaşık iki harf
                    if onceki is not None and k[0] - onceki[2] < bosluk:
                        hucreler[-1] += " " + k[4]
                    else:
                        hucreler.append(k[4])
                    onceki = k
                satirlar.append(hucreler)
        for r in satirlar:
            # bozuk yazı tipi eşlemesindeki kontrol karakterlerini Excel kabul etmez, tüm aktarımı durdururdu
            sayfa.append([hucre_degeri(ILLEGAL_CHARACTERS_RE.sub("", h)) for h in r])
            for h in sayfa[sayfa.max_row]:
                if isinstance(h.value, str) and h.value.startswith("="):
                    h.data_type = "s"  # PDF'teki "=..." yazısı Excel'de çalışan formül olmasın (güvenlik)
        toplam += sum(1 for r in satirlar if r)
        for c, sutun in enumerate(sayfa.columns, start=1):  # sütun genişliği içeriğe göre
            sayfa.column_dimensions[get_column_letter(c)].width = min(60, max((len(str(h.value or "")) for h in sutun),
                                                                              default=8) + 2)
    kitap.save(yol)
    return toplam


YAZIYA_BAGLI = {"Highlight", "Underline", "StrikeOut", "Squiggly"}  # yazının üstünde durur, taşınmaz


def isaret_bul(page, nokta):
    """PDF koordinatındaki noktadaki en üstteki işaret (not, şekil, kalem, vurgu...). Yoksa None."""
    bulunan = None
    for a in page.annots():
        if a.type[1] != "Popup" and (a.rect + (-3, -3, 3, 3)).contains(nokta):  # Popup: notun görünmez kutusu
            bulunan = a.xref
    return bulunan


def isareti_tasi(page, xref, dx, dy):
    """İşareti dx, dy (PDF birimi) kadar taşır; rengi, kalınlığı, ok uçları, saydamlığı, yazarı korunur.
    Kalem ve çizgi işaretlerinin kutusu değiştirilemez: noktaları kaydırılmış olarak yeniden oluşturulur.
    İşaretin (yeni) xref'ini döner."""
    a = page.load_annot(xref)
    tur = a.type[1]
    if tur in YAZIYA_BAGLI:
        raise ValueError("Vurgu / altını çizme / üstünü çizme yazıya bağlıdır, taşınamaz (silinebilir).")
    if tur not in ("Ink", "Line", "Polygon", "PolyLine"):
        a.set_rect(a.rect + (dx, dy, dx, dy))
        a.update()
        return xref
    v, renk, kalinlik = a.vertices, a.colors, a.border.get("width", 1)
    uclar, opaklik, bilgi = a.line_ends, a.opacity, a.info
    kay = lambda p: (p[0] + dx, p[1] + dy)
    # önce yenisi: oluşturma hata verirse eski işaret kaybolmasın
    if tur == "Ink":
        yeni = page.add_ink_annot([[kay(p) for p in kol] for kol in v])
    elif tur == "Line":
        yeni = page.add_line_annot(kay(v[0]), kay(v[1]))
    else:
        yeni = getattr(page, f"add_{tur.lower()}_annot")([kay(p) for p in v])
    page.delete_annot(page.load_annot(xref))
    yeni.set_colors(stroke=renk.get("stroke"), fill=renk.get("fill") or None)
    yeni.set_border(width=kalinlik)
    if uclar and tur != "Ink":
        yeni.set_line_ends(*uclar)
    if opaklik is not None and opaklik >= 0:
        yeni.set_opacity(opaklik)
    yeni.set_info(bilgi)
    yeni.update()
    return yeni.xref


def belge_satirlari(doc):
    """[(sayfa, satır metni)] — sayfada göründüğü sırayla, boşluklar sadeleştirilmiş."""
    return [(i, " ".join(k[4] for k in satir)) for i, s in enumerate(doc)
            for satir in kelimeleri_satirla(s.get_text("words"))]


def karsilastir(eski, yeni):
    """İki belgenin yazısını satır satır karşılaştırır. [(tür, sayfa, metin)] döner:
    tür '-' eskide olup yenide olmayan (sayfa eski belgede), '+' yenide eklenen (sayfa yeni belgede)."""
    a, b = belge_satirlari(eski), belge_satirlari(yeni)
    farklar = []
    for tur, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [m for _, m in a], [m for _, m in b],
                                                        autojunk=False).get_opcodes():
        if tur != "equal":
            farklar += [("-", s, m) for s, m in a[i1:i2]] + [("+", s, m) for s, m in b[j1:j2]]
    return farklar


class KayitHatasi(Exception):
    """Kayıt yarıda kaldı ama belge kurtarıldı: .belge açık belgenin yerine kullanılmalı."""
    belge = None


def kaydet_ve_ac(doc, yol, sifre=None, **ayar):
    """Kaydeder ve kaydedilen dosyayı açık belge olarak döner."""
    gecici = guvenli_kaydet(doc, yol, **ayar)
    doc.close()
    if gecici:  # açık dosyanın üstüne: belge kapandı, artık yerine konabilir
        try:
            os.replace(gecici, yol)
        except OSError as e:  # dosya başka programda açık: belge kaybolmasın, geçici kopyadan geri açılır
            with open(gecici, "rb") as f:
                hata = KayitHatasi(f"{yol} başka bir program tarafından kullanılıyor, üstüne yazılamadı ({e}).\n\n"
                                   f"Değişiklikleriniz kaybolmadı; açık kalıyor ve şu dosyada da duruyor:\n{gecici}")
                hata.belge = goruntuden_ac(f.read(), sifre)
            raise hata
    yeni = pymupdf.open(yol)
    if yeni.needs_pass and sifre:
        yeni.authenticate(sifre)
    return yeni


# ---------- kendi kendini deneme ----------
def test():
    tr = "ğüşİıç Öde"
    metin = lambda s: s.get_text().replace("\xa0", " ")  # PyMuPDF boşluğu bölünmez boşluk olarak okuyor
    klasor = tempfile.mkdtemp()
    doc = pymupdf.open()
    for i in range(3):
        doc.new_page()
    s = doc[0]
    assert yazi_ekle(s, pymupdf.Rect(50, 50, 400, 100), tr) == 11
    assert tr in metin(s), metin(s)

    # döndürülmüş sayfada yazı, ekranda düz okunmalı ve tıklanan yere düşmeli
    s = doc[1]
    s.set_rotation(90)
    r = gorunumden(s, 50, 50, 500, 150)
    assert yazi_ekle(s, r, tr) is not None
    assert tr in metin(s)
    satir = s.get_text("dict")["blocks"][0]["lines"][0]
    m = pymupdf.Matrix(s.rotation_matrix)
    m.e = m.f = 0  # yön vektörü: kaydırma yok, sadece dönme
    yon = pymupdf.Point(satir["dir"]) * m
    assert abs(yon.x - 1) < 0.01 and abs(yon.y) < 0.01, yon  # ekranda soldan sağa
    kutu = pymupdf.Rect(satir["bbox"]) * s.rotation_matrix
    assert kutu.x0 >= 49 and kutu.y0 >= 49, kutu  # tıklanan köşenin içinde

    # arama: döndürülmüş sayfada bulunan kutu, ekranda yazının durduğu yere denk gelmeli
    bulunan = ara(doc, "Öde")
    assert [i for i, _ in bulunan] == [0, 1], bulunan
    g = gorunume(doc[1], bulunan[1][1])
    assert 49 <= g.x0 <= 500 and 49 <= g.y0 <= 150, g

    # değiştir: eski yazı gerçekten gider, yenisi gelir
    s = doc[0]
    assert degistir(s, pymupdf.Rect(45, 45, 405, 105), "Yeni tutar: 1.250 TL") is not None
    assert tr not in metin(s) and "1.250 TL" in metin(s)

    s = doc[2]
    vurgula(s, pymupdf.Rect(50, 50, 200, 80))
    assert s.first_annot.type[1] == "Highlight"

    # sayfa taşıma
    doc[2].insert_text((50, 300), "UCUNCU")
    assert sayfa_tasi(doc, 2, -1) == 1 and "UCUNCU" in doc[1].get_text()
    assert sayfa_tasi(doc, 1, 1) == 2 and "UCUNCU" in doc[2].get_text()
    assert sayfa_tasi(doc, 2, 1) == 2  # son sayfa aşağı gidemez
    assert konuma_tasi(doc, 2, 0) == 0 and "UCUNCU" in doc[0].get_text()
    assert konuma_tasi(doc, 0, 2) == 2 and "UCUNCU" in doc[2].get_text()
    assert konuma_tasi(doc, 2, 1) == 1 and "UCUNCU" in doc[1].get_text()
    konuma_tasi(doc, 1, 2)

    # geri al: anlık görüntüden aynı belge geri gelir
    once = anlik_goruntu(doc)
    doc.delete_page(0)
    geri = goruntuden_ac(once)
    assert geri.page_count == 3 and "1.250 TL" in metin(geri[0])
    geri.close()

    # kaydet, üstüne kaydet, aralık çıkar, birleştir
    yol = os.path.join(klasor, "a.pdf")
    doc = goruntuden_ac(once)
    doc.save(yol)
    doc.close()
    doc = pymupdf.open(yol)
    doc.delete_page(0)
    doc = kaydet_ve_ac(doc, yol)  # açık dosyanın üstüne
    assert doc.page_count == 2 and doc[0].rotation == 90 and tr in metin(doc[0])
    parca = os.path.join(klasor, "b.pdf")
    aralik_cikar(doc, 1, 1, parca)
    with pymupdf.open(parca) as p:
        assert p.page_count == 1 and "UCUNCU" in p[0].get_text()
        doc.insert_pdf(p, start_at=1)
    assert doc.page_count == 3
    doc = kaydet_ve_ac(doc, os.path.join(klasor, "c.pdf"))
    assert doc.page_count == 3 and os.path.exists(yol)
    doc.close()
    assert not [f for f in os.listdir(klasor) if f.startswith("tmp")], os.listdir(klasor)  # geçici dosya kalmasın
    assert os.path.getsize(os.path.join(klasor, "c.pdf")) < 100_000  # yazı tipi küçültüldü

    # resimler: arka plan temizleme
    from PIL import Image, ImageDraw
    foto = Image.new("RGB", (300, 200), (250, 250, 248))  # beyaza yakın kağıt
    ImageDraw.Draw(foto).ellipse((50, 25, 250, 175), fill=(200, 20, 30))
    ImageDraw.Draw(foto).ellipse((140, 90, 160, 110), fill=(250, 250, 248))  # nesnenin içinde beyaz nokta
    k = arka_plani_temizle(foto, 40, kenardan=True)
    assert k.getpixel((5, 5))[3] == 0 and k.getpixel((80, 100))[3] == 255 and k.getpixel((150, 100))[3] == 255
    g = arka_plani_temizle(foto, 40, kenardan=False)
    assert g.getpixel((5, 5))[3] == 0 and g.getpixel((150, 100))[3] == 0 and g.getpixel((80, 100))[3] == 255
    assert max(Image.open(__import__("io").BytesIO(png_baytlari(Image.new("RGB", (4000, 100))))).size) == RESIM_SINIRI

    # resim ekle, şeffaflık korunur, taşı/boyutlandır, sil
    foto_yolu = os.path.join(klasor, "foto.jpg")
    foto.save(foto_yolu)
    doc = pymupdf.open()
    s = doc.new_page()
    resim_ekle(s, pymupdf.Rect(100, 100, 400, 400), foto_yolu)
    r = resimler(s)
    assert len(r) == 1 and abs(r[0]["bbox"].width / r[0]["bbox"].height - 1.5) < 0.01, r
    x = resmi_yerlestir(s, r[0]["xref"], pymupdf.Rect(120, 120, 420, 320))  # aynı içerikle taşı: görünür kalmalı
    r = resimler(s)
    assert len(r) == 1 and r[0]["xref"] == x and r[0]["bbox"].x0 == 120, r
    x = resmi_yerlestir(s, r[0]["xref"], r[0]["bbox"], png_baytlari(k))  # arka planı temizlenmiş haliyle değiştir
    assert resim_pil(doc, x).getpixel((5, 5))[3] == 0 and resim_pil(doc, x).getpixel((80, 100))[3] == 255
    assert resim_bul(s, pymupdf.Point(200, 150))["xref"] == x and resim_bul(s, pymupdf.Point(50, 50)) is None
    x = resmi_yerlestir(s, x, pymupdf.Rect(50, 300, 200, 400))
    r = resimler(s)
    assert len(r) == 1 and r[0]["xref"] == x and abs(r[0]["bbox"].x0 - 50) < 0.5 and abs(r[0]["bbox"].x1 - 200) < 0.5
    assert resim_pil(doc, x).getpixel((5, 5))[3] == 0  # taşıyınca şeffaflık kaybolmadı
    s2 = doc.new_page()
    s2.insert_image(pymupdf.Rect(0, 0, 100, 100), xref=x)  # aynı resim başka sayfada da kullanılıyor
    s = doc[0]  # yeni sayfa eklenince eski sayfa nesnesi belgeden kopuyor
    diger = resimler(doc[1])[0]["bbox"]
    resmi_yerlestir(s, x, pymupdf.Rect(0, 0, 60, 40))  # ortak resim: yalnız bu sayfadaki taşınır
    assert resimler(doc[0])[0]["bbox"] == pymupdf.Rect(0, 0, 60, 40)
    assert resimler(doc[1])[0]["bbox"] == diger and len(resimler(doc[1])) == 1
    assert resim_pil(doc, x).getpixel((80, 100))[3] == 255  # diğer sayfadaki resim bozulmadı
    doc.new_page()
    y = resim_ekle(doc[2], pymupdf.Rect(100, 100, 200, 200), veri=png_baytlari(k))  # aynı resim 3. kez
    resmi_sil(doc[2], y)
    assert resimler(doc[2]) == [] and len(resimler(doc[1])) == 1 and len(resimler(doc[0])) == 1
    assert oranli_kutu(pymupdf.Rect(0, 0, 300, 300), 300, 200) == pymupdf.Rect(0, 0, 300, 200)

    # böl ve birleştir
    assert aralik_coz("1-3, 5,7-8", 10) == [(0, 2), (4, 4), (6, 7)]
    for hatali in ("0", "5-3", "11", "a", "2-x", ""):
        try:
            aralik_coz(hatali, 10)
            raise AssertionError(hatali)
        except ValueError:
            pass
    assert esit_parcalar(5, 2) == [(0, 1), (2, 3), (4, 4)] and esit_parcalar(3, 1) == [(0, 0), (1, 1), (2, 2)]
    kaynak = pymupdf.open()
    for i in range(5):
        kaynak.new_page().insert_text((72, 72), f"BOLUM{i + 1}")
    yollar = bol(kaynak, esit_parcalar(5, 2), klasor, "fatura")
    assert [os.path.basename(y) for y in yollar] == ["fatura_1-2.pdf", "fatura_3-4.pdf", "fatura_5.pdf"]
    with pymupdf.open(yollar[1]) as p:
        assert p.page_count == 2 and "BOLUM3" in p[0].get_text()
    cikti = os.path.join(klasor, "birlesik.pdf")
    assert birlestir([yollar[2], kaynak, yollar[0]], cikti) == 8  # dosya + açık belge + dosya, bu sırayla
    with pymupdf.open(cikti) as p:
        assert ["BOLUM5" in p[0].get_text(), "BOLUM1" in p[1].get_text(), "BOLUM2" in p[7].get_text()] == [True] * 3

    # şifreli PDF: kaydedince ve geri alınca şifresi düşmemeli
    y = os.path.join(klasor, "sifreli.pdf")
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "gizli")
    doc.save(y, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    doc.close()
    doc = pymupdf.open(y)
    doc.authenticate("x")
    an = anlik_goruntu(doc)
    doc.close()
    doc = goruntuden_ac(an, "x")
    assert doc.page_count == 1 and "gizli" in doc[0].get_text()
    doc = kaydet_ve_ac(doc, y, "x")
    assert birlestir([doc], os.path.join(klasor, "acik_sifreli.pdf")) == 1  # şifresi girilmiş açık belge birleşir
    doc.close()
    assert pymupdf.open(y).needs_pass
    try:
        birlestir([y], os.path.join(klasor, "olmaz.pdf"))
        raise AssertionError("şifreli dosya birleşmemeliydi")
    except ValueError as e:
        assert "şifreli" in str(e)

    # var olan yazıyı düzenleme: yer, boyut, renk, kalınlık korunur; arka plan ve komşu satır bozulmaz
    doc = pymupdf.open()
    s = doc.new_page()
    s.draw_rect(pymupdf.Rect(60, 80, 400, 140), color=None, fill=(0.85, 0.9, 1))
    s.insert_text((72, 100), "Tutar: 500 TL", fontsize=12, fontname="hebo", color=(0.8, 0, 0))
    s.insert_text((72, 113), "Alt satir burada", fontsize=12)
    l = satir_bul(s, pymupdf.Point(90, 95))
    assert satir_metni(l) == "Tutar: 500 TL" and satir_bul(s, pymupdf.Point(500, 500)) is None
    satir_degistir(s, l, "Tutar: 1.250,00 TL — ödendi")
    yeni = sorted(satirlar(s), key=lambda x: x["bbox"][1])
    assert [satir_metni(x).replace("\xa0", " ") for x in yeni] == ["Tutar: 1.250,00 TL — ödendi", "Alt satir burada"], yeni
    y0, e0 = yeni[0]["spans"][0], l["spans"][0]
    assert abs(y0["origin"][0] - 72) < 0.5 and abs(y0["origin"][1] - 100) < 0.5 and abs(y0["size"] - 12) < 0.1
    assert y0["color"] == e0["color"] and y0["flags"] & 16, y0  # kırmızı ve kalın kaldı
    assert s.get_pixmap(clip=pymupdf.Rect(300, 95, 301, 96)).pixel(0, 0) == (216, 229, 255)  # arka plan duruyor

    # karışık biçimli satır: kalın "1.1." kalın kalır, değişen normal kısım normal kalır
    s = doc.new_page()
    s.insert_text((72, 200), "1.1.", fontsize=10, fontname="hebo")
    s.insert_text((72 + pymupdf.get_text_length("1.1. ", "hebo", 10), 200), "Eski firma adi burada", fontsize=10)
    s.draw_line((300, 150), (300, 250))  # tablo sütun çizgisi: yazı bunu geçmemeli
    l = satir_bul(s, pymupdf.Point(150, 196))
    assert len(l["spans"]) == 2, l["spans"]
    satir_degistir(s, l, satir_metni(l).replace("Eski", "Yeni Şirket"))
    n = satir_bul(s, pymupdf.Point(150, 196))
    parca = {sp["text"].replace("\xa0", " ").strip(): bool(sp["flags"] & 16) for sp in n["spans"]}
    assert parca.get("1.1.") is True and parca.get("Yeni Şirket firma adi burada") is False, parca
    # sütun çizgisini aşacak kadar uzun metin sığdırılır
    l = satir_bul(s, pymupdf.Point(150, 196))
    satir_degistir(s, l, "1.1. " + "çok uzun bir metin " * 3)
    n = satir_bul(s, pymupdf.Point(100, 196))
    assert n["bbox"][2] <= 300, n["bbox"]

    # taşıma: seçilen satırlar biçimiyle birlikte yeni yere gider, eski yerde yazı kalmaz, arka plan kalır
    s = doc.new_page()
    s.draw_rect(pymupdf.Rect(60, 80, 400, 140), color=None, fill=(0.85, 0.9, 1))
    s.insert_text((72, 100), "Baslik kalin", fontsize=12, fontname="hebo", color=(0, 0, 0.8))
    s.insert_text((72, 115), "ikinci satir", fontsize=10)
    s.insert_text((72, 400), "yerinde kalan", fontsize=10)
    sec = kutudaki_satirlar(s, pymupdf.Rect(65, 85, 200, 118))
    assert len(sec) == 2, [satir_metni(x) for x in sec]
    satirlari_tasi(s, sec, 200, 300)
    assert satir_bul(s, pymupdf.Point(90, 96)) is None and satir_bul(s, pymupdf.Point(90, 112)) is None
    t = satir_bul(s, pymupdf.Point(290, 396))
    assert satir_metni(t).replace("\xa0", " ") == "Baslik kalin" and t["spans"][0]["flags"] & 16
    assert abs(t["spans"][0]["origin"][0] - 272) < 0.5 and abs(t["spans"][0]["origin"][1] - 400) < 0.5
    assert t["spans"][0]["color"] == sec[0]["spans"][0]["color"]
    assert satir_bul(s, pymupdf.Point(290, 411)) and satir_bul(s, pymupdf.Point(90, 396))  # diğerleri yerinde
    assert s.get_pixmap(clip=pymupdf.Rect(90, 95, 91, 96)).pixel(0, 0) == (216, 229, 255)

    # büyütme: sol üst köşe sabit, yazı boyutu ve satır aralığı 2 katına çıkar
    s = doc.new_page()
    s.insert_text((100, 100), "Kucuk yazi", fontsize=10)
    s.insert_text((100, 112), "ikinci", fontsize=10)
    sec = kutudaki_satirlar(s, pymupdf.Rect(95, 85, 300, 115))
    merkez = (min(l["bbox"][0] for l in sec), min(l["bbox"][1] for l in sec))
    satirlari_donustur(s, sec, olcek=2, merkez=merkez)
    b = sorted(satirlar(s), key=lambda x: x["bbox"][1])
    assert [round(x["spans"][0]["size"]) for x in b] == [20, 20], b
    # Helvetica → Arial: üst pay (ascender) farkı 20 puntoda ~3,4 birim
    assert abs(b[0]["bbox"][0] - merkez[0]) < 1 and abs(b[0]["bbox"][1] - merkez[1]) < 4, (b[0]["bbox"], merkez)
    assert abs(b[0]["spans"][0]["origin"][1] - donusmus((100, 100), olcek=2, merkez=merkez).y) < 0.5
    assert abs((b[1]["spans"][0]["origin"][1] - b[0]["spans"][0]["origin"][1]) - 24) < 0.5  # satır aralığı 12→24

    # sayfadan taşmış yazı: tamamı okunur ve geri çekilince eksiksiz döner, dışarıda kopyası kalmaz
    s = doc.new_page()
    s.insert_text((500, 100), "Bu yazi sayfadan tasiyor uzun", fontsize=14)
    l = satir_bul(s, pymupdf.Point(520, 96))
    assert satir_metni(l) == "Bu yazi sayfadan tasiyor uzun", satir_metni(l)
    satirlari_donustur(s, [l], kx=-300)
    hepsi = [satir_metni(x).replace("\xa0", " ") for x in satirlar(s)]
    assert hepsi == ["Bu yazi sayfadan tasiyor uzun"], hepsi
    assert satirlar(s)[0]["bbox"][2] < s.rect.width

    # hizalama: sağa yaslı tutarın sağ kenarı, ortalı başlığın ortası sabit kalır
    s = doc.new_page()
    s.insert_text((400, 100), "500,00 TL", fontsize=11)
    l = satir_bul(s, pymupdf.Point(420, 96))
    satir_degistir(s, l, "1.250.000,00 TL", hiza=2)
    n = satir_bul(s, pymupdf.Point(l["bbox"][2] - 5, 96))
    assert abs(n["bbox"][2] - l["bbox"][2]) < 1.5 and n["bbox"][0] < l["bbox"][0], (n["bbox"], l["bbox"])
    s.insert_text((250, 300), "BASLIK", fontsize=14)
    l = satir_bul(s, pymupdf.Point(260, 296))
    satir_degistir(s, l, "ÇOK DAHA UZUN BAŞLIK", hiza=1)
    n = satir_bul(s, pymupdf.Point((l["bbox"][0] + l["bbox"][2]) / 2, 296))
    assert abs((n["bbox"][0] + n["bbox"][2]) - (l["bbox"][0] + l["bbox"][2])) < 3, (n["bbox"], l["bbox"])
    # eklenen yazı kutu içinde sağa yaslanır
    yazi_ekle(s, pymupdf.Rect(100, 500, 400, 530), "Sağa", hiza=2)
    assert satir_bul(s, pymupdf.Point(390, 510))["bbox"][2] > 395

    # döndürülmüş sayfada: yeni yazı eskisiyle aynı yönde
    s = doc.new_page()
    s.set_rotation(90)
    yazi_ekle(s, gorunumden(s, 50, 50, 500, 100), "Eski metin")
    l = satirlar(s)[0]
    satir_degistir(s, l, "Yeni metin ğış")
    n = satirlar(s)[0]
    assert satir_metni(n).replace("\xa0", " ") == "Yeni metin ğış" and n["dir"] == l["dir"], (n["dir"], l["dir"])

    # işaretler, not, kalem
    doc = pymupdf.open()
    s = doc.new_page()
    s.insert_text((72, 100), "Fatura tutari 500 TL odenecek")
    a = isaretle(s, pymupdf.Rect(70, 85, 200, 105), "alti")
    assert a.type[1] == "Underline" and a.rect.x1 < 300  # kutu kadar değil, kelimeler kadar
    not_ekle(s, pymupdf.Point(300, 300), "Şükrü'ye sor")
    assert not_bul(s, pymupdf.Point(305, 305)).info["content"] == "Şükrü'ye sor"
    assert not_bul(s, pymupdf.Point(500, 700)) is None
    assert kalem(s, [(10, 10), (20, 30), (40, 20)]).type[1] == "Ink"

    # döndürülmüş sayfada ok: ekranda çizilen yönde kalmalı
    s = doc.new_page()
    s.set_rotation(90)
    a = sekil(s, "ok", noktadan(s, 50, 60), noktadan(s, 200, 60))
    v = [pymupdf.Point(p) * s.rotation_matrix for p in a.vertices]
    assert abs(v[0].x - 50) < 1 and abs(v[0].y - 60) < 1 and abs(v[1].x - 200) < 1, v
    assert damga(s, gorunumden(s, 100, 100, 300, 160), "ÖDENDİ") is not None
    assert "ÖDENDİ" in metin(s)

    # karartma sızıntı testi: sayfa yazısı, form değeri ve not, dosyanın ham içinde kalmamalı
    def icinde(b, gizli):
        return gizli in b or gizli.hex().encode() in b.lower()

    doc = pymupdf.open()
    s = doc.new_page()
    s.insert_text((72, 200), "GIZLI123")
    s.insert_text((300, 200), "ACIK456")
    w = pymupdf.Widget()
    w.field_type, w.field_name, w.rect, w.field_value = pymupdf.PDF_WIDGET_TYPE_TEXT, "f", pymupdf.Rect(70, 240, 300, 260), "GIZLIFORM"
    s.add_widget(w)
    not_ekle(s, pymupdf.Point(80, 280), "GIZLINOT")
    ham = lambda: doc.tobytes(garbage=4, deflate=False, expand=255)
    once = ham()
    assert all(icinde(once, g) for g in (b"GIZLI123", b"GIZLIFORM", b"GIZLINOT")), "kontrol: önce bulunmalı"
    karart(s, [pymupdf.Rect(60, 180, 140, 300)])
    sonra = ham()
    for g in (b"GIZLI123", b"GIZLIFORM", b"GIZLINOT"):
        assert not icinde(sonra, g), g
    assert "ACIK456" in metin(s)  # kutunun dışı kalır

    doc = pymupdf.open()
    s = doc.new_page()
    s.insert_text((72, 100), "Ahmet Yilmaz")
    s.insert_text((72, 300), "Imza: Yilmaz")
    assert metni_karart(doc, "Yilmaz") == 2 and "Yilmaz" not in doc[0].get_text()

    # formlar: Türkçe harfli değer kalıcı yazıya çevrilir, diğerleri form alanı kalır
    doc = pymupdf.open()
    s = doc.new_page()
    assert form_alani_ekle(doc, s, "metin", pymupdf.Rect(50, 50, 250, 72), "ad") == "ad"
    assert form_alani_ekle(doc, s, "metin", pymupdf.Rect(50, 80, 250, 102), "ad") == "ad_2"
    form_alani_ekle(doc, s, "onay", pymupdf.Rect(50, 110, 66, 126), "onay")
    form_alani_ekle(doc, s, "liste", pymupdf.Rect(50, 140, 250, 160), "secim", ["Evet", "Hayır"])
    assert not xfa_formu_mu(doc)
    x = {w.field_name: w.xref for _, w in form_alanlari(doc)}
    duz = form_doldur(doc, {x["ad"]: "Şükrü Işık", x["ad_2"]: "Müller Öç", x["onay"]: True, x["secim"]: "Evet"})
    assert duz == ["ad"], duz
    doc = pymupdf.open("pdf", doc.tobytes())
    s = doc[0]
    assert "Şükrü Işık" in metin(s), metin(s)
    kalan = {w.field_name: w.field_value for w in s.widgets()}
    assert "ad" not in kalan and kalan["ad_2"] == "Müller Öç" and kalan["secim"] == "Evet"
    assert kalan["onay"] not in ("Off", False, ""), kalan

    # 1.1: sıkıştırma, şifre, sayfa işleri, filigran, OCR, Excel sayıları
    import shutil
    k = tempfile.mkdtemp()
    try:
        d = pymupdf.open()
        s = d.new_page()
        s.insert_text((60, 100), "Gumruk beyannamesi 2026", fontsize=28)
        tarama = pymupdf.open()  # yazıyı resme çevir: taranmış sayfa
        tarama.new_page().insert_image(pymupdf.Rect(0, 0, 595, 842), pixmap=s.get_pixmap(dpi=200))
        assert taranmis_mi(tarama[0])
        assert ocr_yap(tarama) == 1 and tarama[0].search_for("beyannamesi"), "OCR (tessdata) çalışmadı: " + TESSDATA
        guvenli_kaydet(d, os.path.join(k, "s.pdf"), **sifre_ayari("x"))
        assert pymupdf.open(os.path.join(k, "s.pdf")).needs_pass
        once, sonra = sikistir(tarama, os.path.join(k, "k.pdf"), "cok")
        assert sonra < once, (once, sonra)
        e = pymupdf.open()
        for _ in range(3):
            e.new_page()
        sayfalari_dondur(e, [0, 2], 270)
        assert [p.rotation for p in e] == [270, 0, 270]
        bos_sayfa_ekle(e, 0)
        sayfalari_sil(e, [1])
        assert e.page_count == 3
        assert ust_alt_bilgi(e, filigran="KOPYADIR", numara="{n}/{N}") == 3 and "1/3" in e[0].get_text()
        assert [hucre_degeri(x) for x in ("9.200,00", "5581631660", "30")] == [9200.0, "5581631660", 30]
        # kaşe: gölgeli kâğıt şeffaf, mavi mürekkep kalır
        from PIL import Image as _I, ImageDraw as _D
        foto = _I.new("RGB", (400, 300))
        for x in range(400):  # soldan sağa koyulaşan gölge
            _D.Draw(foto).line([(x, 0), (x, 299)], fill=(int(240 - x * 0.3),) * 3)
        _D.Draw(foto).ellipse((120, 70, 280, 230), outline=(40, 60, 160), width=8)
        a = murekkep_ayir(foto).getchannel("A")
        assert a.getpixel((10, 10)) < 20 and a.getpixel((390, 290)) < 20, "gölge silinmedi"
        assert a.getpixel((124, 150)) > 200, "kaşe çizgisi kayboldu"
    finally:
        shutil.rmtree(k, ignore_errors=True)
    print("Tüm testler geçti.")


if __name__ == "__main__":
    test()
