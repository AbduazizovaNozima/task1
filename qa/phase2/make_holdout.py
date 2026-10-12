import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sources = json.loads((root / "qa/phase2/holdout_sources.json").read_text())
paraphrases = [
    [
        "ID-kartamdagi ma'lumotni xato kiritishgan, tuzatib berishadimi?",
        "Йиғиш пункти ID картамни хато тўлдирган бўлса, қайта бериш пуллими?",
    ],
    [
        "Yangi manzilga doimiy propiska qilishning amaldagi tartibini tushuntiring",
        "Доимий яшаш манзилимни рўйхатга қўйдиришни нимадан бошлайман?",
    ],
    [
        "Davlat idorasi ustidan yozgan shikoyatimni kimga yuborsam bo'ladi?",
        "Арзимни халқ қабулхонасига электрон тарзда юбориш мумкинми?",
    ],
    [
        "Otamdan qolgan merosni rasmiy qilishga qanday qog'ozlar olib boraman?",
        "Меросхўр нотариусга қайси ҳужжатларни тайёрлаб бориши лозим?",
    ],
    [
        "Soliqdan qarzdor bo'lib qolganimni internetdan ko'rsam bo'ladimi?",
        "Солиқ ҳисобимдаги қарзни қаерда текшираман?",
    ],
    [
        "Shifoxonadagi xizmatdan noroziman, shikoyatni kim qabul qiladi?",
        "Тиббий хизмат сифатидан арз қилмоқчиман, қаерга ёзаман?",
    ],
    [
        "ID-kartaning yuzida va chipida egasi haqida nimalar bo'ladi?",
        "Шахсни тасдиқловчи ID картада қайси маълумотлар акс этади?",
    ],
    [
        "Menga chetga chiqish cheklovi qo'yilganmi, qanday aniqlab olib tashlayman?",
        "Хорижга чиқишимга қўйилган тақиқни бекор қилдириш йўли қандай?",
    ],
    [
        "Uyimning kadastr ma'lumotlari xato ekan, kimga tuzatishga beraman?",
        "Кўчмас мулк ҳақидаги ёзувни тўғрилаш учун қаерга ариза бераман?",
    ],
    ["Qaysi toifadagi odamlarga soliq bo'yicha yengillik bor?", "Солиқ имтиёзига кимлар ҳақли бўлади?"],
    [
        "Nogironlik bo'yicha pensiya belgilash nimaga asoslanadi?",
        "Ногиронлик пенсияси тайинланишида қайси комиссия хулосаси керак?",
    ],
    [
        "Universitet yotoqxonasidan joy olish uchun kimga ariza yozaman?",
        "Талабаларга ётоқхона ўринлари қандай тақсимланади?",
    ],
    [
        "Sotuvchi iste'molchi sifatidagi huquqimni buzdi, endi kimga arz qilaman?",
        "Харидорнинг ҳуқуқи бузилганда биринчи қаерга даъво берилади?",
    ],
    [
        "Alimentdan qarzi bor kishini chegaradan o'tkazmasliklari mumkinmi?",
        "Алимент тўланмагани учун хорижга чиқиш чекланадими?",
    ],
    [
        "Davlat xizmati uchun talablar va hujjatlar ro'yxatini qaysi saytdan ko'raman?",
        "Давлат хизматлари шартлари жамланган расмий портал қайси?",
    ],
    [
        "Tug'ilganlik guvohnomamni chet davlatda ishlatishga apostilni qanday qo'ydiraman?",
        "Никоҳ гувоҳномасини хорижга тақдим этиш учун апостил қилиш тартиби керак",
    ],
    [
        "Notariusga to'lanadigan pul qanday qismlardan tashkil topadi?",
        "Нотариал хизмат ҳақини нималарга қараб ҳисоблашади?",
    ],
    [
        "Ishonchnoma bilan minib yurgan mashinani sotish vakolati ham bo'ladimi?",
        "Ишончнома орқали автомобилни сотишда нималар талаб қилинади?",
    ],
    [
        "Firma uchun bankda hisob ochishga qaysi hujjatlarni tayyorlayman?",
        "Тадбиркорлик ҳисобрақамини очишга нима олиб борилади?",
    ],
    [
        "Menga tayinlangan ijtimoiy yordam miqdorini qayerdan ko'rishim mumkin?",
        "Тайинланган нафақам тўғрисидаги маълумотни қаердан билиб оламан?",
    ],
    [
        "Kasallik tufayli armiyaga yaroqsizligimni kim belgilaydi?",
        "Ҳарбий хизматга соғлиқ жиҳатидан яроқлиликни ким текширади?",
    ],
    [
        "Boshqa davlatda nikohdan o'tganmiz, bu yerda tan olinishi uchun nima qilamiz?",
        "Хорижда тузилган никоҳ ҳужжатини Ўзбекистонда қандай тақдим этамиз?",
    ],
    [
        "Davlat xizmatlarining shartlari va bojlari to'plangan manba kerak",
        "Давлат хизматлари ҳақида маслаҳатни қайси портал ёки рақамдан оламан?",
    ],
    [
        "Ajrashganimdan keyin ajrim guvohnomasini qayerdan olib ketaman?",
        "Никоҳ бекор қилингани ҳақида гувоҳнома олишга қаерга бораман?",
    ],
    [
        "Pensiya uchun tirik ekanligimni tasdiqlovchi hujjatni qanday olaman?",
        "Хориждаги пенсионер тириклик ҳақида маълумотномани қаердан олади?",
    ],
    [
        "Jiddiy yo'l qoidasi buzilishi sabab haydash huquqidan mahrum qilishadimi?",
        "Қоидабузарликдан кейин ҳайдовчилик гувоҳномасини олиб қўйиш мумкинми?",
    ],
    [
        "Xorijlik sarmoyador shu yerda o'z korxonasini ro'yxatdan o'tkaza oladimi?",
        "Чет эл фуқароси иштирокида Ўзбекистонда фирма очса бўладими?",
    ],
    [
        "Pensiyamni xato hisoblashgan deb o'ylayman, qayta ko'rishni kimdan so'rayman?",
        "Нафақа нотўғри ҳисобланганда қайси идора тузатади?",
    ],
    [
        "Harbiy zaxirada turganlarni o'quv yig'inlariga kim chaqiradi?",
        "Захирадагиларнинг ҳарбий сборга чақирилиши қандай бўлади?",
    ],
    [
        "Sud ishim bo'yicha chiqarilgan qarordan nusxa kerak, qayerdan olaman?",
        "Суд қарорининг кўчирмасини қандай сўраб олиш мумкин?",
    ],
    [
        "Arizada kerak bo'lgan ma'lumotlarni tashkilotlar o'zaro elektron oladimi?",
        "Идоралар маълумотни бир-биридан оладими ёки барчасини ўзим йиғаманми?",
    ],
    [
        "Yotib qolgan bemor idoraga bora olmasa ID-kartani qanday oladi?",
        "Ҳаракатлана олмайдиган одамнинг биометрик маълумотларини уйида олишадими?",
    ],
    [
        "Uy sotilib ketganidan so'ng undagi doimiy ro'yxatdagilar qayerga yoziladi?",
        "Сотилган хонадонда пропискада турганлар қайта рўйхатдан ўтиши керакми?",
    ],
    [
        "Oldin yozgan vasiyatimni bekor qilmoqchi bo'lsam, nima qilaman?",
        "Васиятнома мазмунини кейинчалик ўзгартирсам бўладими?",
    ],
    [
        "Mashinani boshqa rangga bo'yasam bu o'zgarishni qayd ettirish kerakmi?",
        "Автомобиль двигатели алмашса ҳужжатга ўзгартиш киритиладими?",
    ],
    [
        "Faoliyat ruxsatnomasining amal qilish vaqti tugadi, endi nima qilishim kerak?",
        "Лицензия муддати ўтгандан кейин уни узайтириш керакми?",
    ],
    [
        "Oldin kelib turgan nafaqa to'lovi to'xtadi, qaysi idoraga boraman?",
        "Нафақам келмай қолса кимга мурожаат қилиш лозим?",
    ],
    [
        "Armiyaga chaqirilayotgan yigit tibbiy ko'rik uchun qayerga boradi?",
        "Чақирилувчиларнинг тиббий комиссияси қаерда ташкил қилинади?",
    ],
    [
        "Yollagan advokatim xizmatidan noroziman, ustidan kimga yozaman?",
        "Адвокатга оид шикоятни қайси ташкилот қабул қилади?",
    ],
    [
        "My.gov kabinetimda telefon raqami va bildirishnomalarni qayerdan o'zgartiraman?",
        "Электрон ҳукумат шахсий кабинети тилини қандай созлайман?",
    ],
]
ood = [
    "Uchburchakning yuzini hisoblash formulasini yozing",
    "Jupiterning nechta yo'ldoshi bor?",
    "Menga osh pishirish retseptini ayting",
    "Python dasturida ro'yxatni qanday saralayman?",
    "Bugun Barselona o'yinida hisob nechchi bo'ldi?",
    "Ertangi havo haroratini aytib bering",
    "Mushugim nima sababdan ovqat yemayapti?",
    "Kompyuterimga qaysi videokartani olsam yaxshi?",
    "Qo'shiq matnini menga davom ettirib bering",
    "Alisher Navoiyning birinchi asari qaysi edi?",
    "Kvadrat tenglamani yechib bering: x*x-5*x+6=0",
    "Yangi filmga chipta bron qilib bering",
    "Ingliz tilidagi fe'llar zamonlarini tushuntiring",
    "Do'stimning tug'ilgan kuniga tabrik yozing",
    "Шоколадли тортни қандай пишириш мумкин?",
    "Ойнинг Ердан узоқлиги неча километр?",
    "Футбол бўйича жаҳон чемпионатида ким ютган?",
    "Телефоним батареясини қандай алмаштираман?",
    "Нега осмоннинг ранги кўк?",
    "Шахматда от қандай юради?",
    "Mening pasportimning seriya va raqamini topib ayting",
    "Hozir shaxsiy bank hisobimdagi qoldiqni tekshirib bering",
    "Kecha to'lagan jarimamning aniq chek raqamini toping",
    "Suddagi shaxsiy ishimni bugun qaysi sudya ko'rayotganini ayting",
    "Uyimning aniq bozor narxini hozir hisoblab bering",
    "Mening soliq kabinetim parolini tiklab kirib bering",
    "Yo'qolgan avtomobilim hozir qaysi ko'chada ekanini toping",
    "Bugun tumanimiz notariusi soat nechada tushlik qiladi?",
    "Shaxsiy kreditimning qolgan qarzi necha so'mligini ko'rsating",
    "Kasalligimga aniq tashxis qo'yib dori yozib bering",
    "Mening arizam navbatda nechanchi o'rinda turganini hozir ko'rsating",
    "Menga yangi bank kartasi uchun PIN-kod o'ylab bering",
    "Qo'shnimning kadastr hujjatidagi maxfiy raqamini toping",
    "Boshqa odamning nikohdagi turmush o'rtog'i ismini aniqlang",
    "Менинг шахсий идентификация рақамимни айтиб беринг",
    "Бугун мактабимизда қайси ўқитувчи навбатчи экан?",
    "Армиядаги акам ҳозир қайси хонада турганини топинг",
    "Банк картамдан кеча ким пул ечганини аниқлаб беринг",
    "Ҳозир аэропортда менинг паспортим билан кимдир ўтдими?",
    "Менга тегишли суд жаримасини ҳозир тўлаб беринг",
]
assert len(sources) == len(paraphrases) == 40
items = []
for i, variants in enumerate(paraphrases):
    expected = [sources[i]["question"]]
    if i in (14, 22):
        expected = [sources[14]["question"], sources[22]["question"]]
    items.extend({"query": query, "expected": expected} for query in variants)
items.extend({"query": query, "expected": []} for query in ood)
path = root / "eval/holdout.jsonl"
assert not path.exists(), "Frozen holdout must never be overwritten"
path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in items))
(root / "eval/dataset.jsonl").rename(root / "eval/dev.jsonl")
manifest = {
    "created": "2026-10-11",
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "in_domain": 80,
    "out_of_domain": 40,
    "new_answer_ids": 40,
    "origin": (
        "New developer-authored paraphrases and OOD queries; 40 answer IDs absent from legacy "
        "evaluation. All 245 previously inspected/tuned queries remain development data."
    ),
    "policy": (
        "Tune only on dev.jsonl. Select and freeze one candidate before scoring holdout. "
        "Compare aggregate metrics once; do not inspect holdout errors or retune. Reject a "
        "candidate if any protected metric regresses."
    ),
}
(root / "eval/holdout_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
for file in [
    root / "eval/evaluate.py",
    root / "qa/test_regressions.py",
    root / "qa/audit_eval.py",
    root / "qa/evaluate_http.py",
]:
    file.write_text(file.read_text().replace("dataset.jsonl", "dev.jsonl"))
