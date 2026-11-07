# win-yukleyici — Windows kurulum programi (setup.exe)

Bu klasor, rdpctl icin **tikla-kur** bir Windows kurulum programi (`rdpctl-setup.exe`)
ureten [Inno Setup](https://jrsoftware.org/isinfo.php) betigini icerir.

- `rdpctl.iss` — Inno Setup betigi. Derlendiginde `rdpctl-setup.exe` uretir.
- `rdpctl-setup.exe` — (derleme ciktisi) son kullaniciya verilecek kurulum programi.

## Ne yapar?

`rdpctl-setup.exe` bir kurulum sihirbazidir. Son kullanici cift tiklar,
"Ileri -> Ileri -> Kur" adimlariyla:

- `rdpctl.exe` (uygulama) ve `rdpctl-kaldir.exe` (kaldirici) `C:\Program Files\rdpctl`
  altina kopyalanir,
- **Baslat menusune** `rdpctl` ve `rdpctl Kaldir` kisayollari eklenir,
- istege bagli olarak **masaustune** kisayol eklenir,
- **Programlar ve Ozellikler** (Denetim Masasi > Program kaldir) listesine
  `rdpctl 0.1.0` kaydi eklenir; buradan da kaldirilabilir.

## setup.exe nasil uretilir?

### A) Otomatik (onerilen) — GitHub Actions

Depodaki **"Installers"** is akisi (`.github/workflows/build-installers.yml`)
Windows sunucusunda su adimlari yapar:

1. PyInstaller ile `dist\rdpctl.exe` ve `dist\rdpctl-kaldir.exe` uretir,
2. Inno Setup'i kurar ve `iscc win-yukleyici\rdpctl.iss` ile `rdpctl-setup.exe`'yi derler,
3. ciktiyi **Artifacts** olarak yukler (SHA256 ozetiyle birlikte).

Calistirma: GitHub deposunda **Actions** sekmesi > **Installers** > **Run workflow**
(ya da `v*` etiketi push edilince otomatik). Bitince calismanin altindaki
**Artifacts** bolumunden `rdpctl-windows-installer` indirilir.

### B) Elle — Windows uzerinde

1. [Inno Setup](https://jrsoftware.org/isdl.php) Compiler'i kurun.
2. Uygulamalari uretip `dist\` klasorunu doldurun:
   ```bat
   pyinstaller --noconfirm packaging\rdpctl.spec
   pyinstaller --noconfirm packaging\rdpctl-kaldir.spec
   ```
3. `win-yukleyici\rdpctl.iss` dosyasini Inno Setup Compiler ile acip derleyin
   (veya komut satiri: `iscc win-yukleyici\rdpctl.iss`).
4. `win-yukleyici\rdpctl-setup.exe` olusur.

> `dist\` klasoru farkli bir konumdaysa derleyiciye bildirebilirsiniz:
> `iscc /DSourceDir=C:\tam\yol\dist win-yukleyici\rdpctl.iss`

## Son kullanici deneyimi

1. `rdpctl-setup.exe`'yi cift tiklar.
2. Imzasiz oldugu icin Windows **SmartScreen** uyarisi cikabilir:
   **"Ek bilgi" -> "Yine de calistir"** ile devam edilir. (Program Files'a
   kurulum icin Windows yonetici izni de isteyebilir.)
3. Sihirbazda "Ileri -> Kur -> Son" ile kurulum tamamlanir.
4. Uygulama **Baslat menusunden** acilir; istenirse masaustu kisayolundan.
5. Kaldirmak icin: **Programlar ve Ozellikler** listesinden `rdpctl` ->
   "Kaldir", ya da Baslat menusundeki **"rdpctl Kaldir"** kisayolu.

## Notlar

- Kurulum varsayilan olarak **tum kullanicilar** icin (Program Files, yonetici
  izni) yapilir. Yoneticisiz, yalnizca gecerli kullanici icin kurulum isteyen
  bir alternatif `rdpctl.iss` icinde yorum olarak belgelenmistir.
- Arayuz varsayilan olarak Ingilizce'dir; Turkce sihirbaz icin gereken adim
  (`Turkish.isl`) yine `rdpctl.iss` icinde yorum olarak aciklanmistir.
