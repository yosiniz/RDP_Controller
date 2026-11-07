# macosx — macOS kurulum imaji (.dmg)

Bu klasor, rdpctl icin **surukle-birak** bir macOS kurulum imaji
(`rdpctl.dmg`) ureten betigi icerir.

- `make_dmg.sh` — `dist/rdpctl.app`'ten `rdpctl.dmg` uretir (yalnizca macOS'ta).
- `rdpctl.dmg` — (derleme ciktisi) son kullaniciya verilecek kurulum imaji.

## Ne yapar?

`make_dmg.sh`, icinde `rdpctl.app` ve `/Applications` klasorune bir kisayol
bulunan sikistirilmis bir disk imaji olusturur. Son kullanici `.dmg`'yi acinca
cikan pencerede uygulamayi **Applications** kisayoluna surukleyerek kurar.

> **Yalnizca macOS'ta calisir.** Betik `hdiutil`, `ditto` ve `ln` gibi Apple
> araclarini kullanir; Linux'ta calismaz. Linux ortaminda yalnizca `bash -n`
> ile sozdizimi dogrulanabilir.

## .dmg nasil uretilir?

### A) Otomatik (onerilen) — GitHub Actions

Depodaki **"Installers"** is akisi (`.github/workflows/build-installers.yml`)
bir macOS sunucusunda:

1. PyInstaller ile `dist/rdpctl.app`'i uretir,
2. `bash macosx/make_dmg.sh` ile `rdpctl.dmg`'yi olusturur,
3. ciktiyi **Artifacts** olarak yukler.

Calistirma: **Actions** sekmesi > **Installers** > **Run workflow** (ya da `v*`
etiketi push edilince otomatik). Bitince calismanin altindaki **Artifacts**
bolumunden `rdpctl-macos-dmg` indirilir.

### B) Elle — Mac uzerinde

```bash
# 1) Uygulamayi uret (dist/rdpctl.app olusur)
bash packaging/build_macos.sh

# 2) .dmg uret (macosx/rdpctl.dmg olusur)
bash macosx/make_dmg.sh
```

`dist/rdpctl.app` yoksa betik anlasilir bir hata verip durur.

## Son kullanici deneyimi

1. `rdpctl.dmg` dosyasini cift tiklar; bir pencere acilir.
2. Pencerede **rdpctl**'i **Applications** klasorune surukler.
3. Ilk acilista Gatekeeper, imzasiz uygulamayi engelleyebilir. Bunu asmak icin:
   Applications icinde **rdpctl**'e **sag tik -> "Ac"**, cikan uyarida tekrar
   **"Ac"**. (Bir kez yapildiktan sonra normal cift tikla acilir.)
4. rdpctl'in calismasi icin macOS izinleri gerekir:
   **Sistem Ayarlari > Gizlilik ve Guvenlik** altinda
   - **Ekran Kaydi** (ekran paylasimi icin) ve
   - **Erisilebilirlik** (uzaktan fare/klavye kontrolu icin)
   listelerinde rdpctl isaretlenir.
