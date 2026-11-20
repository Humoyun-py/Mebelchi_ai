"""Public metadata and marketing content served to the client, so the UI has no hard-coded business data."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.calculations import engine
from apps.designs.presets import ROOMS, STYLES, L
from apps.materials.models import Material
from apps.furniture.seed_data import CATEGORIES as FURNITURE_CATEGORIES
from apps.projects.models import Project

CAT_LABELS = {
    "cabinet": L("Cabinet", "Shkaf", "Шкаф"), "kitchen": L("Kitchen", "Oshxona", "Кухня"), "wardrobe": L("Wardrobe", "Garderob", "Гардероб"),
    "tv_unit": L("TV unit", "TV tumba", "ТВ-тумба"), "bedroom": L("Bedroom", "Yotoqxona", "Спальня"), "office": L("Office", "Ofis", "Офис"),
    "living": L("Living room", "Mehmonxona", "Гостиная"), "other": L("Other", "Boshqa", "Другое"),
}
BOARD_LABELS = {"MDF": L("MDF", "MDF", "МДФ"), "LDSP": L("Laminated chipboard", "LDSP (laminat)", "ЛДСП"), "PLYWOOD": L("Plywood", "Fanera", "Фанера")}
EXPORT_FORMATS = ["PDF", "Excel", "GLB", "glTF", "OBJ"]
TOOLS = ["calculator", "cutting_list", "optimizer", "viewer_3d", "editor", "interior"]
LANGUAGES = ["en", "uz", "ru"]

SHOWCASE = [
    {"name": L("Kitchen", "Oshxona", "Кухня"), "input": dict(width=800, height=720, depth=560, thickness=18, shelves=1, doors=2, drawers=0), "color": "#d8c3a5"},
    {"name": L("Wardrobe", "Garderob", "Гардероб"), "input": dict(width=1500, height=2200, depth=580, thickness=18, shelves=5, doors=3, drawers=0), "color": "#c9a27a"},
    {"name": L("TV unit", "TV tumba", "ТВ-тумба"), "input": dict(width=1800, height=450, depth=400, thickness=18, shelves=1, doors=2, drawers=0), "color": "#8b6f4e"},
    {"name": L("Bedroom", "Yotoqxona", "Спальня"), "input": dict(width=900, height=1000, depth=480, thickness=18, shelves=0, doors=0, drawers=4), "color": "#e5e7eb"},
    {"name": L("Office", "Ofis", "Офис"), "input": dict(width=900, height=1200, depth=450, thickness=18, shelves=2, doors=2, drawers=0), "color": "#94a3b8"},
]

FEATURES = [
    ("cpu", L("Furniture Designer", "Mebel dizayneri", "Дизайнер мебели"),
     L("Describe a cabinet in plain dimensions and get a full parametric parts model. A rule-based assistant, honest about what it can and cannot do.",
       "Shkafni oddiy o'lchamlar bilan yozing va to'liq parametrik detallar modelini oling. Qoidalarga asoslangan yordamchi, nimaga qodir va nimaga qodir emasligini ochiq aytadi.",
       "Опишите шкаф обычными размерами и получите полную параметрическую модель деталей. Помощник на правилах, честный в своих возможностях.")),
    ("scissors", L("Smart Cutting List", "Aqlli kesish ro'yxati", "Умная карта раскроя"),
     L("Every part with size, quantity, material and edge banding. Export to PDF or Excel with a professional-review notice.",
       "Har bir detal o'lchami, soni, materiali va kromkasi bilan. PDF yoki Excel ga mutaxassis tekshiruvi eslatmasi bilan eksport.",
       "Каждая деталь с размером, количеством, материалом и кромкой. Экспорт в PDF или Excel с пометкой о проверке специалистом.")),
    ("calculator", L("Material Calculator", "Material kalkulyatori", "Калькулятор материалов"),
     L("Panels, total area, edge banding length and warnings, with the engineering assumptions shown next to every result.",
       "Panellar, umumiy maydon, kromka uzunligi va ogohlantirishlar, har bir natija yonida muhandislik taxminlari bilan.",
       "Панели, общая площадь, длина кромки и предупреждения, с инженерными допущениями рядом с каждым результатом.")),
    ("layers", L("Material Optimizer", "Material optimizatori", "Оптимизатор материалов"),
     L("Guillotine sheet packing with kerf and trim. Utilization, waste, leftover strip and a drawn layout per sheet.",
       "Kesim va chetki qoldiqni hisobga olgan holda list joylashtirish. Foydalanish, chiqindi, qoldiq chiziq va har bir list uchun chizma.",
       "Гильотинный раскрой листов с учётом реза и обрезки. Использование, отходы, остаток и схема на каждый лист.")),
    ("boxes", L("3D Furniture Designer", "3D mebel dizayneri", "3D-дизайнер мебели"),
     L("Interactive 3D built from your parameters. Rotate, zoom, pan, recolor and export GLB, glTF or OBJ.",
       "Parametrlaringizdan qurilgan interaktiv 3D. Aylantiring, yaqinlashtiring, rangini o'zgartiring va GLB, glTF yoki OBJ ga eksport qiling.",
       "Интерактивное 3D из ваших параметров. Вращайте, масштабируйте, меняйте цвет и экспортируйте в GLB, glTF или OBJ.")),
    ("sofa", L("Interior Designer", "Interyer dizayneri", "Дизайнер интерьера"),
     L("Upload room photos and configure style, colors, layout and dimensions. Manual configuration, no automatic image understanding.",
       "Xona rasmlarini yuklang va uslub, rang, joylashuv va o'lchamlarni sozlang. Qo'lda sozlash, rasmni avtomatik tushunish yo'q.",
       "Загрузите фото комнат и настройте стиль, цвета, расстановку и размеры. Ручная настройка, без автоматического анализа изображений.")),
]
STEPS = [
    ("ruler", L("Describe your furniture", "Mebelingizni tasvirlang", "Опишите вашу мебель"), L("Type dimensions to the assistant or start from a template.", "O'lchamlarni yordamchiga yozing yoki shablondan boshlang.", "Напишите размеры помощнику или начните с шаблона.")),
    ("boxes", L("Customize your design", "Dizaynni sozlang", "Настройте дизайн"), L("Adjust size, thickness, shelves, doors, drawers, material and color in 3D.", "O'lcham, qalinlik, tokcha, eshik, yashik, material va rangni 3D da sozlang.", "Меняйте размер, толщину, полки, двери, ящики, материал и цвет в 3D.")),
    ("sheet", L("Calculate and prepare production", "Hisoblang va ishlab chiqarishga tayyorlang", "Рассчитайте и подготовьте производство"), L("Get the cutting list, optimized sheet layouts and exports, ready for professional review.", "Kesish ro'yxati, optimallashtirilgan list sxemalari va eksportlarni oling, mutaxassis tekshiruviga tayyor.", "Получите карту раскроя, оптимизированные схемы листов и экспорт, готовые к проверке специалистом.")),
]
FAQ = [
    (L("Does MEBELCHI AI use ChatGPT or another AI service?", "MEBELCHI AI ChatGPT yoki boshqa AI xizmatidan foydalanadimi?", "Использует ли MEBELCHI AI ChatGPT или другой ИИ-сервис?"),
     L("No. Every calculation, layout and 3D model is produced by our own Python algorithms. The assistant is a rule-based command parser and says so when it cannot answer. The architecture is ready for our own trained models in the future.",
       "Yo'q. Barcha hisob-kitob, joylashtirish va 3D modellar bizning o'z Python algoritmlarimiz bilan yaratiladi. Yordamchi qoidalarga asoslangan buyruq tahlilchisi va javob bera olmasa, buni aytadi. Arxitektura kelajakda o'z modellarimiz uchun tayyor.",
       "Нет. Все расчёты, раскладки и 3D-модели создаются нашими собственными алгоритмами на Python. Помощник — это разбор команд на правилах, и он говорит об этом, когда не может ответить. Архитектура готова к нашим будущим моделям.")),
    (L("Can I send the output straight to the machine?", "Natijani to'g'ridan-to'g'ri stanokka yuborsam bo'ladimi?", "Можно ли отправлять результат сразу на станок?"),
     L("No. Every result is marked for professional review. Check dimensions, grain, hardware and machine limits before cutting. We list the assumptions behind each calculation.",
       "Yo'q. Har bir natija mutaxassis tekshiruvi uchun belgilangan. Kesishdan oldin o'lchamlar, tola yo'nalishi, furnitura va stanok cheklovlarini tekshiring. Har bir hisob taxminlarini ko'rsatamiz.",
       "Нет. Каждый результат помечен для проверки специалистом. Перед резкой проверьте размеры, направление волокон, фурнитуру и ограничения станка. Мы указываем допущения каждого расчёта.")),
    (L("Can it read my hand sketch or drawing?", "U qo'lda chizilgan eskiz yoki chizmani o'qiy oladimi?", "Может ли он прочитать мой эскиз или чертёж?"),
     L("Not yet. You can upload drawings, sketches and room photos and keep them with your project, but dimensions must be entered manually.",
       "Hozircha yo'q. Chizma, eskiz va xona rasmlarini yuklab loyihangizda saqlash mumkin, lekin o'lchamlarni qo'lda kiritish kerak.",
       "Пока нет. Вы можете загружать чертежи, эскизы и фото комнат и хранить их в проекте, но размеры нужно вводить вручную.")),
    (L("Which 3D formats can I export?", "Qaysi 3D formatlarga eksport qilish mumkin?", "В какие 3D-форматы можно экспортировать?"),
     L("GLB, glTF and OBJ. Cutting lists export to PDF and Excel.", "GLB, glTF va OBJ. Kesish ro'yxatlari PDF va Excel ga eksport qilinadi.", "GLB, glTF и OBJ. Карты раскроя экспортируются в PDF и Excel.")),
    (L("Is my data private?", "Ma'lumotlarim maxfiymi?", "Мои данные приватны?"),
     L("Projects, images and files are only accessible to your account. Files are served through short-lived signed links.",
       "Loyihalar, rasmlar va fayllarga faqat sizning hisobingiz kira oladi. Fayllar qisqa muddatli imzolangan havolalar orqali beriladi.",
       "Проекты, изображения и файлы доступны только вашему аккаунту. Файлы отдаются по короткоживущим подписанным ссылкам.")),
]


def build_meta() -> dict:
    furniture = [{"slug": c["slug"], "label": CAT_LABELS.get(c["slug"], L(c["name"], c["name"], c["name"]))} for c in FURNITURE_CATEGORIES]
    return {
        "limits": {k: list(v) for k, v in engine.LIMITS.items()},
        "defaults": {"thickness": 18, "shelves": 3, "doors": 2, "drawers": 0, "width": 800, "height": 2000, "depth": 400},
        "project_categories": [{"value": v, "label": CAT_LABELS[v]} for v, _ in Project.Category.choices],
        "furniture_categories": furniture,
        "boards": [{"value": v, "label": BOARD_LABELS[v]} for v in (Material.Kind.MDF, Material.Kind.LDSP, Material.Kind.PLYWOOD)],
        "rooms": ROOMS, "styles": STYLES, "showcase": SHOWCASE,
        "export_formats": EXPORT_FORMATS,
        "stats": [
            {"key": "categories", "value": len(FURNITURE_CATEGORIES), "label": L("Furniture categories", "Mebel toifalari", "Категории мебели"), "hint": L(", ".join(c["name"].lower() for c in FURNITURE_CATEGORIES), ", ".join(f["label"]["uz"].lower() for f in furniture), ", ".join(f["label"]["ru"].lower() for f in furniture))},
            {"key": "formats", "value": len(EXPORT_FORMATS), "label": L("Export formats", "Eksport formatlari", "Форматы экспорта"), "hint": L(", ".join(EXPORT_FORMATS), ", ".join(EXPORT_FORMATS), ", ".join(EXPORT_FORMATS))},
            {"key": "tools", "value": len(TOOLS), "label": L("Core tools", "Asosiy vositalar", "Основные инструменты"), "hint": L("calculator, cutting list, optimizer, 3D, editor, interior", "kalkulyator, kesish ro'yxati, optimizator, 3D, muharrir, interyer", "калькулятор, раскрой, оптимизатор, 3D, редактор, интерьер")},
            {"key": "languages", "value": len(LANGUAGES), "label": L("Interface languages", "Interfeys tillari", "Языки интерфейса"), "hint": L("English, Uzbek, Russian", "Ingliz, o'zbek, rus", "английский, узбекский, русский")},
        ],
        "content": {
            "features": [{"icon": i, "title": t, "text": x} for i, t, x in FEATURES],
            "steps": [{"icon": i, "title": t, "text": x} for i, t, x in STEPS],
            "faq": [{"q": q, "a": a} for q, a in FAQ],
        },
    }


class MetaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes: list = []  # cheap/static or signature-protected: the anonymous per-IP limit would break shared networks

    def get(self, request):
        return Response(build_meta())
