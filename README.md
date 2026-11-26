# kanal-fabrikasi
Kıssa Kahvesi ve Tarih Sahnesi videolarını bilgisayar kapalıyken de paylaşan sistem.
- `kuyruk/<kanal>/` : kalite kontrolünden geçen video (`.mp4`) + bilgi (`.json`)
- `.github/workflows/paylas.yml` : her gün 17:23 (Berlin) en eski videoyu YouTube Shorts + Instagram Reels olarak paylaşır, `yayinlanan/` altına kaydeder, telefona ntfy bildirimi yollar.
Anahtarlar yalnızca GitHub Secrets'ta durur; depoda şifre yoktur.
