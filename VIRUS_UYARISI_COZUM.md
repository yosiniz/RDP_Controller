# "Virüs" / "Bilinmeyen yayımcı" uyarısını giderme

Başka bir bilgisayara kurarken antivirüs veya Windows SmartScreen uyarı
veriyorsa, bu neredeyse her zaman bir **yanlış pozitiftir (false positive)**.

## Neden oluyor?

`rdpctl.exe`, Python kodunun PyInstaller ile paketlenmiş halidir. Bu tür
dosyalar üç nedenle uyarı alır — **içlerinde zararlı bir şey olduğu için
değil**:

1. **İmzasız:** Dosyanın doğrulanmış bir yayımcı kimliği (kod imzası) yok.
   Windows, imzasız her yeni programa "Bilinmeyen yayımcı" der.
2. **İtibarsız (SmartScreen):** Dosya yeni ve az indirilmiş. SmartScreen,
   henüz "yeterince çok kişi güvenle çalıştırmadı" dediği için uyarır.
3. **Paketleme sezgisi:** PyInstaller'ın tek-dosya önyükleyicisi, bazı
   antivirüslerin zararlı yazılımlarda da gördüğü bir kalıptır; motor
   "benzetme" yaparak işaretler.

> Önemli: Çözüm, dosyayı **gizlemek değildir**. Tam tersine, kimliğini ve
> güvenilirliğini **kanıtlamaktır**. Aşağıdaki adımların hepsi dosyayı daha
> tanınır ve doğrulanabilir yapar.

---

## Çözümler (en etkiliden başlayarak)

### 1) Kod imzalama — ASIL çözüm ⭐

Dosyaya, bir sertifika yetkilisi tarafından doğrulanmış yayımcı kimliğinizi
ekler. İmzalı dosyada "bilinmeyen yayımcı" yazmaz ve çoğu antivirüs güvenir.

1. Bir **Authenticode kod imzalama sertifikası** edinin (ör. DigiCert,
   Sectigo, SSL.com). Türü:
   - **OV (standart):** Daha ucuz; SmartScreen güveni indirme sayısıyla birikir.
   - **EV (genişletilmiş doğrulama):** Daha pahalı ama SmartScreen güvenini
     **anında** sağlar.
2. `rdpctl.exe` üretildikten sonra imzalayın:

   ```powershell
   .\packaging\sign_windows.ps1 -Pfx "C:\yol\sertifika.pfx" -Password "***"
   ```

   Bu betik `signtool` ile hem uygulamayı hem kaldırıcıyı imzalar ve zaman
   damgası ekler (`packaging/sign_windows.ps1`).

### 2) Yanlış pozitifi Microsoft'a ve antivirüslere bildirin

İmzalasanız bile ilk günlerde bir motor yanılabilir. Bildirmek ücretsizdir
ve genelde 1-3 günde düzeltilir:

- **Microsoft Defender:** https://www.microsoft.com/wdsi/filesubmission
  ("Yanlış pozitif — bir dosyayı yanlışlıkla engelliyor" seçeneği).
- Diğer motorlar için (Avast, Kaspersky, vb.) "false positive submission"
  sayfalarını kullanın. Dosyanızı önce https://www.virustotal.com adresinde
  tarayıp hangi motorların işaretlediğini görün.

### 3) Yapı tarafında yaptığımız iyileştirmeler (hazır)

Bu depodaki derleme ayarları yanlış pozitifi azaltmak için zaten düzenlendi:

- **UPX sıkıştırması kapatıldı** — en sık yanlış-pozitif tetikleyicilerinden.
- **Sürüm/üretici bilgisi eklendi** — `rdpctl.exe` artık Ayrıntılar
  sekmesinde sürüm ve açıklama gösterir (imzasız + bilgisiz dosyalar daha
  çok işaretlenir).
- **Klasör (onedir) dağıtımı seçeneği** — tek-dosya, çalışırken kendini
  geçici klasöre açtığı için bazı motorları tetikler. Klasör dağıtımı bunu
  yapmaz:

  ```bat
  set RDPCTL_ONEDIR=1
  packaging\build_windows.bat
  ```

  Bu, tek `.exe` yerine `dist\rdpctl\` klasörü üretir; o klasörü olduğu gibi
  kopyalayıp içindeki `rdpctl.exe`'yi çalıştırırsınız. Genelde daha az uyarı
  alır.

### 4) Güvenilir bir kanaldan dağıtın

Dosyayı e-posta ekiyle veya rastgele bağlantılarla değil, **GitHub Releases**
üzerinden yayımlayın. Bilinen bir kaynaktan indirme, SmartScreen itibarını
hızlandırır ve karşı tarafın güvenini artırır. Ayrıca yayımladığınız
dosyanın **SHA-256 özetini** paylaşın ki indiren kişi doğrulayabilsin:

```powershell
Get-FileHash dist\rdpctl.exe -Algorithm SHA256
```

---

## Son kullanıcı ne yapmalı? (imzalamaya hazır değilken geçici yol)

Siz henüz sertifika almadıysanız, **güvendiğiniz** kişi dosyayı şöyle
çalıştırabilir:

- **SmartScreen uyarısında:** "Ek bilgi" → "Yine de çalıştır".
- **Dosya özelliklerinde:** Sağ tık → Özellikler → altta "Engeli Kaldır"
  (Unblock) kutusu varsa işaretleyin → Uygula.

> Bunu yalnızca dosyayı **sizden, güvendiğiniz bir kaynaktan** aldıklarından
> emin olduklarında yapmalılar. Paylaştığınız SHA-256 özetiyle karşılaştırmak
> en güvenli yoldur. Bu adım bir güvenlik önlemini atlamaktır; kalıcı ve
> doğru çözüm **kod imzalamadır (1. madde)**.

---

## Özet

| Yöntem | Etki | Maliyet |
|---|---|---|
| Kod imzalama (EV) | Uyarıyı anında kaldırır | Ücretli, yıllık |
| Kod imzalama (OV) | Zamanla kaldırır | Ücretli, yıllık |
| Yanlış pozitif bildirimi | Belirli motoru düzeltir | Ücretsiz |
| UPX kapalı + sürüm bilgisi | Yanlış pozitifi azaltır | Ücretsiz (yapıldı) |
| Klasör (onedir) dağıtımı | Yanlış pozitifi azaltır | Ücretsiz (hazır) |
| GitHub Releases + SHA-256 | İtibar + doğrulanabilirlik | Ücretsiz |
