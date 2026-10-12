# Qidiruv sifati: development va frozen holdout

Production threshold: **MATCH_THRESHOLD=0.67**. Hech bir alohida xato misolga mos keyword yoki qoida qo'shilmadi. bge-m3 modeli va uning revision'i o'zgarmadi.

## Ma'lumotlarni ajratish

- `eval/dev.jsonl`: ilgari `dataset.jsonl` bo'lgan **245 savol** (186 in-domain, 59 OOD). Oldingi lug'at va threshold shu ma'lumotlar bilan sozlangan, shuning uchun eski savollarni holdout deb qayta nomlash halol bo'lmas edi. Ularning hammasi development uchun qoldirildi.
- `eval/holdout.jsonl`: yangi **120 savol**: ilgari eval'da qamrab olinmagan **40 javob ID** uchun 80 ta lotin/kirill parafraz va 40 ta begona/qo'llab-quvvatlanmaydigan so'rov. Oddiy begona mavzular bilan birga shaxsiy balans, shaxsiy ariza holati kabi bazadagi umumiy yo'riqnoma javob bera olmaydigan so'rovlar ham bor.
- Holdout model bilan tekshirilishidan oldin muzlatildi. SHA-256 va kelib chiqishi: `eval/holdout_manifest.json`. Test hash o'zgarmaganini va dev bilan so'rovlar kesishmasligini tekshiradi.
- Savollar inson foydalanuvchilaridan mustaqil yig'ilmagan: developer tomonidan yozilgan. 120 ta sintetik savol ishlab chiqarish muhitidagi aniqlik uchun kafolat emas. Ikki semantik teng xizmat-ma'lumoti manbasi scoringdan oldin birga maqbul javob sifatida belgilangan.

## Tajriba tartibi

Eng sodda variant — global threshold kalibrovkasi tanlandi. **Faqat dev** bo'yicha 0.30–0.90 oralig'i 0.01 qadamda tekshirildi. Maqsad: `to'g'ri qabul − 2 × noto'g'ri qabul`, bunda to'g'ri qabul baseline'ning kamida 95 foizi bo'lishi kerak. Teng holatda ko'proq to'g'ri javob, keyin baseline'ga yaqin threshold afzal.

Dev **0.67** nomzodini tanladi. Nomzod va qabul sharti holdout ochilishidan oldin `frozen_candidate.json` ga yozildi. Holdout'da faqat shu bitta nomzod **0.64** baseline bilan solishtirildi. Qabul uchun decision accuracy, in-domain correct rate, accepted precision va OOD rejection F1 kamaymasligi, xato qabul sonlari oshmasligi va kamida bitta metrika yaxshilanishi talab qilindi.

Holdout'ning **alohida savol xatolari chiqarilmadi va tuningda ko'rilmadi**. Faqat agregat natijalar olindi. Boshqa nomzodlar bilan holdout'ga qayta moslash qilinmadi.

## Natijalar

Quyidagi metrikalar API'ning threshold va qisqa so'rov ambiguity qarorini hisobga oladi. `wrong accepted` in-domain noto'g'ri javoblarni ham, OOD false acceptance'larni ham o'z ichiga oladi.

| Ko'rsatkich | Dev 0.64 | Dev 0.67 | Holdout 0.64 | Holdout 0.67 |
|---|---:|---:|---:|---:|
| To'g'ri qabul | 141/186 | 135/186 | 72/80 | 72/80 |
| Noto'g'ri qabul | 34 | 24 | 29 | 24 |
| Shundan OOD false acceptance | 2/59 | 0/59 | 21/40 | 16/40 |
| In-domain rad etilgan | 13 | 27 | 0 | 0 |
| Decision accuracy | 0.8082 | 0.7918 | 0.7583 | **0.8000** |
| In-domain correct rate | 0.7581 | 0.7258 | 0.9000 | **0.9000** |
| Accepted precision | 0.8057 | 0.8491 | 0.7129 | **0.7500** |
| OOD rejection F1 | 0.8837 | 0.8138 | 0.6441 | **0.7500** |
| Recall@1 (ranking) | 0.7849 | 0.7849 | 0.9000 | 0.9000 |
| Recall@3 (ranking) | 0.9086 | 0.9086 | 0.9500 | 0.9500 |
| MRR | 0.8492 | 0.8492 | 0.9255 | 0.9255 |

Holdout'da **5 qaror yaxshilandi, 0 qaror yomonlashdi**; barcha himoyalangan metrikalar kamaymadi. Shu oldindan belgilangan mezon asosida **0.67 qabul qilindi**. Bu kichik, developer yozgan to'plamdagi kuzatilgan yaxshilanish; statistik yoki production kafolati emas.

**Dev'dagi tradeoff yashirilmagan:** 6 ta to'g'ri javob yo'qolgan va decision accuracy hamda OOD F1 pasaygan. Nomzodni qabul qilish mustaqil holdout bo'yicha amalga oshirildi. Global threshold bir xil ma'nodagi so'rovlarni mukammal ajratmaydi.

Phase 1 dagi 0.785 Recall@1, 0.909 Recall@3, 0.849 MRR va 0.891 F1 raqamlari qayta takrorlangan edi. Eski F1 faqat threshold bo'yicha hisoblangan; yangi jadval ambiguity rad etishlarini ham qo'shadi, shu sabab dev baseline F1 0.8837. Bu raqamlar turli qaror o'lchovlarini ifodalaydi.

Asl muzlatilgan tajriba artefaktlari: `eval/baseline/{frozen_candidate,dev_summary,holdout_summary}.json`.

## Qayta bajarish

Ishlayotgan PostgreSQL/Qdrant va yuklangan korpus/model bilan, loyiha ildizidan:

```bash
python -m eval.evaluate --dataset eval/dev.jsonl --out eval/results/dev
```

Dev evaluator joriy threshold bo'yicha bitta savol qarorlarini hisoblaydi. Tuning va suhbat baholash olib tashlangan; holdout qayta baholanmaydi.

## Ma'lum cheklovlar — QA-01 to'liq yopilmadi

0.67 ham holdout'da **24 noto'g'ri javobni qabul qiladi**, ulardan 16 tasi OOD. Yuqori similarity javobning so'ralgan jihatni qamrab olishini kafolatlamaydi. Phase 1 dagi ID-karta narxi misoli kabi noto'g'ri, lekin yuqori balli javoblar qolishi mumkin. Maxsus misol keyword'lari kiritilmadi.

Keyingi mustaqil tajriba uchun yangi holdout kerak: bu holdout endi release qarorida ishlatilgan. Reranker yoki sparse/hybrid qidiruv ushbu bosqichda qo'shilmadi; yangi model, dependency va kalibrovka ko'lamini oshirmasdan global threshold bilan kichik, o'lchangan yaxshilanish olindi. Bazadagi mazmunan yaqin, matni turlicha javoblar ham annotatsiya cheklovi bo'lib qoladi.
