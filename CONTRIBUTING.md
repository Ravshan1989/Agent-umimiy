# Hissa qo'shish / Contributing

Rahmat! **Agent Umimiy** ochiq loyiha — har qanday yordam (kod, hujjat, xato xabari, g'oya)
mamnuniyat bilan qabul qilinadi.

> 🇬🇧 English note: contributions are welcome. The project interface is in Uzbek; issues and
> pull requests may be written in Uzbek, Russian or English.

## Xato yoki taklif

- Avval mavjud [Issue'larni](../../issues) qidiring — takrorlanmasin.
- Yangi [Issue](../../issues/new/choose) oching: xato uchun qadamlarni, kutilgan va haqiqiy natijani,
  OS/versiyani yozing.

## Kod bilan hissa qo'shish

1. Repozitoriyani **fork** qiling va yangi **branch** oching:
   ```bash
   git checkout -b feature/qisqa-nom
   ```
2. O'zgarish kiriting. Imkon qadar kichik va bitta maqsadga qaratilgan bo'lsin.
3. **Testlarni ishga tushiring**:
   ```bash
   python -m unittest discover -s tests -t .
   ```
4. Commit xabarini aniq yozing (o'zbek, rus yoki ingliz tilida).
5. **Pull request** yuboring: nima o'zgargani va nega kerakligini qisqa tushuntiring.

## Manba koddan ishga tushirish

Python 3.9+ kerak. Ixtiyoriy kutubxonalar: `pypdf` (PDF), `qrcode` (telefon QR), `pillow` (skrinshot qo'yish), `python-docx` va `openpyxl` (Word/Excel yaratish).

```bash
git clone https://github.com/Ravshan1989/Agent-umimiy.git
cd Agent-umimiy
pip install pypdf qrcode pillow python-docx openpyxl
python app.py                              # oyna
python app.py --cli -m broadcast "salom"   # terminal
```

## Uslub

- Kod Python standartlariga (PEP 8) yaqin bo'lsin; mavjud fayllardagi uslubga ergashing.
- Foydalanuvchiga ko'rinadigan matnlar hozircha **o'zbek tilida** (interfeys tili loyiha rejasida
  kengaytiriladi).
- Yangi agent turi: `providers.py` da `Agent` ni meros qilib, `KINDS` ga qo'shing.

## Litsenziya

Hissa qo'shish orqali kodingiz loyiha litsenziyasi — [MIT](LICENSE) ostida tarqatilishiga rozilik
bildirasiz.
