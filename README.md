# Semantik savol-javob tizimi

Foydalanuvchi savolni o'z so'zlari bilan (lotin yoki kirill yozuvida) yozadi. Tizim Excel'dagi savol-javoblar orasidan ma'nosi eng yaqinini topadi va javobni bazadagi matn holida qaytaradi. Mos javob bo'lmasa — "topilmadi". LLM ishlatilmaydi, hamma narsa lokal ishlaydi.

**Stek:** bge-m3 · Qdrant · PostgreSQL · FastAPI · aiogram · Docker Compose

## Arxitektura

```
Telegram ─▶ bot/ ──HTTP──▶ app/api ─▶ SearchService ─▶ bge-m3 + Qdrant + PostgreSQL
qa.xlsx ─▶ python -m app.cli ingest ─▶ IngestionService ─▶ PostgreSQL (matn) + Qdrant (vektor)
```

```
app/
  domain/      modellar, Protocol'lar (ports.py), xatolar, matn va so'rov qoidalari (text.py, query.py)
  adapters/    bge-m3, Qdrant, PostgreSQL, Excel
  api/         FastAPI: /ask, /ingest, /health
  container.py barcha obyektlar shu yerda yig'iladi
bot/           Telegram bot — API'ga faqat HTTP orqali murojaat qiladi
eval/          baholash to'plamlari va skript
tests/         unit testlar (fake'lar bilan) va integratsion testlar
```

**Savol qanday javob topadi:**
1. Kirill yozuvi lotinga o'giriladi, so'zlashuv shakllari va xalq iboralari bazadagi atamalarga bog'lanadi (`erga tegmoq → nikoh`, `prava → haydovchilik guvohnomasi`).
2. bge-m3 savolni vektorga aylantiradi, Qdrant eng yaqin savollarni topadi, top-5 olinadi.
3. Ball `MATCH_THRESHOLD` dan past bo'lsa — "topilmadi". 1–2 so'zli so'rovda eng yaxshi ikki variant bali deyarli teng bo'lsa — aniqlashtirish uchun variantlar taklif qilinadi.

## Ishga tushirish

```bash
cp .env.example .env            # bot uchun TELEGRAM_BOT_TOKEN ni yozing; API uchun shart emas
docker compose up -d --build    # postgres, qdrant, ingest, api, bot
docker compose logs -f api bot  # loglarni kuzatish
```

Portlar band bo'lsa, ishga tushirishdan oldin `POSTGRES_PORT`, `QDRANT_PORT`, `API_PORT` ni bo'sh portlarga belgilang. API so'rovlarida yangi `API_PORT` dan foydalaning; lokal test/eval uchun `.env` dagi `DATABASE_URL` va `QDRANT_URL` portlarini ham moslang. Parallel nusxa uchun alohida `COMPOSE_PROJECT_NAME` va `QA_IMAGE` ishlating. Token bo'lmasa bot ishga tushmaydi, API ishlaydi.

`ingest` servisi `data/qa.xlsx` faylini yuklaydi (birinchi safar model yuklanishi va embedding hisoblanishini kuting; keyingi safar faqat o'zgargan savollar). API: http://localhost:8000/docs

```bash
curl -X POST localhost:8000/ask -H 'Content-Type: application/json' \
     -d '{"question": "Id karta olish uchun nima kerak"}'
```

**Testlar va baholash** (`pip install -e ".[api,bot,dev]"`):

```bash
ruff check . && ruff format --check . && mypy app bot tests eval && pytest
python -m eval.evaluate --dataset eval/dev.jsonl --out eval/results/dev
# Frozen holdout va bir martalik kalibrovka: EVALUATION.md
```

Joriy tekshiruv: **68 test o'tdi**, shu jumladan PostgreSQL/Qdrant bilan 6 integratsion test.

## Import va xatolar

Excel importi SQL tranzaksiyasida bajariladi: vektorlar yozilgandan keyingina SQL commit bo'ladi. Vektor yoki embedding xatosida SQL o'zgarishlari rollback qilinadi. Qisman qolgan vektorlar SQL'da tasdiqlangan yozuv bo'lmasa javob sifatida ishlatilmaydi; qayta import ularni yakunlaydi. Bu ikki servis uchun distributed transaction emas: muvaffaqiyatsiz importdan qolgan vector yozuvlar fizik jihatdan qayta importgacha saqlanishi mumkin.

Ingest boshlanishida saqlash servislarining tayyorligi 60 soniyagacha qayta tekshiriladi; oxirgi tarmoq so'rovi o'z timeout'igacha davom etishi mumkin. Buzilgan Excel XML'i 422 beradi. Bot uzun javobni plain-text bo'laklarda to'liq yuboradi; input validatsiyasi bilan servis uzilishini farqlaydi.

`MATCH_THRESHOLD=0.67` yangi, muzlatilgan holdout'da tekshirildi. Bu noto'g'ri javoblarni to'liq yo'qotmaydi; dev/holdout natijalari va cheklovlar [EVALUATION.md](EVALUATION.md) da.
