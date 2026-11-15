# Xavfsizlik siyosati / Security Policy

## Qo'llab-quvvatlanadigan versiyalar

| Versiya | Qo'llab-quvvatlanadi |
|---|---|
| 0.3.x | ✅ |

## Zaiflik haqida xabar berish

Xavfsizlik zaifligini topsangiz, **uni ochiq Issue sifatida joylamang**. Buning o'rniga:

- GitHub'ning [Security Advisory](../../security/advisories/new) bo'limi orqali maxfiy xabar yuboring,
  yoki
- repozitoriya egasiga to'g'ridan-to'g'ri yozing.

Iloji boricha quyidagilarni qo'shing: zaiflik tavsifi, takrorlash qadamlari, ta'sir doirasi va
(agar bo'lsa) tuzatish taklifi. Imkon qadar tez javob berishga harakat qilamiz.

## Foydalanuvchi uchun xavfsizlik eslatmalari

**Agent Umimiy** lokal desktop ilova, lekin uning ayrim integratsiyalari joriy Windows/Linux foydalanuvchisi huquqlari bilan ishlaydi.

- **API kalitlari, suhbatlar va xotira** diskda shifrlanmagan saqlanadi. Ilova papkasi POSIX tizimlarda egasiga cheklanadi; Windows'da foydalanuvchi AppData ACL'lariga tayanadi. Disk shifrlashni (BitLocker/FileVault/LUKS) yoqish tavsiya etiladi.
- **Shell va CLI agentlar** tanlangan loyiha papkasidan boshlanishi mumkin, ammo OS darajasida sandbox qilinmagan: joriy foydalanuvchi huquqlari bilan boshqa fayllar va tizim resurslariga ham kira oladi. Buyruqni tasdiqlashdan oldin tekshiring.
- **MCP serverlari** alohida dastur sifatida ishga tushadi va joriy foydalanuvchi huquqlariga ega. Ularning muhitiga provider API kalitlari avtomatik uzatilmaydi; kerakli tokenlarni faqat shu server uchun aniq sozlang.
- **Telefondan boshqarish** oddiy HTTP orqali ishlaydi. Token URL fragmentida bo'lsa ham, so'rovlar tarmoqda shifrlanmaydi. Faqat ishonchli LAN yoki Tailscale/VPN kabi shifrlangan tunnelda foydalaning.
- **Ichki fayl asboblari** tanlangan loyiha papkasidan tashqariga chiqishni bloklaydi; shell/CLI/MCP uchun bu kafolat yo'q.
- **HTML ko'rinish oynasi** tashqi resurs yuklashini CSP bilan cheklaydi va sandbox ichida ishlaydi. Biroq iframe navigatsiyasini barcha brauzerlarda to'liq bloklash kafolatlanmagan; maxfiy ma'lumotli ishonchsiz HTML'ni ochmang.
- **Masofaviy veb-server** login/sessiya bilan himoyalangan, lekin internetga to'g'ridan-to'g'ri ochish o'rniga HTTPS reverse proxy yoki VPN ishlating.
- **Veb-server foydalanuvchilari** kompyuter egasining sozlangan provider/API kalitlaridan foydalanadi. Taklif kodini faqat ishonchli odamlarga bering. Bir akkauntga 60 soniyada 20 ta xabar va 100 ta suhbat limiti bor, lekin kunlik xarajat yoki umumiy disk kvotasi yo'q.
- **Maxsus provider URL** sozlaganda masofaviy endpoint uchun HTTPS ishlating; HTTP endpointga yuborilgan API kaliti tarmoqda ochiq ko'rinishi mumkin.
- **Python 3.9** upstream tomonidan qo'llab-quvvatlashdan chiqqan. Ilovani imkon qadar xavfsizlik yangilanishlari olayotgan Python 3.11 yoki yangiroq versiyada ishga tushiring.
- **Release fayllari** hozircha kod imzosi bilan tasdiqlanmaydi; faqat rasmiy GitHub relizlaridan yuklab oling.

Zaiflik haqida xabar berish uchun yuqoridagi maxfiy Security Advisory kanalidan foydalaning.
