# Qidiruv sifatini baholash

```bash
python -m eval.evaluate   # natijalar: eval/results/{metrics,failures,conversations}.json
```

## To'plamlar

**`eval/dataset.jsonl`** — 245 ta bitta savollik so'rov:
- **bazada javobi bor 186 ta savol:** 46 ta javobga 3 tadan parafraz, avvalgi loyihadan 46 ta real uslubdagi savol, bot chatidan 2 ta savol. Ulardan 137 tasi lotin, 49 tasi kirill yozuvida;
- **bazada javobi yo'q 59 ta savol.**

Bot faqat o'zbek tilida ishlaydi, shuning uchun ruscha savollar o'zbekcha kirill variantlariga almashtirilgan.

**`eval/conversations.jsonl`** — 6 ta suhbat ssenariysi, jami 15 ta xabar: davomi savollar, mavzu almashishi, noaniq so'rov, xalq iborasi.

**Cheklov:** savollarni real foydalanuvchilar emas, ishlab chiquvchi yozgan. Lug'atdagi bir nechta so'z ("rodom", "lgota", "pinfl") shu to'plamdagi xatolarga qarab qo'shilgan, chegara ham shu to'plamda tanlangan. Shuning uchun raqamlar biroz optimistik.

## Natijalar

| Ko'rsatkich | Qiymat |
|---|---|
| Recall@1 | **0.785** |
| Recall@3 | **0.909** |
| MRR | **0.849** |
| "Topilmadi" qarori, F1 (chegara 0.64) | **0.891** |
| Suhbat ssenariylari | **12 / 15** xabar to'g'ri |

## Chegara tanlovi

"Ijobiy" sinf — bazada javobi yo'q savolni rad etish.

| Chegara | Precision | Recall | F1 | To'g'ri javob ulushi | Noto'g'ri rad etilgan | Noto'g'ri qabul qilingan |
|---|---|---|---|---|---|---|
| 0.60 | 0.830 | 0.746 | 0.786 | 0.769 | 9 | 15 |
| 0.62 | 0.844 | 0.915 | 0.878 | 0.763 | 10 | 5 |
| **0.64** | **0.826** | **0.966** | **0.891** | **0.758** | **12** | **2** |
| 0.65 | 0.763 | 0.983 | 0.859 | 0.737 | 18 | 1 |

`MATCH_THRESHOLD=0.64` F1 eng yuqori bo'lgan nuqta: 59 ta begona savoldan 57 tasi rad etiladi. Davlat xizmatlari botida noto'g'ri javob "topilmadi" javobidan qimmatroq tushadi.

## Qolgan xatolar

| Savol | Natija | Sabab |
|---|---|---|
| `pensiya nechpul` | Pensiya haqidagi boshqa javob (0.662) | Pensiya miqdori bazada yo'q, lekin pensiya mavzusidagi savollar yaqin ball oladi. |
| `erga tegmoqchiman prava olmayman` | Topilmadi (0.638) | Qisqa so'rov chegaradan biroz past. 0.62 chegarada to'g'ri javob topilardi. |
| `Pasportni almashtirish...` → `buning uchun qanday hujjatlar kerak` | Chet elda pasport almashtirish | Davomi savolda mavzu so'zlari ustun chiqadi. Vektorlarni aralashtirish ham sinab ko'rildi, umumiy natijani yaxshilamadi. |
| `Id karta qanaqa qilib olinadi` | To'g'ri javob 2-o'rinda | Bitta mavzudagi o'nlab savol bir-biriga juda yaqin ball oladi. |
| `guvohnomadagi xatoni to'g'irlash` | Mazmunan bir xil boshqa javob | Bazada deyarli bir xil javoblar bor. Bunday holatlar xatolarning qariyb yarmini tashkil qiladi. |
| `vid na jitelstvo yo'qoldi`, `OSAGO polis` | Topilmadi | Ruscha ibora lotin harflarida va lug'atda yo'q qisqartma. |
| "ID-karta narxi" | Topilmaydi | Narx faqat javob matni ichida yozilgan, faqat savollar indekslanadi. |

## Keyingi qadamlar

1. **Reranker** (`bge-reranker-v2-m3`, lokal, ~2.3 GB). Nomzodlarni savol bilan birga o'qib qayta tartiblaydi. Bu 2-o'rindagi to'g'ri javoblar va chegara yaqinidagi noto'g'ri qabullar uchun eng katta yaxshilanishni berishi kutiladi.
2. **Javob matnlarini ham indekslash.**
3. **Bazani tozalash:** "Menga ... haqida ayting" shablonlarini olib tashlash, mazmunan bir xil javoblarni birlashtirish.
4. **Real foydalanuvchi savollari logidan to'plam yig'ib, chegarani qayta kalibrovka qilish.**
