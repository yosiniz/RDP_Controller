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

## Arayüz

Koyu, modern ve güven veren bir tasarım: degrade başlıklar, hover'da
yükselen kartlar, yumuşak renk geçişli yuvarlatılmış butonlar, nabız gibi
atan canlı durum göstergesi, bağlanırken dönen spinner, beliren oturum kodu
animasyonu, geri sayım çubuklu onay penceresi, "Kod kopyalandı" bildirimleri
ve kontrol sırasında ekranın üstünde "Sonlandır" butonlu uyarı bandı.
Tasarım sistemi `rdpctl/ui.py` içindedir (ek bağımlılık yok, saf Tkinter).

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

## Masaüstü uygulaması olarak kurulum (önerilen)

### macOS için hazır .app (derlemeye gerek yok)

GitHub Actions, her kod gönderiminde `rdpctl.app`'i **gerçek macOS
sunucularında** (hem Apple Silicon hem Intel) derler. Deponun **Actions**
sekmesi → "macOS Uygulamasi Derle" → en son çalışma → **Artifacts**:
`rdpctl-macos-apple-silicon` veya `rdpctl-macos-intel`. Adım adım kurulum
ve Gatekeeper/izin notları: **[HIZLI_BASLANGIC_MAC.txt](HIZLI_BASLANGIC_MAC.txt)**.



Aynı uygulamayı **iki bilgisayara da** kurarsınız. Açılışta her bilgisayar
rolünü seçer:

- Kontrol **edilecek** bilgisayar → "🖥 Bu bilgisayarı paylaş (Host)"
- Kontrol **eden** bilgisayar → "🔌 Başka bilgisayara bağlan (Controller)"

> **"Virüs" / "bilinmeyen yayımcı" uyarısı mı alıyorsunuz?** Bu, imzasız
> PyInstaller dosyalarında çok yaygın bir **yanlış pozitiftir**. Kalıcı çözüm
> (kod imzalama) ve tüm diğer adımlar için **[VIRUS_UYARISI_COZUM.md](VIRUS_UYARISI_COZUM.md)**
> dosyasına bakın. Derleme ayarları (UPX kapalı, sürüm bilgisi) bunu azaltmak
> için zaten düzenlendi; `set RDPCTL_ONEDIR=1` ile klasör dağıtımı da üretebilirsiniz.

### 1) Kurulum gerektirmeyen tek-dosya uygulamayı üretin

Her bilgisayarda **kendi işletim sistemine ait** betiği çalıştırın (tek
seferlik; Python ve derleme araçları yalnızca üreten makinede gerekir):

| İşletim sistemi | Komut | Çıktı |
|---|---|---|
| **Windows** | `packaging\build_windows.bat` (çift tık) | `dist\rdpctl.exe` |
| **macOS** | `bash packaging/build_macos.sh` | `dist/rdpctl.app` |
| **Linux** | `bash packaging/build_linux.sh` | `dist/rdpctl` |

Oluşan dosyayı (`rdpctl.exe` / `rdpctl.app` / `rdpctl`) ilgili bilgisayara
kopyalayıp **çift tıklamanız yeterli** — ayrı bir Python kurulumu gerekmez.

> **Windows:** `.exe`'yi oluşturmak için önce [python.org](https://www.python.org/downloads/)
> üzerinden Python 3.10+ kurun (kurulumda "Add to PATH" işaretli olsun).
> **macOS:** ilk çalıştırmada Sistem Ayarları → Gizlilik ve Güvenlik'ten
> **Ekran Kaydı** ve **Erişilebilirlik** izinlerini `rdpctl` için açın.
> **Linux:** X11/Wayland masaüstü ve `python3-tk` paketi gereklidir.

### 2) Bağlanma

1. **Host** bilgisayarda `rdpctl`'i açın → "Bu bilgisayarı paylaş"ı seçin.
   Pencerede bir **oturum kodu** ve **dinlenen adres** görünür.
2. Host'un **IP adresini** ve **oturum kodunu** karşı tarafa güvenli bir
   kanaldan (telefon, şifreli mesaj) iletin.
3. **Controller** bilgisayarda `rdpctl`'i açın → "Başka bilgisayara bağlan"ı
   seçin. **Ad, soyad**, host IP'si ve **oturum kodunu** girip "Bağlan"a basın.
4. Host ekranında onay penceresi çıkar; "Kabul Et" denince kontrol başlar.

> **Ağ:** İki bilgisayar aynı yerel ağdaysa host'un yerel IP'si (ör.
> `192.168.1.50`) yeterlidir. İnternet üzerinden bağlanılacaksa host'un
> bulunduğu yönlendiricide **7443** portunun host'a yönlendirilmesi
> (port forwarding) gerekir.

## Kaldırma (rdpctl-kaldir.exe)

Derleme betikleri uygulamanın yanında bir de **kaldırıcı** üretir:
`dist\rdpctl-kaldir.exe`. Çift tıklayınca bilgisayarı tarar ve eski
kurulumlardan kalanları listeler:

| Bulunan | Varsayılan |
|---|---|
| Çalışan rdpctl süreçleri (önce kapatılır) | seçili |
| Kurulum sihirbazıyla kurulmuş sürüm (kayıt defteri) | seçili |
| `rdpctl.exe` kopyaları (Masaüstü, İndirilenler, Belgeler, Program Files…) | seçili |
| Kısayollar ve Windows Güvenlik Duvarı kuralı | seçili |
| `%USERPROFILE%\.rdpctl` (TLS anahtarı, sertifika, günlükler) | seçili |
| Zip'ten çıkarılmış kaynak klasörleri | **seçili değil** |

- Denetim günlükleri silinmeden önce **Masaüstüne yedeklenir** (kapatılabilir;
  yedek alınamazsa ayarlar klasörü hiç silinmez).
- Silmeden önce onay istenir; yalnızca `rdpctl.exe` adlı dosyalar ve
  tanınan klasörler hedeflenir.
- Program Files veya güvenlik duvarı kuralı için "Yönetici olarak aç" butonu çıkar.

Komut satırı:

```bash
rdpctl-kaldir --list        # yalnızca listeler, hiçbir şey silmez
rdpctl-kaldir --silent      # varsayılan seçimlerle arayüzsüz kaldırır
```

## Geliştirici modu (paketlemeden çalıştırma)

Python kuruluysa doğrudan da çalıştırabilirsiniz:

```bash
pip install -r requirements.txt
python3 run_app.py              # rol seçim ekranıyla başlar
```

İsterseniz rolleri doğrudan da başlatabilirsiniz:

```bash
python3 run_app.py host         # veya: python3 run_host.py
python3 run_app.py controller   # veya: python3 run_controller.py
```

Host seçenekleri:

```bash
python3 run_host.py --port 7443 --fps 10 --max-width 1280 --quality 65 \
    --watch ~/Documents --watch ~/Desktop --audit ~/.rdpctl/audit.log
```

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
  app.py        Birleşik masaüstü başlatıcı (rol seçim ekranı)
  ui.py         Tasarım sistemi (tema, animasyonlu bileşenler)
  uninstall.py  Kaldırıcı mantığı (tarama, yedekleme, silme, CLI)
  uninstall_gui.py Kaldırıcı arayüzü
packaging/
  rdpctl.spec       PyInstaller tanımı (tek-dosya, penceresiz)
  rdpctl-kaldir.spec PyInstaller tanımı (kaldırıcı)
  version_app.txt / version_uninstall.txt  Windows sürüm bilgisi
  sign_windows.ps1  Kod imzalama yardımcısı (signtool)
  build_windows.bat Windows için rdpctl.exe + rdpctl-kaldir.exe üretir
  build_macos.sh    macOS için rdpctl.app üretir
  build_linux.sh    Linux için rdpctl ikili dosyası üretir
run_app.py      Masaüstü uygulaması giriş noktası (rol seçimi)
run_uninstall.py Kaldırıcı giriş noktası
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
