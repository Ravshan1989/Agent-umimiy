# Xavfsizlik siyosati / Security Policy

## Qo'llab-quvvatlanadigan versiyalar

| Versiya | Qo'llab-quvvatlanadi |
|---|---|
| 0.1.x | ✅ |

## Zaiflik haqida xabar berish

Xavfsizlik zaifligini topsangiz, **uni ochiq Issue sifatida joylamang**. Buning o'rniga:

- GitHub'ning [Security Advisory](../../security/advisories/new) bo'limi orqali maxfiy xabar yuboring,
  yoki
- repozitoriya egasiga to'g'ridan-to'g'ri yozing.

Iloji boricha quyidagilarni qo'shing: zaiflik tavsifi, takrorlash qadamlari, ta'sir doirasi va
(agar bo'lsa) tuzatish taklifi. Imkon qadar tez javob berishga harakat qilamiz.

## Foydalanuvchi uchun xavfsizlik eslatmalari

**Agent Umimiy** lokal desktop ilova. Quyidagilarni yodda tuting:

- **API kalitlar** faqat sizning kompyuteringizdagi sozlama faylida saqlanadi
  (`%APPDATA%\AgentUmimiy\agents.json`) — shifrlanmagan. Begona kompyuterda ehtiyot bo'ling.
- **Suhbatlar** `%APPDATA%\AgentUmimiy\chats.json` da shifrlanmagan saqlanadi — maxfiy ma'lumot
  yozmang yoki saqlashni o'chiring.
- **Telefondan boshqarish** ulanishi **shifrlanmagan (HTTP)**: faqat ishonchli uy Wi-Fi'ida
  ishlating. Kirish kaliti (`t=...`) parol kabi maxfiy — oshkor bo'lsa "Yangi kalit" ni bosing.
- **Agent** faqat siz tanlagan papkada fayl o'zgartiradi; buyruq va yozish ruxsatingiz bilan
  bajariladi; brauzer alohida profilda ishlaydi.
- Internet/sahifa matni agent uchun faqat ma'lumot sifatida qaraladi — undagi "buyruqlar"ga
  amal qilinmaydi.
