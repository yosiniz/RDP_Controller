# rdpctl Kurulum Programlari (Yukleyiciler)

rdpctl artik her iki platform icin de **gercek, tikla-kur** kurulum programlariyla
dagitilir. Son kullanicinin Python, komut satiri ya da teknik bilgiye ihtiyaci
yoktur: tek bir dosya indirilir ve cift tiklanir.

| Platform | Dosya | Ne yapar | Ayrintili belge |
|----------|-------|----------|-----------------|
| Windows  | `rdpctl-setup.exe` | Sihirbazla **Program Files**'a kurar; **Baslat menusu** kisayolu ve **Programlar ve Ozellikler** kaydi ekler | [`win-yukleyici/README.md`](win-yukleyici/README.md) |
| macOS    | `rdpctl.dmg`       | Acilan pencereden rdpctl'i **Applications** klasorune suruklemek yeterli | [`macosx/README.md`](macosx/README.md) |

## Son kullanici: hangisini indirip nasil kurar?

### Windows
1. `rdpctl-setup.exe`'yi indir, cift tikla.
2. Imzasiz oldugu icin SmartScreen cikarsa: **"Ek bilgi" -> "Yine de calistir"**.
3. Sihirbazda **Ileri -> Kur -> Son**.
4. Uygulama **Baslat menusune** ve **Programlar ve Ozellikler** listesine eklenir.
   Kaldirmak icin oradan "Kaldir" ya da Baslat menusundeki **"rdpctl Kaldir"**.

### macOS
1. `rdpctl.dmg`'yi indir, cift tikla.
2. Acilan pencerede **rdpctl**'i **Applications** klasorune surukle.
3. Ilk acilista Gatekeeper icin: **sag tik -> "Ac"**.
4. **Sistem Ayarlari > Gizlilik ve Guvenlik** altinda **Ekran Kaydi** ve
   **Erisilebilirlik** izinlerini ver.

## Kurulum programlari nasil uretilir?

Her ikisi de **GitHub Actions** ile otomatik uretilir.

1. GitHub deposunda **Actions** sekmesine gidin.
2. Soldaki listeden **"Installers"** is akisini secin.
3. **Run workflow** butonuna basin (veya bir `v*` etiketi push edilince
   otomatik calisir).
4. Calisma bitince, calismanin en altindaki **Artifacts** bolumunden indirin:
   - `rdpctl-windows-installer` -> `rdpctl-setup.exe` (+ SHA256)
   - `rdpctl-macos-dmg` -> `rdpctl.dmg` (+ SHA256)

> Bir surum etiketi (orn. `v0.1.0`) push edildiginde bu dosyalar ayrica
> otomatik olarak bir GitHub **Release**'ine de yuklenir.

Yerelde elle uretmek icin ilgili klasorlerin README dosyalarina bakin:
- Windows: [`win-yukleyici/README.md`](win-yukleyici/README.md) (Inno Setup gerekir)
- macOS: [`macosx/README.md`](macosx/README.md) (`make_dmg.sh`, yalnizca Mac'te)
