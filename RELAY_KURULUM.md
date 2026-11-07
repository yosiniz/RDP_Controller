# Relay (buluşma) sunucusu — kurulum ve "tıkla-çalıştır" bağlantı

Bu rehber **geliştirici içindir** (son kullanıcı için değil). Relay'i **bir
kez** kurarsınız; sonra uygulamayı kullanan herkes — teknolojiden hiç
anlamayan kişiler dahil — **aynı ağda olmadan ve hiçbir port açmadan**,
sadece **oturum kodu** ile bağlanır. IP yok, port yönlendirme yok.

## Neden gerekli?

İki bilgisayar farklı internet bağlantılarındayken birbirini doğrudan
göremez (NAT/güvenlik duvarı arkasındalar). Relay, ikisinin de **dışarı
doğru** bağlandığı ortak bir buluşma noktasıdır: oturum koduyla eşleştirir
ve aralarında baytları aktarır.

**Güvenlik:** Relay trafiği **göremez**. Host ile controller kendi uçtan
uca TLS'lerini relay'in aktardığı tünelin *içinden* kurar. Relay yalnızca
şifreli baytları geçirir; ekranı, girdiyi veya kimlikleri çözemez
(zero-trust aktarıcı). Oturum kodu relay'de yalnızca "hangi iki tarafı
eşleştireyim" anahtarıdır.

---

## 1) Relay'i bir sunucuya kurun

Küçük bir Linux VPS yeterli (en ucuz paket bile olur; relay çok hafiftir,
**hiç pip bağımlılığı yoktur**). Sadece **7444/tcp** portu internete açık
olmalı ve bir alan adınız (veya sabit IP'niz) olmalı.

### Seçenek A — Docker (önerilir)

```bash
git clone https://github.com/<kullanıcı>/RDP_Controller.git
cd RDP_Controller
docker build -f packaging/relay.Dockerfile -t rdpctl-relay .
docker run -d --name rdpctl-relay -p 7444:7444 --restart unless-stopped rdpctl-relay
```

### Seçenek B — Doğrudan Python (systemd ile)

```bash
git clone https://github.com/<kullanıcı>/RDP_Controller.git /opt/rdpctl
```

`/etc/systemd/system/rdpctl-relay.service`:

```ini
[Unit]
Description=rdpctl relay
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m rdpctl.relay --host 0.0.0.0 --port 7444
WorkingDirectory=/opt/rdpctl
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now rdpctl-relay
```

> **Güvenlik duvarı:** 7444/tcp'yi açın (ör. `ufw allow 7444/tcp`).
> **TLS sertifikası gerekmez:** Uçtan uca şifreleme host↔controller
> arasında zaten var; relay sadece baytları taşır.

Test: `nc -vz <relay-adresiniz> 7444` bağlanabiliyorsa relay ayakta.

---

## 2) Uygulamayı relay adresiyle derleyin

Uygulamanın relay'i bulması için **derleme sırasında** relay adresini
gömersiniz. GitHub Actions ile en kolayı:

1. GitHub'da deponun **Settings → Secrets and variables → Actions →
   Variables** sekmesine gidin.
2. **New repository variable** ile ekleyin:
   - `RDPCTL_RELAY_HOST` = `relay.alanadınız.com` (veya sabit IP)
   - (isteğe bağlı) `RDPCTL_RELAY_PORT` = `7444`
3. Dala push edin veya Actions'tan derlemeyi yeniden çalıştırın.

Workflow, `packaging/embed_relay.py` ile bu değeri `rdpctl/config.py` içine
gömer. Artık indirilen `rdpctl.exe` / `rdpctl.app` **relay modunda** açılır:
kullanıcıya IP/port sorulmaz.

> Değişkeni ayarlamazsanız uygulama eskisi gibi **doğrudan-IP (yerel ağ)**
> modunda çalışır; hiçbir şey bozulmaz.

### Yerelde derlerken

```bash
# macOS/Linux
export RDPCTL_RELAY_HOST=relay.alanadınız.com
bash packaging/build_macos.sh      # veya build_linux.sh
```

```bat
REM Windows
set RDPCTL_RELAY_HOST=relay.alanadiniz.com
packaging\build_windows.bat
```

(Betikler çalışmadan önce `python packaging/embed_relay.py` çağırmıyorsa,
derlemeden hemen önce elle çalıştırın; CI bunu otomatik yapar.)

---

## 3) Son kullanıcı deneyimi (tıkla-çalıştır)

1. Destek alacak kişi `rdpctl`'i açar → **"Bilgisayarımı Paylaş"** → ekranda
   bir **oturum kodu** görür. (IP/port yok; "🌐 İnternet üzerinden hazır".)
2. Kodu karşı tarafa söyler (telefon/mesaj).
3. Destek veren kişi `rdpctl`'i açar → **"Uzak Bilgisayara Bağlan"** →
   **ad, soyad ve kodu** girer → **Bağlan**.
4. Paylaşan tarafta onay penceresi çıkar → **İzin Ver** → bağlantı başlar.

Aynı ağ, port yönlendirme, IP — **hiçbiri gerekmez.**

---

## Ölçek / notlar

- Relay hafiftir ama tek örnek tek makinede çalışır; çok sayıda eşzamanlı
  oturum için birden fazla relay örneği + yük dengeleyici koyabilirsiniz
  (her oturum tek bir relay'e bağlı kalmalı).
- Oturum kodu çakışmasını relay `code_in_use` ile engeller; kodlar
  rastgele 9 hanedir.
- Eşleşme 60 sn içinde olmazsa host otomatik yeniden kaydolur.
- Relay IP başına eşzamanlı bağlantı sayısını sınırlar (kaba DoS koruması).
