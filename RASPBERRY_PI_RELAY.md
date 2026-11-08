# Raspberry Pi'ye relay kurulumu

Relay saf Python (stdlib) olduğundan Raspberry Pi için idealdir: ARM'de
çalışır, çok az kaynak kullanır, 7/24 açık kalabilir. Bu rehber Pi'yi bir
kez kurar; **son kullanıcılar hiçbir şey yapmaz**, sadece uygulamayı açıp
kod girerler.

> **Önemli:** Pi evde, modemin arkasındadır. İki uzak kullanıcının ona
> ulaşması için Pi'nin **internetten erişilebilir** olması gerekir. Aşağıda
> ADIM 4'te iki yöntem var; birini **bir kez siz** yaparsınız.

---

## ADIM 1 — Pi'ye bağlan ve gerekli şeyleri kur

Pi'ye SSH ile girin (ya da klavye/ekran bağlayın), sonra:

```bash
sudo apt update && sudo apt install -y git python3
```

(Raspberry Pi OS'ta `python3` zaten gelir; `git` yoksa bu kurar.)

## ADIM 2 — Relay kodunu indir

```bash
sudo git clone https://github.com/yosiniz/RDP_Controller.git /opt/rdpctl
```

Relay ek bağımlılık istemez; `pip install` gerekmez.

## ADIM 3 — Servisi kur (otomatik başlatma + çökünce yeniden başlar)

```bash
sudo useradd -r -s /usr/sbin/nologin rdpctl 2>/dev/null || true
sudo cp /opt/rdpctl/packaging/rdpctl-relay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rdpctl-relay
```

Çalıştığını doğrula:

```bash
systemctl status rdpctl-relay --no-pager
ss -tlnp | grep 7444        # 0.0.0.0:7444 dinliyor olmalı
```

Bu noktada relay Pi üzerinde çalışıyor ama henüz sadece **yerel ağdan**
erişilebilir. İnternete açmak için ADIM 4.

## ADIM 4 — Pi'yi internete aç (BİRİNİ seç)

### Seçenek A — Modemde port yönlendirme + ücretsiz DNS (önerilen, kalıcı)

1. Pi'ye sabit bir yerel IP ver (modemin DHCP ayarından ya da Pi'de statik IP).
2. Modem arayüzünde **port yönlendirme**: dış **7444/TCP** → Pi'nin yerel IP'si **7444**.
3. Ev IP'niz değişebileceği için ücretsiz bir **dinamik DNS** alın
   (ör. [DuckDNS](https://www.duckdns.org) — ücretsiz). Size
   `seninad.duckdns.org` gibi bir adres verir ve ev IP'nizi güncel tutar.
   DuckDNS'in Pi için kurulum betiği vardır (5 dakika).
4. Relay adresiniz artık: `seninad.duckdns.org` (port 7444).

> Bu, **sizin** bir kez yaptığınız tek "port açma" işidir. Uygulamayı
> kullananlar hiçbir şey açmaz.

### Seçenek B — ngrok ile tünel (modeme dokunmadan)

Modem ayarına erişemiyorsanız, giden bağlantıyla tünel açan
[ngrok](https://ngrok.com) kullanın:

```bash
# ngrok'u kurup hesabınızın token'ını girdikten sonra:
ngrok tcp 7444
```

Size `tcp://1.tcp.ngrok.io:12345` gibi bir **genel adres + port** verir.
Relay adresiniz: `1.tcp.ngrok.io`, portunuz: `12345`.

> Ücretsiz ngrok'ta bu adres her yeniden başlatmada **değişir**; ücretli
> planda sabit kalır. Kalıcı çözüm için Seçenek A daha iyidir.

## ADIM 5 — Adresi uygulamalara tanıt

GitHub deposu → **Settings → Secrets and variables → Actions → Variables**
→ **New repository variable**:

- `RDPCTL_RELAY_HOST` = relay adresiniz (ör. `seninad.duckdns.org` veya ngrok host'u)
- (ngrok'ta port farklıysa) `RDPCTL_RELAY_PORT` = o port (ör. `12345`)

Sonra **Actions → "Installers" → Run workflow** ile `setup.exe` / `.dmg`
yeniden üretilir; bu kez relay adresi uygulamanın içine gömülür.

---

## Doğrulama

Pi çalışırken, başka bir ağdaki bir bilgisayardan (ör. mobil veri):

```bash
# relay adresinize TCP bağlantısı açılıyor mu?
nc -vz seninad.duckdns.org 7444
```

"succeeded/open" derse relay internetten erişilebilir demektir.

## Notlar

- **Bant genişliği:** Uzak kontrol trafiği Pi'nizin **ev internet
  yüklemesinden (upload)** geçer. Ara sıra destek için yeterli; sürekli/çok
  oturum için ev upload hızınız sınırlayıcı olabilir. O durumda küçük bir
  bulut sunucu (statik IP, NAT yok) daha rahattır — aynı adımlar geçerlidir.
- **Güvenlik:** Relay **zero-trust**'tır — host↔controller arası TLS'i
  göremez, sadece şifreli baytları aktarır. Yine de internete açık her
  servis gibi Pi'nizi güncel tutun; isterseniz `fail2ban` ekleyin.
- **Docker tercih ederseniz:** `packaging/relay.Dockerfile` ile de
  çalıştırabilirsiniz; ama Pi'de yukarıdaki systemd yöntemi daha hafiftir.

## Güncelleme

Relay kodunu güncellemek için:

```bash
sudo git -C /opt/rdpctl pull
sudo systemctl restart rdpctl-relay
```
