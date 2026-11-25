"""Rule-based furniture assistant (English / Uzbek / Russian).

NOT an AI model: it detects the language with simple script/keyword rules, answers a fixed set of
small-talk phrases, and parses dimensions with regular expressions to call the internal calculation
engine. Unsupported requests get an honest answer in the user's language."""
from __future__ import annotations

import re

from apps.calculations import engine
from apps.cutting_lists import optimizer

NUM = r"(\d+(?:[.,]\d+)?)"
SEP = r"\s*(?:mm|мм)?\s*[x×*хX]\s*"
DIMS = re.compile(NUM + SEP + NUM + SEP + NUM, re.I)

# ---------------------------------------------------------------- language detection
UZ_WORDS = re.compile(
    r"\b(salom|assalomu|assalom|rahmat|qalaysiz|qalaysan|qanday|nima|kerak|hisobla\w*|hisob|shkaf|tokcha\w*|eshik\w*|yashik\w*|kenglik|balandlik|"
    r"chuqurlik|yordam|xayr|sen|siz|ha|yoq|mebel|bor|menga|qil\w*|qila|olasan|olasiz|kimsan|kimsiz|yaxshi|zo'r|zor|ismingiz|isming|bilan|uchun|"
    r"ta|ko'rishguncha|hayr|kesish|javon|stol|bo'yi|eni)\b|o[‘’'`]|g[‘’'`]", re.I)
UZ_CYR = re.compile(r"[ўқғҳЎҚҒҲ]")


def detect_lang(text: str, fallback: str = "en") -> str:
    if UZ_CYR.search(text):
        return "uz"
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    if UZ_WORDS.search(text):
        return "uz"
    if re.search(r"[a-zA-Z]{3,}", text):
        return "en"  # plain Latin words with no Uzbek marker
    return fallback if fallback in ("en", "uz", "ru") else "en"


# ---------------------------------------------------------------- small talk
SMALL = [
    ("greet", r"(hi|hello|hey|yo|good (morning|afternoon|evening)|salom|assalomu alaykum|assalom|assalomu|hayrli (kun|tong|kech)|привет|здравствуй\w*|добрый (день|вечер)|доброе утро|салом)"),
    ("how", r"(how are you|how('s| is) it going|what'?s up|qalaysiz|qalaysan|ahvol\w*|nima gap|yaxshimisiz|как дела|как ты|как поживаешь|что нового)"),
    ("thanks", r"(thanks?|thank you|thx|rahmat|katta rahmat|tashakkur|спасибо|благодарю)"),
    ("bye", r"(bye|goodbye|see you|xayr|ko'rishguncha|hayr|до свидания|пока)"),
    ("identity", r"(who are you|what are you|are you (an? )?(ai|bot|robot)|kimsan|kimsiz|sen kimsan|siz kimsiz|sen nimasan|ты кто|кто ты|кто вы|ты (ии|бот|робот))"),
    ("name", r"(your name|ismingiz nima|isming nima|isming|как тебя зовут|как вас зовут)"),
    ("help", r"(help|what can you do|yordam|nima qila olasan|nima qila olasiz|nimalarga qodirsan|помощь|помоги\w*|что ты умеешь|что вы умеете)"),
    ("ok", r"(ok|okay|great|nice|cool|good|yaxshi|zo'r|zor|ajoyib|отлично|хорошо|ладно|супер)"),
    ("yes", r"(yes|yeah|ha|ha ?albatta|да)"),
    ("no", r"(no|nope|yo'q|yoq|нет)"),
]
SMALL_RE = [(k, re.compile(rf"^\W*{p}(?:\W+[\w']+){{0,2}}\W*$", re.I)) for k, p in SMALL]

T = {
    "en": {
        "greet": "Hello! I am the MEBELCHI AI assistant. Tell me the size of a cabinet, for example `cabinet 800x2000x400 with 3 shelves and 2 doors`, and I will calculate the panels.",
        "how": "I am a program, so I have no feelings, but everything is running fine. What would you like to calculate?",
        "thanks": "You are welcome! Send me another size whenever you need a calculation.",
        "bye": "Goodbye! Your projects stay saved in your workspace.",
        "identity": "I am the built-in MEBELCHI AI assistant. I am a rule-based tool, not a language model: I understand dimensions and a few commands, and I calculate furniture panels, areas and sheets.",
        "name": "I am MEBELCHI AI, a rule-based furniture assistant.",
        "ok": "Glad to hear it! Give me dimensions whenever you are ready, for example `wardrobe 1000x2200x580 with 4 shelves`.",
        "yes": "Great. Send me the size of the furniture (width x height x depth in mm).",
        "no": "No problem. I am here when you need a calculation.",
        "help": """I am the built-in MEBELCHI AI assistant. I am a rule-based tool, not a language model, so I understand a limited set of commands:

- **Calculate a cabinet:** `cabinet 800x2000x400 with 3 shelves and 2 doors` (width x height x depth in mm)
- **Cutting list and sheet count:** `cutting list for wardrobe 1000x2200x580, 4 shelves, 2 doors, 18 mm`
- **Drawers:** `chest 900x1000x480 with 4 drawers`
- **3D preview:** use the button under a calculation

You can also write sizes separately: `width 900 height 720 depth 560 thickness 18 shelves 2`. I answer in the language you write in (English, Uzbek, Russian).
For anything else (free-form design advice, reading drawings or sketches) please use the editor tools directly.""",
        "unsupported": "I could not turn that into a calculation. I am a rule-based assistant and I only understand dimension-based commands and simple chat.\n\nTry something like `cabinet 800x2000x400 with 3 shelves and 2 doors`, or type `help`.",
        "attach": "\n\nAttachments received and stored: {names}. Automatic reading of images, PDFs, drawings or sketches is **not implemented** yet, so please enter the dimensions as text.",
        "need": "I need the **{missing}** to calculate. Give all three sizes in mm, for example `cabinet 800x2000x400 with 2 shelves` (width x height x depth).",
        "invalid": "I cannot calculate that input:",
        "cab": "**Cabinet {w:g} x {h:g} x {d:g} mm**, {t:g} mm board, {s} shelves, {dr} doors, {dw} drawers.",
        "cols": ["Part", "Width", "Height", "Thick.", "Qty", "Material", "Edge banding"],
        "panels": "- Panels: **{n}**, total area **{a} m2**", "edge": "- Edge banding: **{e} m**",
        "sheets": "**{m} sheets (2800 x 2070 mm, 3 mm kerf):** {n} sheet(s), utilization {u}%, waste {w}%.",
        "warn": "Warning", "disc": "_Calculated output for professional review. Not verified for manufacture._",
        "fields": {"width": "width", "height": "height", "depth": "depth"},
    },
    "uz": {
        "greet": "Assalomu alaykum! Men MEBELCHI AI yordamchisiman. Mebel o'lchamini yozing, masalan `shkaf 800x2000x400, 3 ta tokcha va 2 ta eshik`, men panellarni hisoblab beraman.",
        "how": "Men dasturman, shuning uchun his-tuyg'um yo'q, lekin hammasi joyida. Nimani hisoblab beray?",
        "thanks": "Arzimaydi! Hisob-kitob kerak bo'lsa, yana o'lcham yuboring.",
        "bye": "Xayr! Loyihalaringiz ish maydonida saqlanib turadi.",
        "identity": "Men MEBELCHI AI ichki yordamchisiman. Men til modeli emas, qoidalarga asoslangan dasturman: o'lchamlarni va bir nechta buyruqni tushunaman, mebel panellari, maydoni va listlarini hisoblayman.",
        "name": "Men MEBELCHI AI, qoidalarga asoslangan mebel yordamchisiman.",
        "ok": "Yaxshi! Tayyor bo'lganda o'lchamlarni yozing, masalan `javon 1000x2200x580, 4 ta tokcha`.",
        "yes": "Ajoyib. Mebel o'lchamini yuboring (eni x balandligi x chuqurligi, mm da).",
        "no": "Mayli. Hisob kerak bo'lsa, shu yerdaman.",
        "help": """Men MEBELCHI AI ichki yordamchisiman. Men til modeli emas, qoidalarga asoslangan dasturman, shuning uchun cheklangan buyruqlarni tushunaman:

- **Shkafni hisoblash:** `shkaf 800x2000x400, 3 ta tokcha va 2 ta eshik` (eni x balandligi x chuqurligi, mm)
- **Kesish ro'yxati va list soni:** `kesish ro'yxati javon 1000x2200x580, 4 ta tokcha, 2 ta eshik, 18 mm`
- **Yashiklar:** `komod 900x1000x480, 4 ta yashik`
- **3D ko'rinish:** hisob ostidagi tugmani bosing

O'lchamlarni alohida ham yozish mumkin: `kenglik 900 balandlik 720 chuqurlik 560 tokcha 2`. Men siz yozgan tilda javob beraman (o'zbek, rus, ingliz).
Boshqa narsalar (erkin dizayn maslahati, chizma yoki eskizni o'qish) uchun muharrir vositalaridan foydalaning.""",
        "unsupported": "Buni hisobga aylantira olmadim. Men qoidalarga asoslangan yordamchiman, faqat o'lchamli buyruqlarni va oddiy suhbatni tushunaman.\n\nMasalan: `shkaf 800x2000x400, 3 ta tokcha va 2 ta eshik` deb yozing yoki `yordam` deng.",
        "attach": "\n\nFayllar qabul qilindi va saqlandi: {names}. Rasm, PDF, chizma yoki eskizni avtomatik o'qish hali **mavjud emas**, shuning uchun o'lchamlarni matn bilan yozing.",
        "need": "Hisoblash uchun **{missing}** kerak. Uchala o'lchamni mm da yozing, masalan `shkaf 800x2000x400, 2 ta tokcha` (eni x balandligi x chuqurligi).",
        "invalid": "Bu ma'lumot bilan hisoblay olmayman:",
        "cab": "**Shkaf {w:g} x {h:g} x {d:g} mm**, {t:g} mm list, {s} ta tokcha, {dr} ta eshik, {dw} ta yashik.",
        "cols": ["Detal", "Eni", "Bo'yi", "Qalinlik", "Soni", "Material", "Kromka"],
        "panels": "- Panellar: **{n}**, umumiy maydon **{a} m2**", "edge": "- Kromka: **{e} m**",
        "sheets": "**{m} listlar (2800 x 2070 mm, 3 mm kesim):** {n} ta list, foydalanish {u}%, chiqindi {w}%.",
        "warn": "Ogohlantirish", "disc": "_Hisob-kitob mutaxassis tekshiruvi uchun. Ishlab chiqarishga tasdiqlanmagan._",
        "fields": {"width": "eni (kenglik)", "height": "balandlik", "depth": "chuqurlik"},
    },
    "ru": {
        "greet": "Здравствуйте! Я помощник MEBELCHI AI. Напишите размеры мебели, например `шкаф 800x2000x400, 3 полки и 2 двери`, и я рассчитаю панели.",
        "how": "Я программа, поэтому у меня нет чувств, но всё работает отлично. Что рассчитать?",
        "thanks": "Пожалуйста! Присылайте новые размеры, когда нужен расчёт.",
        "bye": "До свидания! Ваши проекты сохранены в рабочем пространстве.",
        "identity": "Я встроенный помощник MEBELCHI AI. Я не языковая модель, а программа на правилах: понимаю размеры и несколько команд, считаю панели, площадь и листы.",
        "name": "Я MEBELCHI AI, помощник по мебели на основе правил.",
        "ok": "Отлично! Когда будете готовы, напишите размеры, например `шкаф 1000x2200x580, 4 полки`.",
        "yes": "Хорошо. Пришлите размеры мебели (ширина x высота x глубина, в мм).",
        "no": "Хорошо. Я здесь, когда понадобится расчёт.",
        "help": """Я встроенный помощник MEBELCHI AI. Я не языковая модель, а программа на правилах, поэтому понимаю ограниченный набор команд:

- **Расчёт шкафа:** `шкаф 800x2000x400, 3 полки и 2 двери` (ширина x высота x глубина, мм)
- **Раскрой и число листов:** `раскрой шкаф 1000x2200x580, 4 полки, 2 двери, 18 мм`
- **Ящики:** `комод 900x1000x480, 4 ящика`
- **3D-просмотр:** кнопка под расчётом

Размеры можно писать и по отдельности: `ширина 900 высота 720 глубина 560 полки 2`. Я отвечаю на том языке, на котором вы пишете (русский, узбекский, английский).
Для остального (свободные советы по дизайну, чтение чертежей и эскизов) используйте инструменты редактора.""",
        "unsupported": "Я не смог превратить это в расчёт. Я помощник на правилах и понимаю только команды с размерами и простое общение.\n\nПопробуйте: `шкаф 800x2000x400, 3 полки и 2 двери` или напишите `помощь`.",
        "attach": "\n\nФайлы получены и сохранены: {names}. Автоматическое чтение изображений, PDF, чертежей и эскизов **пока не реализовано**, поэтому введите размеры текстом.",
        "need": "Для расчёта нужны: **{missing}**. Укажите все три размера в мм, например `шкаф 800x2000x400, 2 полки` (ширина x высота x глубина).",
        "invalid": "Я не могу рассчитать такие данные:",
        "cab": "**Шкаф {w:g} x {h:g} x {d:g} мм**, плита {t:g} мм, полок: {s}, дверей: {dr}, ящиков: {dw}.",
        "cols": ["Деталь", "Ширина", "Высота", "Толщ.", "Кол-во", "Материал", "Кромка"],
        "panels": "- Панелей: **{n}**, общая площадь **{a} м2**", "edge": "- Кромка: **{e} м**",
        "sheets": "**Листы {m} (2800 x 2070 мм, рез 3 мм):** {n} шт., использование {u}%, отходы {w}%.",
        "warn": "Предупреждение", "disc": "_Расчёт для проверки специалистом. Не подтверждён для производства._",
        "fields": {"width": "ширину", "height": "высоту", "depth": "глубину"},
    },
}
PART = {
    "uz": {"Side panel": "Yon devor", "Top panel": "Usti", "Bottom panel": "Osti", "Shelf": "Tokcha", "Back panel": "Orqa devor (HDF)", "Door": "Eshik",
           "Drawer front": "Yashik fasadi", "Drawer side": "Yashik yoni", "Drawer back": "Yashik orqasi", "Drawer inner front": "Yashik old devori", "Drawer bottom": "Yashik tagi",
           "Front top rail": "Old usti plankasi", "Rear top rail": "Orqa usti plankasi", "Plinth": "Sokol", "Hanging rail": "Osish plankasi", "Sliding door": "Surma eshik"},
    "ru": {"Side panel": "Боковина", "Top panel": "Верх", "Bottom panel": "Низ", "Shelf": "Полка", "Back panel": "Задняя стенка (ХДФ)", "Door": "Дверь",
           "Drawer front": "Фасад ящика", "Drawer side": "Бок ящика", "Drawer back": "Задник ящика", "Drawer inner front": "Передняя стенка ящика", "Drawer bottom": "Дно ящика",
           "Front top rail": "Передняя верхняя планка", "Rear top rail": "Задняя верхняя планка", "Plinth": "Цоколь", "Hanging rail": "Навесная планка", "Sliding door": "Раздвижная дверь"},
}
EDGE = {
    "uz": {"front edge (1 x height)": "old qirra (1 x bo'yi)", "front edge (1 x width)": "old qirra (1 x eni)", "no edge banding": "kromkasiz", "all 4 edges": "4 qirra",
           "top edge (1 x length)": "yuqori qirra (1 x uzunlik)", "top edge (1 x width)": "yuqori qirra (1 x eni)"},
    "ru": {"front edge (1 x height)": "передняя кромка (1 x высота)", "front edge (1 x width)": "передняя кромка (1 x ширина)", "no edge banding": "без кромки", "all 4 edges": "4 кромки",
           "top edge (1 x length)": "верхняя кромка (1 x длина)", "top edge (1 x width)": "верхняя кромка (1 x ширина)"},
}
WARN = [  # (regex on the English engine warning, {lang: template})
    (r"Door width (\d+) mm exceeds 600", {"uz": "Eshik eni {0} mm, 600 mm dan oshadi; egilish va sharnir yukini kamaytirish uchun eshiklar sonini oshiring.",
                                           "ru": "Ширина двери {0} мм превышает 600 мм; увеличьте число дверей, чтобы уменьшить перекос и нагрузку на петли."}),
    (r"Door height exceeds 2200", {"uz": "Eshik balandligi 2200 mm dan oshadi; sharnirlar sonini va barqarorlikni tekshiring.",
                                    "ru": "Высота двери больше 2200 мм; проверьте число петель и устойчивость."}),
    (r"Shelf span (\d+) mm at (\S+) mm", {"uz": "{0} mm oraliqdagi tokcha {1} mm qalinlikda egilishi mumkin; o'rta tayanch yoki qalinroq list qo'ying.",
                                           "ru": "Полка пролётом {0} мм при толщине {1} мм может прогнуться; добавьте центральную опору или возьмите плиту толще."}),
    (r"Back thickness above 6", {"uz": "HDF uchun 6 mm dan qalin orqa devor odatiy emas.", "ru": "Толщина задней стенки из ХДФ больше 6 мм встречается редко."}),
    (r"Very shallow carcass", {"uz": "Korpus juda sayoz; tokchalar qulayligini tekshiring.", "ru": "Корпус очень мелкий; проверьте удобство полок."}),
]
CALC_WORDS = re.compile(
    r"(cutting|optimi|sheet|nesting|layout|calculate|cabinet|wardrobe|shelf|shelves|drawer|door|unit|chest|bookcase|material|panel|"
    r"shkaf|tokcha|eshik|yashik|javon|komod|hisobla|hisob|kesish|kesim|list|"
    r"шкаф|полк|двер|ящик|комод|тумб|рассчит|расчёт|расчет|посчит|раскрой|панел)", re.I)
CUT_WORDS = re.compile(r"(cutting|optimi|sheet|nesting|layout|kesish|kesim|list soni|раскрой|лист)", re.I)

CAPABILITIES = T["en"]["help"]
UNSUPPORTED = T["en"]["unsupported"]


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def parse(text: str) -> dict:
    t = text.lower()
    out: dict = {}
    m = DIMS.search(t)
    if m:
        out["width"], out["height"], out["depth"] = (_f(m.group(i)) for i in (1, 2, 3))
    for key, words in (("width", r"width|kenglik|eni|ширина"), ("height", r"height|balandlik|bo'yi|высота"), ("depth", r"depth|chuqurlik|глубина")):
        mm = re.search(rf"\b(?:{words})\b\s*[:=]?\s*{NUM}", t)
        if mm:
            out[key] = _f(mm.group(1))
    mm = re.search(rf"(?:thickness|qalinlik|толщина)\s*[:=]?\s*{NUM}", t) or re.search(rf"{NUM}\s*(?:mm|мм)\s*(?:thick|board|panel|mdf|ldsp|chipboard|list|плита|лдсп)", t)
    if mm:
        out["thickness"] = _f(mm.group(1))
    for key, pat in (("shelves", r"shel(?:ves|f)|tokcha\w*|polka\w*|полк\w*|полок"), ("doors", r"doors?|eshik\w*|двер\w*|дверц\w*|створ\w*"),
                     ("drawers", r"drawers?|yashik\w*|ящик\w*")):
        mm = re.search(rf"(\d+)\s*(?:ta\s*)?(?:{pat})", t)
        if mm:
            out[key] = int(mm.group(1))
    return out


def _table(parts, lang) -> str:
    c = T[lang]["cols"]
    rows = ["| " + " | ".join(c) + " |", "|---|---:|---:|---:|---:|---|---|"]
    for p in parts:
        name = PART.get(lang, {}).get(p["name"], p["name"])
        edge = EDGE.get(lang, {}).get(p["edge_note"], p["edge_note"]) or "-"
        rows.append(f"| {name} | {p['width']:g} | {p['height']:g} | {p['thickness']:g} | {p['quantity']} | {p['material']} | {edge} |")
    return "\n".join(rows)


def _warning(w: str, lang: str) -> str:
    if lang == "en":
        return w
    for pat, tpl in WARN:
        m = re.search(pat, w)
        if m:
            return tpl[lang].format(*m.groups())
    return w


def _small_talk(text: str):
    t = text.strip().lower()
    for key, rx in SMALL_RE:
        if rx.match(t):
            return key
    # greeting followed by a short extra phrase ("salom, qalaysan")
    parts = re.split(r"[,.!?;]+", t)
    keys = [next((k for k, rx in SMALL_RE if rx.match(p.strip())), None) for p in parts if p.strip()]
    if keys and all(keys):
        return keys[-1] if keys[-1] != "greet" else keys[0]
    return None


def respond(text: str, attachments: list | None = None, default_lang: str = "en") -> tuple[str, dict]:
    lang = detect_lang(text, default_lang)
    tr = T[lang]
    note = ""
    if attachments:
        note = tr["attach"].format(names=", ".join(a["name"] for a in attachments))

    params = parse(text)
    has_calc = bool(CALC_WORDS.search(text)) or {"width", "height", "depth"} & set(params)

    if not has_calc:
        key = _small_talk(text)
        if key == "help" or re.fullmatch(r"\W*(\?|yordam|помощь)\W*", text.strip(), re.I):
            return tr["help"] + note, {"intent": "help", "lang": lang}
        if key:
            return tr[key] + note, {"intent": "smalltalk", "lang": lang}
        return tr["unsupported"] + note, {"intent": "unsupported", "lang": lang}

    wants_cut = bool(CUT_WORDS.search(text))
    missing = [k for k in ("width", "height", "depth") if k not in params]
    if missing:
        names = ", ".join(tr["fields"][k] for k in missing)
        return tr["need"].format(missing=names) + note, {"intent": "need_input", "missing": missing, "partial": params, "lang": lang}

    try:
        calc = engine.calculate(params)
    except engine.EngineValidationError as e:
        issues = "\n".join(f"- **{k}**: {v}" for k, v in e.errors.items())
        return f"{tr['invalid']}\n\n{issues}" + note, {"intent": "invalid_input", "errors": e.errors, "lang": lang}

    s, inp = calc["summary"], calc["input"]
    lines = [tr["cab"].format(w=inp["width"], h=inp["height"], d=inp["depth"], t=inp["thickness"], s=inp["shelves"], dr=inp["doors"], dw=inp["drawers"]),
             "", _table(calc["parts"], lang), "",
             tr["panels"].format(n=s["panel_count"], a=s["total_area_m2"]), tr["edge"].format(e=s["edge_banding_m"])]
    labels = {"en": ["Open in 3D viewer", "Create cutting list"], "uz": ["3D ko'rinishda ochish", "Kesish ro'yxatini yaratish"], "ru": ["Открыть в 3D", "Создать карту раскроя"]}[lang]
    actions = [{"type": "open_3d", "label": labels[0]}, {"type": "create_cutting_list", "label": labels[1]}]
    meta = {"intent": "calculation", "input": inp, "summary": s, "parts": calc["parts"], "actions": actions, "lang": lang}

    if wants_cut:
        main = [p for p in calc["parts"] if p["material"] == inp["material"]]
        try:
            o = optimizer.optimize(main, 2800, 2070)["summary"]
            lines += ["", tr["sheets"].format(m=inp["material"], n=o["sheet_count"], u=o["utilization_pct"], w=o["waste_pct"])]
            meta["optimization"] = o
        except optimizer.OptimizerError as e:  # pragma: no cover
            lines += ["", f"Optimization failed: {e}"]
    for w in calc["warnings"]:
        lines.append(f"\n> {tr['warn']}: {_warning(w, lang)}")
    lines += ["", tr["disc"]]
    return "\n".join(lines) + note, meta
