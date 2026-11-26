"""Kuyruktaki en eski videoyu YouTube Shorts + Instagram Reels olarak paylasir.
Kuyruk: kuyruk/<kanal>/<ad>.mp4 + <ad>.json
json: {"ig_aciklama": str, "yt_baslik": str, "yt_aciklama": str, "yt_etiketler": [..], "kk_gecti": true,
       "durum": {"yt": null|"link", "ig": null|"id"}}
"""
import json, os, sys, time, glob, shutil, datetime, requests

KANALLAR = {"kissa": "KISSA", "tarih": "TARIH"}
DENEME = os.environ.get("DENEME") == "true"
REPO = os.environ.get("REPO", "")
BRANCH = "main"
rapor = []

def ntfy(baslik, mesaj, oncelik="default"):
    t = os.environ.get("NTFY_TOPIC")
    if not t:
        return
    try:
        requests.post(f"https://ntfy.sh/{t}", data=mesaj.encode(), timeout=15,
                      headers={"Title": baslik.encode("utf-8").decode("latin-1", "ignore"), "Priority": oncelik})
    except Exception as e:
        print("ntfy hata", e)

def yt_yukle(sfx, mp4, meta):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    rt = os.environ.get(f"YT_REFRESH_{sfx}")
    if not rt:
        return None, "YouTube anahtari yok"
    cr = Credentials(None, refresh_token=rt, client_id=os.environ["YT_CLIENT_ID"],
                     client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=cr, cache_discovery=False)
    body = {"snippet": {"title": meta["yt_baslik"][:100], "description": meta["yt_aciklama"][:4900],
                        "tags": meta.get("yt_etiketler", [])[:30], "categoryId": "27", "defaultLanguage": "tr"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(mp4, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtube.com/shorts/{resp['id']}", None

def ig_yukle(sfx, rel_yol, meta):
    tok, uid = os.environ.get(f"IG_TOKEN_{sfx}"), os.environ.get(f"IG_USER_{sfx}")
    if not tok or not uid:
        return None, "Instagram anahtari yok"
    url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{rel_yol}"
    g = "https://graph.facebook.com/v21.0"
    r = requests.post(f"{g}/{uid}/media", data={"media_type": "REELS", "video_url": url, "caption": meta["ig_aciklama"][:2200],
                                                "share_to_feed": "true", "access_token": tok}, timeout=60).json()
    if "id" not in r:
        return None, f"IG kap hatasi: {r}"
    cid = r["id"]
    for _ in range(40):
        time.sleep(15)
        s = requests.get(f"{g}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            return None, f"IG isleme hatasi: {s}"
    else:
        return None, "IG isleme zaman asimi"
    p = requests.post(f"{g}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60).json()
    return (p["id"], None) if "id" in p else (None, f"IG yayin hatasi: {p}")

def kanal_isle(kanal, sfx):
    metalar = sorted(glob.glob(f"kuyruk/{kanal}/*.json"))
    if not metalar:
        rapor.append(f"{kanal}: kuyrukta video yok")
        return
    mj = metalar[0]
    meta = json.load(open(mj, encoding="utf-8"))
    mp4 = mj[:-5] + ".mp4"
    ad = os.path.basename(mj[:-5])
    if not meta.get("kk_gecti") or not os.path.exists(mp4):
        rapor.append(f"{kanal}/{ad}: kalite kontrol onayi ya da video yok, paylasilmadi")
        return
    durum = meta.setdefault("durum", {"yt": None, "ig": None})
    if DENEME:
        rapor.append(f"{kanal}/{ad}: DENEME - paylasilacakti (yt={durum['yt']}, ig={durum['ig']})")
        return
    if not durum.get("ig"):
        sonuc, hata = ig_yukle(sfx, mp4, meta)
        durum["ig"] = sonuc
        if hata: rapor.append(f"{kanal}/{ad} IG: {hata}")
    if not durum.get("yt"):
        try:
            sonuc, hata = yt_yukle(sfx, mp4, meta)
        except Exception as e:
            sonuc, hata = None, f"YT hata: {e}"
        durum["yt"] = sonuc
        if hata: rapor.append(f"{kanal}/{ad} YT: {hata}")
    json.dump(meta, open(mj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if durum.get("yt") and durum.get("ig"):
        os.makedirs("yayinlanan", exist_ok=True)
        meta["paylasim_tarihi"] = datetime.date.today().isoformat()
        json.dump(meta, open(f"yayinlanan/{kanal}_{ad}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.remove(mj); os.remove(mp4)
        rapor.append(f"✅ {kanal}/{ad}: YouTube {durum['yt']} + Instagram tamam")
    else:
        rapor.append(f"⚠️ {kanal}/{ad}: kismi (yt={bool(durum.get('yt'))}, ig={bool(durum.get('ig'))}) - yarin eksik tamamlanir")

def yt_dogrula(sfx):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    rt = os.environ.get(f"YT_REFRESH_{sfx}")
    if not rt:
        return "anahtar yok"
    cr = Credentials(None, refresh_token=rt, client_id=os.environ["YT_CLIENT_ID"],
                     client_secret=os.environ["YT_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token")
    r = build("youtube", "v3", credentials=cr, cache_discovery=False).channels().list(part="snippet", mine=True).execute()
    return ", ".join(i["snippet"]["title"] for i in r.get("items", [])) or "kanal yok"

secim = os.environ.get("KANAL", "hepsi")
if DENEME:
    for k, s in KANALLAR.items():
        try:
            rapor.append(f"DENEME {k}: YouTube -> {yt_dogrula(s)} | Instagram anahtari {'var' if os.environ.get('IG_TOKEN_'+s) else 'yok'}")
        except Exception as e:
            rapor.append(f"DENEME {k}: YouTube HATA {e}")
for k, s in KANALLAR.items():
    if secim in ("hepsi", k):
        try:
            kanal_isle(k, s)
        except Exception as e:
            rapor.append(f"❌ {k}: {e}")
metin = "\n".join(rapor)
print(metin)
ntfy("Kanal paylasimi", metin, "high" if ("❌" in metin or "⚠️" in metin) else "default")
