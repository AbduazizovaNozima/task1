# Qidiruv sifatini baholash

Natijalarni qayta hosil qilish (PostgreSQL va Qdrant'ga ma'lumot yuklangan bo'lishi kerak):

```bash
python -m eval.evaluate
```

Natijalar `eval/results/metrics.json` (barcha ko'rsatkichlar va chegara sweep'i) va `eval/results/failures.json` (xatolar ro'yxati) fayllariga yoziladi.

## 1. Baholash to'plami qanday tuzilgan

`eval/dataset.jsonl` — 239 ta savol. Har bir qator: `{"query": ..., "expected": [bazadagi savol matni, ...]}`. Kutilgan javob bazadagi savol matni orqali beriladi, chunki u o'qilishi oson va ID o'zgarsa ham buzilmaydi. `expected: []` — bazada javobi yo'q savol.

| Qism | Soni | Qanday tuzilgan |
|---|---|---|
| Parafrazlar (yangi) | 138 | Bazadagi 505 ta javobdan har 11-chisi olindi: 46 ta javob, barcha 9 kategoriyani qamraydi. Har biriga 3 tadan parafraz yozildi: so'zlashuv uslubida, imlo xatosi bilan, kirill yozuvida va ruscha. |
| Parafrazlar (avvalgi loyihadan) | 46 | Qo'lda yozilgan real uslubdagi savollar ("prava", "voenniy bilet", "otpusk" kabi so'zlar bilan). |
| Domendan tashqari (yangi) | 30 | Bazada javobi yo'q savollar: kundalik hayot, texnika, ob-havo; o'zbek, kirill va rus tillarida. |
| Domendan tashqari (avvalgi) | 25 | Xuddi shunday. |

Yozuv turi bo'yicha: lotin — 135 ta, kirill (o'zbek va rus) — 49 ta savol (bazada javobi bor savollar hisobida).

**Cheklov.** Parafrazlarni real foydalanuvchilar emas, ishlab chiquvchi yozgan. Bazadagi savollarning o'zi esa shablon asosida yaratilgan ("Menga ... haqida ayting"). Shu sababli ular baholashda ishlatilmadi: ularda sifat haqiqatdagidan yuqori chiqib qolardi.

## 2. Qidiruv sifati (bazada javobi bor 184 ta savol)

| Ko'rsatkich | Qiymat |
|---|---|
| Recall@1 | **0.734** |
| Recall@3 | **0.891** |
| MRR | **0.813** |
| Recall@1, lotin yozuvi (135) | 0.726 |
| Recall@1, kirill yozuvi (49) | 0.735 |

Kirill yozuvidagi o'zbekcha savollar lotinga o'girilmasa ham to'g'ri topildi ("ЗАГСда никоҳдан ўтиш учун нималар керак?" → nikohni qayd qilish). Shuning uchun eski koddagi "kirill → lotin" transliteratsiyasi olib tashlandi. U ruscha matnni ham lotinga o'girib, bge-m3 tushunadigan ruscha so'zlarni buzar edi.

## 3. "Topilmadi" qarori va chegara tanlovi

"Ijobiy" sinf — rad etilishi kerak bo'lgan savol, ya'ni bazada javobi yo'q savol:

- **precision** — rad etilganlar ichida haqiqatan domendan tashqari bo'lganlar ulushi;
- **recall** — domendan tashqari savollarning rad etilgan ulushi.

`answered` — bazada javobi bor savollardan nechtasiga to'g'ri javob berilgani (chegaradan o'tgan **va** 1-o'rindagi javob to'g'ri).

| Chegara | Precision | Recall | F1 | Answered | Noto'g'ri rad etilgan | Noto'g'ri qabul qilingan |
|---|---|---|---|---|---|---|
| 0.50 | 0.714 | 0.091 | 0.161 | 0.734 | 2 | 50 |
| 0.55 | 0.800 | 0.436 | 0.565 | 0.728 | 6 | 31 |
| 0.60 | 0.776 | 0.818 | 0.796 | 0.712 | 13 | 10 |
| **0.62** | **0.750** | **0.982** | **0.850** | **0.701** | **18** | **1** |
| 0.65 | 0.639 | 1.000 | 0.780 | 0.652 | 31 | 0 |
| 0.70 | 0.462 | 1.000 | 0.632 | 0.565 | 64 | 0 |

**Tanlov: `MATCH_THRESHOLD=0.62`** — sweep (0.30–0.90, qadam 0.01) bo'yicha F1 eng yuqori bo'lgan nuqta.

- 0.62 da domendan tashqari 55 ta savoldan 54 tasi rad etiladi, to'g'ri javoblar ulushi esa atigi 3 punktga kamayadi (0.734 → 0.701).
- 0.60 da 10 ta begona savolga noto'g'ri javob beriladi. Davlat xizmatlari bo'yicha botda noto'g'ri javob "topilmadi" javobidan qimmatroq tushadi.
- 0.65 da esa to'g'ri savollarning 17 foizi rad etiladi.

bge-m3 kosinus ballari tor diapazonda yotadi: domendan tashqari savollarning eng yuqori bali 0.628 bo'ldi. Oldingi koddagi "taxminiy" 0.70 chegarasi bilan to'g'ri savollarning 35 foizi (184 tadan 64 tasi) rad etilgan bo'lardi.

## 4. Xato misollari va tahlil

| # | Savol | Ball | Natija | Sabab |
|---|---|---|---|---|
| 1 | `guvohnomadagi xatoni to'g'irlash` | 0.786 | "Guvohnomadagi sana yoki ma'lumotni tuzatish mumkinmi?" (kutilgan: "FHDYO yozuvidagi xato qanday tuzatiladi?") | **Yorliq noaniqligi.** Bazada mazmunan deyarli bir xil ikki javob bor, model topgani ham to'g'ri. Xatolarning qariyb yarmi shu turdagi (49 ta xatodan 23 tasida to'g'ri javob 2-o'rinda, 29 tasida — top-3 ichida). |
| 2 | `firmani qanday yopaman` | 0.756 | "Firma nomini o'zgartirish qanday qilinadi?" | **Leksik ustunlik.** "firma" so'zi niyatdan ("yopish") kuchliroq chiqdi. To'g'ri javob 2-o'rinda. |
| 3 | `vid na jitelstvo yo'qoldi` | 0.548 | rad etildi | **Ruscha so'z lotin harflarida.** Tokenizator buni na rus, na o'zbek so'zi deb taniydi. |
| 4 | `pinfl nima o'zi` | 0.457 | rad etildi | **Qisqartma.** Bazada faqat "JSHSHIR" shakli bor. Dense vektor qisqartmalar sinonimligini bilmaydi. |
| 5 | `OSAGO polis qanday olinadi` | 0.492 | rad etildi | Xuddi shunday: qisqartma bazada boshqacha ifodalangan. |
| 6 | `rodomni o'zim tanlasam bo'ladimi` | 0.567 | to'g'ri javob 18-o'rinda | **Jargon** ("rodom" = tug'ruqxona). |
| 7 | `bog'cha puli uchun lgota bormi` | 0.608 | 1-o'rin to'g'ri, lekin chegaradan past → rad etildi | **Noto'g'ri rad etish.** Ruscha "lgota" so'zi ballni pasaytirdi. |
| 8 | `mulkdan ulushimni ajratib olmoqchiman` | 0.677 | "Menga xorijga chiqishga qo'yilgan taqiqni tekshirish bekor qilish haqida ayting" | **Shablon shovqini.** Bazadagi "Menga ... haqida ayting" shabloni savollar orasida umumiy "shovqin" hosil qiladi. |
| 9 | `Avtomobil moyini qachon almashtirish kerak?` (domendan tashqari) | 0.628 | noto'g'ri qabul qilindi: "Avtomobil rangi yoki dvigateli o'zgartirilsa qayd etiladimi?" | **Mavzu yaqinligi.** Savol avtomobil haqida, bazada ham avtomobil bo'yicha savollar bor. Bu yagona noto'g'ri qabul. |

## 5. Yaxshilash g'oyalari (amalga oshirilmagan)

Ko'rsatkichlar maqbul darajada bo'lgani uchun quyidagilar faqat taklif sifatida qoldirildi:

1. **Hybrid qidiruv: dense + sparse.** bge-m3 bir vaqtda leksik (sparse) og'irliklarni ham qaytaradi. Qdrant ularni named sparse vector sifatida saqlab, RRF yoki og'irlikli yig'indi bilan birlashtira oladi. Bu qisqartmalar (JSHSHIR, OSAGO, ERI) va aniq atamalar bo'yicha 3–5-misollardagi xatolarni kamaytirishi kutiladi.
2. **Reranker (`bge-reranker-v2-m3`, lokal).** Top-10 nomzodni qayta tartiblash 1, 2 va 8-misollardagi turdagi xatolarni (to'g'ri javob 2–3-o'rinda) tuzatadi. Bunda Recall@1 Recall@3 (0.89) ga yaqinlashishi mumkin. Narxi: har bir so'rovga CPU'da ~100–200 ms.
3. **Sinonimlar lug'ati.** `pinfl → JSHSHIR`, `prava → haydovchilik guvohnomasi`, `rodom → tug'ruqxona`, `lgota → imtiyoz` kabi kichik lug'at bilan so'rovni kengaytirish.
4. **Ma'lumotni tozalash.** Savollardagi "Menga ... haqida ayting", "Iltimos, ayting:" kabi shablon qismlarni olib tashlash, mazmunan bir xil javoblarni birlashtirish.
5. **Javob matnini ham indekslash** (alohida vektor sifatida) — savol variantlari kam bo'lgan javoblar uchun foydali.
6. **Chegarani qayta kalibrovka qilish.** Real foydalanuvchi so'rovlari logidan to'plam yig'ib, chegarani qayta tanlash.
