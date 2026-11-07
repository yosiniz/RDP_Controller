# RDP_Controller (rdpctl)

AnyDesk/TeamViewer tarzı, **onay (consent) tabanlı** güvenli uzaktan
destek/kontrol uygulaması. Bir bilgisayarın ekranını görüp fare/klavyesini
uzaktan kontrol etmeyi sağlar — ancak **yalnızca kontrol edilen makinenin
başındaki kişinin açık izniyle**.

> ⚠️ **Etik ve yasal kullanım.** Bu araç, kullanıcısının bilgisi ve rızası
> olan bilgisayarlarda (kendi makineleriniz, izinli IT destek, yetkili
> yönetim) kullanılmak üzere tasarlanmıştır. Tasarımı bilerek **şeffaftır**:
> bağlantı gizlenemez, kontrol edilen kişiye her zaman görünür ve her işlem
> kaydedilir. Birinin haberi/izni olmadan bilgisayarını izlemek veya kontrol
> etmek çoğu ülkede suçtur.

## Güvenlik özellikleri

| Özellik | Açıklama |
|---|---|
| **Zorunlu kimlik** | Controller giriş yaparken **ad ve soyad** girmek zorundadır; bu isim host'ta onay penceresinde ve tüm günlüklerde görünür. |
| **Oturum kodu** | Host her başlatıldığında rastgele kod üretir; controller bunu bilmeden el sıkışamaz. Kod sabit-zamanlı karşılaştırılır. |
| **Açık onay** | Kod doğru olsa bile, host'un başındaki kişi "Kabul Et" demeden kontrol **başlamaz** (60 sn içinde yanıt yoksa reddedilir). |
| **Kalıcı uyarı bandı** | Kontrol boyunca host ekranının üstünde kırmızı "UZAKTAN KONTROL AKTİF — <isim>" bandı durur. |
| **Anında kesme** | Host "Bağlantıyı Kes" ile oturumu her an sonlandırabilir. |
| **TLS şifreleme** | Tüm trafik TLS 1.2+ ile şifrelenir. Host sertifika parmak izini gösterir; MITM'e karşı karşılaştırılabilir. |
| **Brute-force koruması** | IP başına hatalı kod denemeleri kilitlenir. |
| **Kurcalanamaz denetim günlüğü** | Her kayıt bir öncekinin SHA-256 hash'ini içerir (hash zinciri); sonradan değiştirme tespit edilir. |
| **Dosya değişikliği kaydı** | Oturum boyunca izlenen klasörlerdeki dosya oluşturma/değiştirme/silme/taşıma olayları kaydedilir. |

## Kurulum

```bash
pip install -r requirements.txt
```

> Not: Ekran yakalama ve girdi enjeksiyonu için grafik oturumu (X11/Wayland,
> Windows masaüstü veya macOS) gerekir. Başsız (headless) sunucuda GUI
> açılmaz. macOS'ta ayrıca "Erişilebilirlik" ve "Ekran Kaydı" izinleri
> verilmelidir.

## Kullanım

**Kontrol EDİLEN bilgisayarda (host):**

```bash
python3 run_host.py
```

Pencerede görünen **oturum kodunu** karşı tarafa güvenli bir kanaldan iletin.

Seçenekler:

```bash
python3 run_host.py --port 7443 --fps 10 --max-width 1280 --quality 65 \
    --watch ~/Documents --watch ~/Desktop --audit ~/.rdpctl/audit.log
```

**Kontrol EDEN bilgisayarda (controller):**

```bash
python3 run_controller.py --host 192.168.1.50
```

Açılan formda **ad, soyad**, host adresi ve **oturum kodunu** girin, "Bağlan"a
tıklayın. Host onayladığında uzak ekran görüntülenir.

## Denetim günlüğünü inceleme

```bash
python3 view_log.py ~/.rdpctl/audit.log            # tüm olaylar
python3 view_log.py ~/.rdpctl/audit.log --changes  # yalnız dosya değişiklikleri
python3 view_log.py ~/.rdpctl/audit.log --verify   # kurcalama kontrolü
```

## Mimari

```
rdpctl/
  protocol.py   Mesaj çerçeveleme (4 bayt uzunluk + JSON) ve TLS yardımcıları
  auth.py       Ad/soyad doğrulama, oturum kodu, brute-force sınırlayıcı
  audit.py      Hash-zincirli kurcalanamaz denetim günlüğü
  fswatch.py    Dosya değişikliği izleyici (watchdog)
  host.py       Kontrol edilen makine ajanı (onay + banner + yayın + enjeksiyon)
  controller.py Kontrol eden istemci (giriş + görüntüleme + girdi gönderimi)
```

Tel protokolü: her mesaj `[4 bayt big-endian uzunluk][UTF-8 JSON gövde]`.
Ekran kareleri JPEG olarak base64 ile JSON içinde taşınır; taşıma TLS olduğu
için gövde zaten şifrelidir.

## Sınırlamalar / yol haritası

- Tek eşzamanlı oturum (host meşgulken yeni bağlantı reddedilir).
- Dosya aktarımı ve pano paylaşımı henüz yok.
- Kare kodlaması JPEG (basit); üretim için H.264/delta kodlama düşünülebilir.
- NAT arkasında doğrudan IP erişimi gerekir (STUN/relay yok).

## Lisans

Dahili/eğitim amaçlı. Yürürlükteki gizlilik ve bilişim yasalarına uyarak kullanın.
