# rdpctl — Gizlilik Politikası

Son güncelleme: Kasım 2026

rdpctl, iki bilgisayar arasında **onay tabanlı** uzaktan destek sağlayan bir
uygulamadır. Bu belge hangi verilerin nasıl işlendiğini açıklar.

## Geliştirici hiçbir kişisel veri toplamaz
rdpctl'in geliştiricisi kullanıcılardan veri toplamaz, saklamaz, satmaz veya
üçüncü taraflarla paylaşmaz. Uygulamada reklam, analitik veya izleme yoktur.

## Uygulamanın işlediği veriler
| Veri | Nerede | Amaç |
|---|---|---|
| Bağlanan kişinin **adı ve soyadı** | Yalnızca iki taraf arasında iletilir; paylaşan bilgisayarın yerel denetim günlüğüne yazılır | Paylaşan kişinin kimin bağlandığını görüp onay vermesi |
| **Ekran görüntüsü**, fare ve klavye olayları | Yalnızca oturum süresince, iki taraf arasında | Uzaktan destek |
| **Denetim günlüğü** (bağlantılar, girdiler, dosya değişiklikleri) | Yalnızca paylaşan bilgisayarda, kullanıcının kendi klasöründe (`.rdpctl`) | Güvenlik ve şeffaflık; kullanıcı istediği zaman silebilir |

## Şifreleme ve aktarma sunucusu
İki bilgisayar, internet üzerinden bir aktarma (relay) sunucusu aracılığıyla
buluşur. Tüm trafik iki taraf arasında **uçtan uca TLS ile şifrelenir**; aktarma
sunucusu içeriği okuyamaz ve hiçbir veriyi kaydetmez.

## Onay
Paylaşan bilgisayarın kullanıcısı açıkça **"İzin Ver"** demeden hiçbir bağlantı
başlamaz ve oturum sırasında ekranda sürekli bir uyarı bandı görünür. Kullanıcı
oturumu istediği an sonlandırabilir.

## Güncelleme denetimi
Microsoft Store dışındaki sürümler, yeni sürüm olup olmadığını öğrenmek için
GitHub'daki herkese açık bir dosyayı okur. Bu istek kişisel veri içermez.

## İletişim
Sorular için: https://github.com/yosiniz/RDP_Controller/issues
