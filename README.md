# Semantik savol-javob tizimi

Foydalanuvchi savolni o'z so'zlari bilan (lotin yoki kirill yozuvida) yozadi. Tizim Excel'dagi savol-javoblar orasidan ma'nosi eng yaqinini topadi va javobni bazadagi matn holida qaytaradi. Mos javob bo'lmasa — "topilmadi". LLM ishlatilmaydi, hamma narsa lokal ishlaydi.

**Stek:** bge-m3 · Qdrant · PostgreSQL · FastAPI · aiogram · Docker Compose

## Arxitektura

```
Telegram ─▶ bot/ ──HTTP──▶ app/api ─▶ ConversationService ─▶ SearchService ─▶ bge-m3 + Qdrant + PostgreSQL
                                          │ (chat tarixi)
qa.xlsx ─▶ python -m app.cli ingest ─▶ IngestionService ─▶ PostgreSQL (matn) + Qdrant (vektor)
```

```
app/
  domain/      modellar, Protocol'lar (ports.py), xatolar, matn va so'rov qoidalari (text.py, query.py)
  services/    search.py (qidiruv), conversation.py (chat tarixi), ingestion.py (yuklash)
  adapters/    bge-m3, Qdrant, PostgreSQL, Excel
  api/         FastAPI: /ask, /sessions/{id}, /ingest, /health
  container.py barcha obyektlar shu yerda yig'iladi
bot/           Telegram bot — API'ga faqat HTTP orqali murojaat qiladi
eval/          baholash to'plamlari va skript
tests/         unit testlar (fake'lar bilan) va integratsion testlar
```

**Savol qanday javob topadi:**
1. Kirill yozuvi lotinga o'giriladi, so'zlashuv shakllari va xalq iboralari bazadagi atamalarga bog'lanadi (`erga tegmoq → nikoh`, `prava → haydovchilik guvohnomasi`).
2. bge-m3 savolni vektorga aylantiradi, Qdrant eng yaqin savollarni topadi, top-5 olinadi.
3. Ball `MATCH_THRESHOLD` dan past bo'lsa — "topilmadi". 1–2 so'zli so'rovda eng yaxshi ikki variant bali deyarli teng bo'lsa — aniqlashtirish uchun variantlar taklif qilinadi.
4. Har bir foydalanuvchining suhbat mavzusi PostgreSQL'da 30 daqiqa saqlanadi (guruhda ham har kimniki alohida). "muddati-chi?", "buning narxi" kabi davomi savollar shu mavzu bilan qidiriladi. `/new` — yangi suhbat.

Har bir savol API logida bitta blok bo'lib chiqadi:

```
session=telegram-1-1 question="muddati-chi?" context="Id karta olish uchun nima kerak" -> FOUND score=0.916
  #1 0.916 Q: ID-karta qancha muddatga beriladi?
           A: Bir yoshgacha bo'lgan bolaga — 2 yil, 1 yoshdan 16 yoshgacha — 5 yil muddatga ...
  #2 0.799 Q: ...
```

## Ishga tushirish

```bash
cp .env.example .env            # TELEGRAM_BOT_TOKEN ni yozing
docker compose up -d --build    # postgres, qdrant, ingest, api, bot
docker compose logs -f api bot  # loglarni kuzatish
```

`ingest` servisi `data/qa.xlsx` faylini yuklaydi (birinchi marta ~7 daqiqa, keyingi safar faqat o'zgargan savollar). API: http://localhost:8000/docs

```bash
curl -X POST localhost:8000/ask -H 'Content-Type: application/json' \
     -d '{"question": "Id karta olish uchun nima kerak", "session_id": "demo"}'
```

**Testlar va baholash** (`pip install -e ".[api,bot,dev]"`):

```bash
ruff check . && mypy app bot tests eval && pytest
python -m eval.evaluate         # natijalar: EVALUATION.md
```
