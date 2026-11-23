"""User-facing texts. Uzbek (Latin) is the default; Russian and English are supported.
Language is taken from the Telegram client setting, falling back to Uzbek."""
from html import escape

DEFAULT_LANG = "uz"
SUPPORTED = ("uz", "ru", "en")

TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "welcome_linked": "<b>MEBELCHI AI</b> botiga xush kelibsiz, {name}.",
        "welcome_unlinked": "<b>MEBELCHI AI</b> botiga xush kelibsiz.\n\nAvval hisobingizni bog'lang: veb-ilovada "
                            "<b>Telegram ulash</b> kodini oling va shu yerga yuboring.",
        "link_ask_code": "Veb-ilovadagi 8 belgili kodni yuboring (masalan, ABCD-EFGH).",
        "link_ok": "Hisob muvaffaqiyatli bog'landi: <b>{email}</b>.",
        "err_invalid_code": "Kod noto'g'ri yoki allaqachon ishlatilgan. Veb-ilovada yangi kod oling.",
        "err_expired": "Kod muddati tugagan (10 daqiqa). Veb-ilovada yangi kod oling.",
        "err_too_many_attempts": "Juda ko'p noto'g'ri urinish. Bir necha daqiqadan so'ng qayta urinib ko'ring.",
        "err_telegram_in_use": "Bu Telegram hisobi boshqa MEBELCHI hisobiga bog'langan.",
        "menu_title": "Asosiy menyu",
        "btn_profile": "Profilim", "btn_projects": "Loyihalarim", "btn_create": "Mebel yaratish",
        "btn_calc": "Material kalkulyatori", "btn_cutting": "Kesish ro'yxati", "btn_designs": "Dizaynlarim",
        "btn_notifications": "Bildirishnomalar", "btn_help": "Yordam", "btn_web": "Veb-ilovani ochish",
        "btn_link": "Hisobni bog'lash", "btn_unlink": "Bog'lanishni uzish", "btn_cancel": "Bekor qilish",
        "btn_back": "Orqaga", "btn_new_project": "Yangi loyiha", "btn_rename": "Nomini o'zgartirish",
        "btn_pdf": "PDF yuklab olish", "btn_xlsx": "Excel yuklab olish", "btn_upload": "Fayl yuklash",
        "not_linked": "Bu amal uchun hisobni bog'lash kerak. /start buyrug'ini bosing.",
        "profile_text": "<b>Profil</b>\nEmail: {email}\nIsm: {name}\nRol: {role}",
        "unlinked_done": "Telegram bog'lanishi uzildi.",
        "projects_title": "<b>Loyihalaringiz</b>", "projects_empty": "Hozircha loyiha yo'q.",
        "ask_project_name": "Yangi loyiha nomini yuboring (2–160 belgi).",
        "project_created": "Loyiha yaratildi: <b>{name}</b>",
        "ask_new_name": "Loyihaning yangi nomini yuboring.",
        "project_renamed": "Nomi o'zgartirildi: <b>{name}</b>",
        "ask_width": "Kengligi (mm), 200–4000:",
        "ask_height": "Balandligi (mm), 200–3000:",
        "ask_depth": "Chuqurligi (mm), 150–1000:",
        "ask_thickness": "Plita qalinligi (mm), 8–40, masalan 16 yoki 18:",
        "ask_shelves": "Tokchalar soni, 0–20:",
        "ask_doors": "Eshiklar soni, 0–6:",
        "invalid_number": "Noto'g'ri qiymat. Raqam kiriting va chegaradan chiqmang.",
        "calc_result": "<b>Hisoblash natijasi</b>\nDetallar soni: {panels}\nTurli detallar: {distinct}\n"
                       "Umumiy yuza: {area} m²\nChekka bant: {edge} m\n\n<i>{disclaimer}</i>",
        "calc_disclaimer": "Professional tekshiruvdan o'tkazing. Ishlab chiqarish uchun tasdiqlanmagan.",
        "cutting_done": "<b>Kesish ro'yxati tayyor</b>\nDetallar: {parts}\nPlitalar: {sheets}\n"
                        "Foydalanish: {util}%\n{cost}\n\n<i>{disclaimer}</i>",
        "cutting_cost": "Taxminiy narx: {cost}",
        "cutting_nocost": "Narx: plita narxi sozlanmagan",
        "export_failed": "Faylni yuklab bo'lmadi. Qayta urinib ko'ring.",
        "choose_project": "Loyihani tanlang yoki loyihasiz davom eting:",
        "no_project": "Loyihasiz",
        "upload_ask": "Chizma yoki rasm yuboring (PDF, JPG, PNG, WEBP, DWG, DXF; 20 MB gacha).",
        "upload_ok": "Fayl saqlandi: <b>{name}</b>. Bo'sh joy: {percent}%",
        "upload_rejected_unsupported_type": "Bu fayl turi qo'llab-quvvatlanmaydi.",
        "upload_rejected_too_large": "Fayl juda katta.",
        "upload_rejected_empty": "Fayl bo'sh.",
        "upload_rejected_content_mismatch": "Fayl mazmuni turiga mos kelmaydi.",
        "upload_rejected_no_name": "Fayl nomi aniqlanmadi.",
        "notifications_title": "<b>Yangi bildirishnomalar</b>", "notifications_empty": "Yangi bildirishnoma yo'q.",
        "help_text": "<b>Yordam</b>\n/start — menyu\n/link — hisobni bog'lash\n/unlink — bog'lanishni uzish\n"
                     "/cancel — joriy amalni bekor qilish\n\nSavollar uchun veb-ilovadagi Yordam bo'limiga qarang.",
        "cancelled": "Bekor qilindi.",
        "admin_menu": "<b>Administrator paneli</b>",
        "admin_stats": "<b>Statistika</b>\nFoydalanuvchilar: {users}\nFaol (30 kun): {active}\n"
                       "Telegram bog'langan: {linked}\nLoyihalar: {projects}",
        "admin_system": "<b>Tizim holati</b>\nBackend: {backend}\nMa'lumotlar bazasi: {db}\n"
                        "Redis: {redis}\nCelery: {celery}",
        "admin_broadcast_ask": "Xabar matnini yuboring (2000 belgigacha). Bekor qilish uchun /cancel.",
        "admin_broadcast_queued": "Xabar navbatga qo'yildi.",
        "forbidden": "Bu buyruq faqat administratorlar uchun.",
        "rate_limited": "Juda tez yuboryapsiz. Bir oz kuting.",
        "backend_unavailable": "Server bilan aloqa yo'q. Keyinroq urinib ko'ring.",
        "generic_error": "Xatolik yuz berdi. Qayta urinib ko'ring.",
        "unknown": "Tushunmadim. /start buyrug'ini bosing.",
    },
    "ru": {
        "welcome_linked": "Добро пожаловать в бот <b>MEBELCHI AI</b>, {name}.",
        "welcome_unlinked": "Добро пожаловать в бот <b>MEBELCHI AI</b>.\n\nСначала свяжите аккаунт: получите код "
                            "<b>привязки Telegram</b> в веб-приложении и отправьте его сюда.",
        "link_ask_code": "Отправьте 8-значный код из веб-приложения (например, ABCD-EFGH).",
        "link_ok": "Аккаунт привязан: <b>{email}</b>.",
        "err_invalid_code": "Код неверный или уже использован. Получите новый в веб-приложении.",
        "err_expired": "Срок действия кода истёк (10 минут). Получите новый в веб-приложении.",
        "err_too_many_attempts": "Слишком много неверных попыток. Повторите позже.",
        "err_telegram_in_use": "Этот Telegram уже привязан к другому аккаунту MEBELCHI.",
        "menu_title": "Главное меню",
        "btn_profile": "Профиль", "btn_projects": "Мои проекты", "btn_create": "Создать мебель",
        "btn_calc": "Калькулятор материалов", "btn_cutting": "Карта раскроя", "btn_designs": "Мои дизайны",
        "btn_notifications": "Уведомления", "btn_help": "Помощь", "btn_web": "Открыть веб-приложение",
        "btn_link": "Привязать аккаунт", "btn_unlink": "Отвязать", "btn_cancel": "Отмена",
        "btn_back": "Назад", "btn_new_project": "Новый проект", "btn_rename": "Переименовать",
        "btn_pdf": "Скачать PDF", "btn_xlsx": "Скачать Excel", "btn_upload": "Загрузить файл",
        "not_linked": "Для этого нужно привязать аккаунт. Нажмите /start.",
        "profile_text": "<b>Профиль</b>\nEmail: {email}\nИмя: {name}\nРоль: {role}",
        "unlinked_done": "Привязка Telegram отменена.",
        "projects_title": "<b>Ваши проекты</b>", "projects_empty": "Проектов пока нет.",
        "ask_project_name": "Отправьте название нового проекта (2–160 символов).",
        "project_created": "Проект создан: <b>{name}</b>",
        "ask_new_name": "Отправьте новое название проекта.",
        "project_renamed": "Название изменено: <b>{name}</b>",
        "ask_width": "Ширина (мм), 200–4000:",
        "ask_height": "Высота (мм), 200–3000:",
        "ask_depth": "Глубина (мм), 150–1000:",
        "ask_thickness": "Толщина плиты (мм), 8–40, например 16 или 18:",
        "ask_shelves": "Количество полок, 0–20:",
        "ask_doors": "Количество дверей, 0–6:",
        "invalid_number": "Некорректное значение. Введите число в допустимых пределах.",
        "calc_result": "<b>Результат расчёта</b>\nДеталей: {panels}\nРазных деталей: {distinct}\n"
                       "Общая площадь: {area} м²\nКромка: {edge} м\n\n<i>{disclaimer}</i>",
        "calc_disclaimer": "Требуется проверка специалистом. Не проверено для производства.",
        "cutting_done": "<b>Карта раскроя готова</b>\nДеталей: {parts}\nЛистов: {sheets}\n"
                        "Использование: {util}%\n{cost}\n\n<i>{disclaimer}</i>",
        "cutting_cost": "Ориентировочная стоимость: {cost}",
        "cutting_nocost": "Стоимость: цена листа не задана",
        "export_failed": "Не удалось скачать файл. Попробуйте ещё раз.",
        "choose_project": "Выберите проект или продолжите без проекта:",
        "no_project": "Без проекта",
        "upload_ask": "Отправьте чертёж или изображение (PDF, JPG, PNG, WEBP, DWG, DXF; до 20 МБ).",
        "upload_ok": "Файл сохранён: <b>{name}</b>. Занято места: {percent}%",
        "upload_rejected_unsupported_type": "Этот тип файла не поддерживается.",
        "upload_rejected_too_large": "Файл слишком большой.",
        "upload_rejected_empty": "Файл пустой.",
        "upload_rejected_content_mismatch": "Содержимое файла не соответствует его типу.",
        "upload_rejected_no_name": "Не удалось определить имя файла.",
        "notifications_title": "<b>Новые уведомления</b>", "notifications_empty": "Новых уведомлений нет.",
        "help_text": "<b>Помощь</b>\n/start — меню\n/link — привязать аккаунт\n/unlink — отвязать\n"
                     "/cancel — отменить текущее действие\n\nВопросы — в разделе Помощь веб-приложения.",
        "cancelled": "Отменено.",
        "admin_menu": "<b>Панель администратора</b>",
        "admin_stats": "<b>Статистика</b>\nПользователи: {users}\nАктивные (30 дн.): {active}\n"
                       "Привязано Telegram: {linked}\nПроекты: {projects}",
        "admin_system": "<b>Состояние системы</b>\nBackend: {backend}\nБаза данных: {db}\n"
                        "Redis: {redis}\nCelery: {celery}",
        "admin_broadcast_ask": "Отправьте текст рассылки (до 2000 символов). Отмена: /cancel.",
        "admin_broadcast_queued": "Рассылка поставлена в очередь.",
        "forbidden": "Эта команда только для администраторов.",
        "rate_limited": "Слишком часто. Подождите немного.",
        "backend_unavailable": "Нет связи с сервером. Попробуйте позже.",
        "generic_error": "Произошла ошибка. Попробуйте ещё раз.",
        "unknown": "Не понял команду. Нажмите /start.",
    },
    "en": {
        "welcome_linked": "Welcome to the <b>MEBELCHI AI</b> bot, {name}.",
        "welcome_unlinked": "Welcome to the <b>MEBELCHI AI</b> bot.\n\nFirst link your account: get a <b>Telegram link</b> "
                            "code in the web app and send it here.",
        "link_ask_code": "Send the 8-character code from the web app (for example ABCD-EFGH).",
        "link_ok": "Account linked: <b>{email}</b>.",
        "err_invalid_code": "The code is wrong or already used. Get a new one in the web app.",
        "err_expired": "The code has expired (10 minutes). Get a new one in the web app.",
        "err_too_many_attempts": "Too many wrong attempts. Try again in a few minutes.",
        "err_telegram_in_use": "This Telegram account is linked to another MEBELCHI account.",
        "menu_title": "Main menu",
        "btn_profile": "My profile", "btn_projects": "My projects", "btn_create": "Create furniture",
        "btn_calc": "Material calculator", "btn_cutting": "Cutting list", "btn_designs": "My designs",
        "btn_notifications": "Notifications", "btn_help": "Help", "btn_web": "Open web app",
        "btn_link": "Link account", "btn_unlink": "Unlink", "btn_cancel": "Cancel",
        "btn_back": "Back", "btn_new_project": "New project", "btn_rename": "Rename",
        "btn_pdf": "Download PDF", "btn_xlsx": "Download Excel", "btn_upload": "Upload file",
        "not_linked": "This action needs a linked account. Press /start.",
        "profile_text": "<b>Profile</b>\nEmail: {email}\nName: {name}\nRole: {role}",
        "unlinked_done": "Telegram link removed.",
        "projects_title": "<b>Your projects</b>", "projects_empty": "No projects yet.",
        "ask_project_name": "Send the new project name (2–160 characters).",
        "project_created": "Project created: <b>{name}</b>",
        "ask_new_name": "Send the new project name.",
        "project_renamed": "Renamed to <b>{name}</b>",
        "ask_width": "Width (mm), 200–4000:",
        "ask_height": "Height (mm), 200–3000:",
        "ask_depth": "Depth (mm), 150–1000:",
        "ask_thickness": "Panel thickness (mm), 8–40, for example 16 or 18:",
        "ask_shelves": "Number of shelves, 0–20:",
        "ask_doors": "Number of doors, 0–6:",
        "invalid_number": "Invalid value. Enter a number within the allowed range.",
        "calc_result": "<b>Calculation result</b>\nPanels: {panels}\nDistinct parts: {distinct}\n"
                       "Total area: {area} m²\nEdge banding: {edge} m\n\n<i>{disclaimer}</i>",
        "calc_disclaimer": "Needs professional review. Not verified for manufacture.",
        "cutting_done": "<b>Cutting list ready</b>\nParts: {parts}\nSheets: {sheets}\n"
                        "Utilization: {util}%\n{cost}\n\n<i>{disclaimer}</i>",
        "cutting_cost": "Estimated cost: {cost}",
        "cutting_nocost": "Cost: sheet price is not set",
        "export_failed": "Could not download the file. Try again.",
        "choose_project": "Choose a project or continue without one:",
        "no_project": "No project",
        "upload_ask": "Send a drawing or image (PDF, JPG, PNG, WEBP, DWG, DXF; up to 20 MB).",
        "upload_ok": "File saved: <b>{name}</b>. Storage used: {percent}%",
        "upload_rejected_unsupported_type": "This file type is not supported.",
        "upload_rejected_too_large": "The file is too large.",
        "upload_rejected_empty": "The file is empty.",
        "upload_rejected_content_mismatch": "The file content does not match its type.",
        "upload_rejected_no_name": "Could not read the file name.",
        "notifications_title": "<b>New notifications</b>", "notifications_empty": "No new notifications.",
        "help_text": "<b>Help</b>\n/start — menu\n/link — link account\n/unlink — remove link\n"
                     "/cancel — cancel the current step\n\nFor questions, see Help in the web app.",
        "cancelled": "Cancelled.",
        "admin_menu": "<b>Administrator panel</b>",
        "admin_stats": "<b>Statistics</b>\nUsers: {users}\nActive (30 days): {active}\n"
                       "Telegram linked: {linked}\nProjects: {projects}",
        "admin_system": "<b>System status</b>\nBackend: {backend}\nDatabase: {db}\nRedis: {redis}\nCelery: {celery}",
        "admin_broadcast_ask": "Send the broadcast text (up to 2000 characters). Cancel with /cancel.",
        "admin_broadcast_queued": "Broadcast queued.",
        "forbidden": "This command is for administrators only.",
        "rate_limited": "Too many requests. Please wait a moment.",
        "backend_unavailable": "Cannot reach the server. Try again later.",
        "generic_error": "Something went wrong. Try again.",
        "unknown": "I did not understand. Press /start.",
    },
}


from bot.utils.room_texts import ROOM_TEXTS  # noqa: E402 - appended after TEXTS on purpose

for _lang, _texts in ROOM_TEXTS.items():
    TEXTS[_lang].update(_texts)


def language_for(telegram_language_code: str | None) -> str:
    code = (telegram_language_code or "").split("-")[0].lower()
    return code if code in SUPPORTED else DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    table = TEXTS.get(lang, TEXTS[DEFAULT_LANG])
    template = table.get(key) or TEXTS[DEFAULT_LANG].get(key) or key
    # Values interpolated into HTML messages are escaped; the templates themselves are trusted.
    return template.format(**{k: escape(str(v)) if isinstance(v, str) else v for k, v in kwargs.items()})
