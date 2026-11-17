# Microsoft Store'da yayımlama rehberi

Amaç: Kullanıcılar rdpctl'i **Microsoft Store'dan** kursun. Böylece
"Windows kişisel bilgisayarınızı korudu / Bilinmeyen yayımcı" uyarısı çıkmaz
(paketi Microsoft imzalar) ve güncellemeleri Store otomatik yapar.

> Store yalnızca **Windows** içindir. Mac sürümü `.app` olarak devam eder.

---

## 1) Ücretsiz geliştirici hesabı aç (bir kez)
1. https://storedeveloper.microsoft.com adresine git → **Bireysel geliştirici
   olarak kaydol** (ücretsiz, kredi kartı gerekmez).
2. Microsoft hesabınla giriş yap, kimlik doğrulamayı tamamla.

## 2) Uygulama adını ayır
1. Partner Center → **Apps and games → + New product → MSIX or PWA app**.
2. Bir ad yaz (ör. `rdpctl` ya da daha anlaşılır bir ad, örn. `Güvenli Uzak Destek`)
   → **Reserve product name**. Ad başkası tarafından alınmışsa başka ad dene.

## 3) Ürün kimliği değerlerini al
Partner Center'da uygulamanın sayfası → **Product management → Product identity**.
Şu 3 değeri kopyala:

| Partner Center'daki alan | GitHub değişkeni |
|---|---|
| Package/Identity/Name | `MSIX_IDENTITY_NAME` |
| Package/Identity/Publisher (`CN=...` ile başlar) | `MSIX_PUBLISHER` |
| Package/Properties/PublisherDisplayName | `MSIX_PUBLISHER_DISPLAY_NAME` |

Ayrıca ayırdığın uygulama adını `MSIX_DISPLAY_NAME` olarak ekle.

## 4) Değerleri GitHub'a gir
https://github.com/yosiniz/RDP_Controller/settings/variables/actions →
**New repository variable** ile yukarıdaki 4 değişkeni ekle (birebir aynı yaz).

## 5) Paketi ürettir
Bir sonraki kod gönderiminde (ya da Actions → **Microsoft Store Paketi (MSIX)** →
Run workflow) paket üretilir. Çalışma bitince **Artifacts → rdpctl-store-msix**
içinden `rdpctl.msix`'i indir.

## 6) Gönderimi doldur (Partner Center → Start your submission)
- **Pricing and availability:** Free (Ücretsiz), tüm pazarlar.
- **Properties → Category:** Utilities & tools.
- **Privacy policy URL:**
  `https://github.com/yosiniz/RDP_Controller/blob/claude/upbeat-einstein-3z3sm1/PRIVACY.md`
- **Age ratings:** anketi doldur (şiddet/içerik yok → genelde "3+").
- **Packages:** `rdpctl.msix` dosyasını sürükle-bırak.
- **Store listings → Türkçe:** aşağıdaki metni kullan, ekran görüntüsü ekle
  (en az 1 adet, 1366x768 veya üzeri), uygulama logosu olarak
  `packaging/msix/Assets/StoreListing300.png`.
- **Submission options → Notes for certification** ve **runFullTrust gerekçesi**
  sorulursa şunu yaz:
  > Bu bir Win32 masaüstü uygulamasıdır. Kullanıcının açık onayıyla ekran
  > paylaşımı ve fare/klavye girişi için tam güven (runFullTrust) gerekir.
  > Test: Uygulamayı iki bilgisayarda açın; birinde "Bilgisayarımı Paylaş"
  > ile çıkan kodu diğerinde "Uzak Bilgisayara Bağlan" ekranına girin;
  > paylaşan tarafta "İzin Ver"e basın.

Gönder → Microsoft incelemesi genelde **birkaç gün** sürer. Onaylanınca uygulama
Store'da görünür.

## 7) Sonrası
- Kullanıcılar Store'da adı aratıp **Al / Yükle**'ye basar. Uyarı çıkmaz.
- Yeni sürüm için: kod gönder → yeni `rdpctl.msix` indir → Partner Center'da
  **Update** ile yeni gönderim yap. Sürüm numarası otomatik artar.
  Kullanıcılara güncelleme Store üzerinden otomatik gelir.

---

## Store açıklama metni (kopyala-yapıştır)

**Kısa açıklama:**
Güvenli, onay tabanlı uzaktan destek. Sadece kodla bağlanın; IP veya port ayarı gerekmez.

**Açıklama:**
rdpctl ile başka bir bilgisayara güvenle uzaktan destek verebilir ya da destek alabilirsiniz.

• Sadece kodla bağlantı: Aynı ağda olmanıza veya port açmanıza gerek yok.
• Onaysız bağlanılamaz: Ekranı paylaşılan kişi, kimin bağlandığını (ad-soyad) görür ve "İzin Ver" demeden bağlantı başlamaz.
• Her zaman görünür: Bağlantı süresince ekranda uyarı bandı durur, tek tıkla sonlandırılır.
• Uçtan uca şifreli: Tüm trafik TLS ile şifrelenir.
• Tam kayıt: Bağlantılar, girdiler ve dosya değişiklikleri kurcalamaya karşı korumalı bir günlüğe yazılır.

**Özellikler (Features):**
- Kodla internet üzerinden bağlantı
- Açık onay ve kimlik gösterimi
- Uçtan uca TLS şifreleme
- Kurcalamaya dayanıklı denetim günlüğü
- Türkçe arayüz
