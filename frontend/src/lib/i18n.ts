import { useUI } from '../stores/ui'

type Dict = Record<string, string>
const en: Dict = {
  'nav.home': 'Home', 'nav.features': 'Features', 'nav.how': 'How It Works', 'nav.pricing': 'Pricing', 'nav.about': 'About',
  'nav.login': 'Log in', 'nav.start': 'Get Started',
  'side.new': 'New Project', 'side.search': 'Search', 'side.recent': 'Recent Projects', 'side.pinned': 'Pinned Projects', 'side.folders': 'Folders',
  'side.images': 'Generated Images', 'side.models': '3D Models', 'side.files': 'Saved Files', 'side.settings': 'Settings', 'side.profile': 'Profile',
  'side.dashboard': 'Dashboard', 'side.chat': 'Assistant', 'side.projects': 'Projects', 'side.admin': 'Administration', 'side.logout': 'Log out',
  'common.save': 'Save', 'common.cancel': 'Cancel', 'common.delete': 'Delete', 'common.rename': 'Rename', 'common.create': 'Create',
  'common.loading': 'Loading', 'common.search': 'Search', 'common.download': 'Download', 'common.upload': 'Upload',
  'auth.email': 'Email', 'auth.password': 'Password', 'auth.login': 'Log in', 'auth.register': 'Create account', 'auth.forgot': 'Forgot password?',
  'home.welcome': 'Welcome back', 'home.dream': 'Design Your Dream Space', 'home.quick': 'Quick actions', 'home.recent': 'Recent projects',
}
const uz: Dict = {
  'nav.home': 'Bosh sahifa', 'nav.features': 'Imkoniyatlar', 'nav.how': 'Qanday ishlaydi', 'nav.pricing': 'Narxlar', 'nav.about': 'Biz haqimizda',
  'nav.login': 'Kirish', 'nav.start': 'Boshlash',
  'side.new': 'Yangi loyiha', 'side.search': 'Qidirish', 'side.recent': 'So\'nggi loyihalar', 'side.pinned': 'Mahkamlangan loyihalar', 'side.folders': 'Papkalar',
  'side.images': 'Tasvirlar', 'side.models': '3D modellar', 'side.files': 'Saqlangan fayllar', 'side.settings': 'Sozlamalar', 'side.profile': 'Profil',
  'side.dashboard': 'Boshqaruv paneli', 'side.chat': 'Yordamchi', 'side.projects': 'Loyihalar', 'side.admin': 'Boshqaruv', 'side.logout': 'Chiqish',
  'common.save': 'Saqlash', 'common.cancel': 'Bekor qilish', 'common.delete': 'O\'chirish', 'common.rename': 'Nomini o\'zgartirish', 'common.create': 'Yaratish',
  'common.loading': 'Yuklanmoqda', 'common.search': 'Qidirish', 'common.download': 'Yuklab olish', 'common.upload': 'Yuklash',
  'auth.email': 'Elektron pochta', 'auth.password': 'Parol', 'auth.login': 'Kirish', 'auth.register': 'Hisob yaratish', 'auth.forgot': 'Parolni unutdingizmi?',
  'home.welcome': 'Xush kelibsiz', 'home.dream': 'Orzuingizdagi makonni loyihalang', 'home.quick': 'Tezkor amallar', 'home.recent': 'So\'nggi loyihalar',
}
const ru: Dict = {
  'nav.home': 'Главная', 'nav.features': 'Возможности', 'nav.how': 'Как это работает', 'nav.pricing': 'Тарифы', 'nav.about': 'О нас',
  'nav.login': 'Войти', 'nav.start': 'Начать',
  'side.new': 'Новый проект', 'side.search': 'Поиск', 'side.recent': 'Недавние проекты', 'side.pinned': 'Закреплённые проекты', 'side.folders': 'Папки',
  'side.images': 'Изображения', 'side.models': '3D-модели', 'side.files': 'Сохранённые файлы', 'side.settings': 'Настройки', 'side.profile': 'Профиль',
  'side.dashboard': 'Панель', 'side.chat': 'Ассистент', 'side.projects': 'Проекты', 'side.admin': 'Администрирование', 'side.logout': 'Выйти',
  'common.save': 'Сохранить', 'common.cancel': 'Отмена', 'common.delete': 'Удалить', 'common.rename': 'Переименовать', 'common.create': 'Создать',
  'common.loading': 'Загрузка', 'common.search': 'Поиск', 'common.download': 'Скачать', 'common.upload': 'Загрузить',
  'auth.email': 'Эл. почта', 'auth.password': 'Пароль', 'auth.login': 'Войти', 'auth.register': 'Создать аккаунт', 'auth.forgot': 'Забыли пароль?',
  'home.welcome': 'С возвращением', 'home.dream': 'Создайте пространство мечты', 'home.quick': 'Быстрые действия', 'home.recent': 'Недавние проекты',
}

Object.assign(en, {
  'hero.title': 'From Idea to Furniture.', 'hero.sub': 'Design smarter. Calculate faster. Build better. MEBELCHI AI brings furniture design and production workflows into one intelligent platform.',
  'hero.cta1': 'Get Started', 'hero.cta2': 'Explore Features', 'hero.badge': 'Built-in calculation engine. No external AI services.',
  'auth.welcome': 'Welcome back', 'auth.welcome.sub': 'Log in to continue to your workspace.', 'auth.new': 'New here?', 'auth.have': 'Already have an account?',
  'auth.google': 'Continue with Google', 'auth.or': 'or continue with email', 'auth.back': 'Back to website', 'auth.google.off': 'Google sign-in is not configured yet. Ask the administrator to set GOOGLE_CLIENT_ID.',
  'reg.title': 'Create your account', 'reg.sub': 'Start designing and calculating furniture in minutes.', 'reg.step1': 'About you', 'reg.step2': 'Secure account',
  'reg.next': 'Continue', 'reg.prev': 'Back', 'reg.first': 'First name', 'reg.last': 'Last name', 'reg.phone': 'Phone number (optional)', 'reg.confirm': 'Confirm password',
  'reg.hint': 'At least 8 characters, not too common.', 'reg.hi': 'Nice to meet you', 'reg.create': 'Create account',
  'pw.weak': 'Weak', 'pw.fair': 'Fair', 'pw.good': 'Good', 'pw.strong': 'Strong',
  'side.tag': 'From idea to furniture.', 'side.f1': 'Panel and material calculator', 'side.f2': 'Sheet optimization with cutting layouts', 'side.f3': 'Interactive 3D, GLB / OBJ export',
  'role.title': 'Choose Your Experience', 'role.sub': 'Pick the workspace that fits how you work. You can change this later in settings.',
  'role.maker': 'Furniture Maker', 'role.makerText': 'Professional furniture production workspace.', 'role.maker1': 'Panel and material calculator', 'role.maker2': 'Cutting lists with sheet optimization', 'role.makerCta': 'Continue as Furniture Maker',
  'role.home': 'Home Owner', 'role.homeText': 'Personal furniture and interior design workspace.', 'role.home1': 'Plan rooms, styles and layouts', 'role.home2': 'Upload room photos and organize ideas', 'role.homeCta': 'Continue as Home Owner',
})
Object.assign(uz, {
  'hero.title': 'G\'oyadan mebelgacha.', 'hero.sub': 'Aqlliroq loyihalang. Tezroq hisoblang. Yaxshiroq yasang. MEBELCHI AI mebel dizayni va ishlab chiqarish jarayonlarini bitta platformada birlashtiradi.',
  'hero.cta1': 'Boshlash', 'hero.cta2': 'Imkoniyatlar', 'hero.badge': 'Ichki hisoblash dvigateli. Tashqi AI xizmatlari yo\'q.',
  'auth.welcome': 'Xush kelibsiz', 'auth.welcome.sub': 'Ish maydoningizga kirish uchun tizimga kiring.', 'auth.new': 'Yangimisiz?', 'auth.have': 'Hisobingiz bormi?',
  'auth.google': 'Google orqali davom etish', 'auth.or': 'yoki pochta orqali', 'auth.back': 'Saytga qaytish', 'auth.google.off': 'Google orqali kirish hali sozlanmagan. Administrator GOOGLE_CLIENT_ID ni kiritishi kerak.',
  'reg.title': 'Hisob yarating', 'reg.sub': 'Mebel loyihalash va hisoblashni bir necha daqiqada boshlang.', 'reg.step1': 'Siz haqingizda', 'reg.step2': 'Xavfsizlik',
  'reg.next': 'Davom etish', 'reg.prev': 'Orqaga', 'reg.first': 'Ism', 'reg.last': 'Familiya', 'reg.phone': 'Telefon raqami (ixtiyoriy)', 'reg.confirm': 'Parolni tasdiqlang',
  'reg.hint': 'Kamida 8 belgi, oddiy parol bo\'lmasin.', 'reg.hi': 'Tanishganimizdan xursandmiz', 'reg.create': 'Hisob yaratish',
  'pw.weak': 'Kuchsiz', 'pw.fair': 'O\'rtacha', 'pw.good': 'Yaxshi', 'pw.strong': 'Kuchli',
  'side.tag': 'G\'oyadan mebelgacha.', 'side.f1': 'Panel va material kalkulyatori', 'side.f2': 'Kesish sxemalari bilan list optimizatsiyasi', 'side.f3': 'Interaktiv 3D, GLB / OBJ eksport',
  'role.title': 'Ish muhitini tanlang', 'role.sub': 'Ishingizga mos maydonni tanlang. Keyinroq sozlamalarda o\'zgartirishingiz mumkin.',
  'role.maker': 'Mebel ustasi', 'role.makerText': 'Mebel ishlab chiqarish uchun professional ish maydoni.', 'role.maker1': 'Panel va material kalkulyatori', 'role.maker2': 'List optimizatsiyali kesish ro\'yxatlari', 'role.makerCta': 'Mebel ustasi sifatida davom etish',
  'role.home': 'Uy egasi', 'role.homeText': 'Shaxsiy mebel va interyer dizayni maydoni.', 'role.home1': 'Xona, uslub va joylashuvni rejalashtiring', 'role.home2': 'Xona rasmlarini yuklang va g\'oyalarni saqlang', 'role.homeCta': 'Uy egasi sifatida davom etish',
})
Object.assign(ru, {
  'hero.title': 'От идеи до мебели.', 'hero.sub': 'Проектируйте умнее. Считайте быстрее. Стройте лучше. MEBELCHI AI объединяет дизайн мебели и подготовку производства на одной платформе.',
  'hero.cta1': 'Начать', 'hero.cta2': 'Возможности', 'hero.badge': 'Встроенный движок расчётов. Без внешних ИИ-сервисов.',
  'auth.welcome': 'С возвращением', 'auth.welcome.sub': 'Войдите, чтобы продолжить работу.', 'auth.new': 'Впервые здесь?', 'auth.have': 'Уже есть аккаунт?',
  'auth.google': 'Продолжить с Google', 'auth.or': 'или по электронной почте', 'auth.back': 'Назад на сайт', 'auth.google.off': 'Вход через Google ещё не настроен. Администратору нужно задать GOOGLE_CLIENT_ID.',
  'reg.title': 'Создайте аккаунт', 'reg.sub': 'Начните проектировать и считать мебель за несколько минут.', 'reg.step1': 'О вас', 'reg.step2': 'Безопасность',
  'reg.next': 'Продолжить', 'reg.prev': 'Назад', 'reg.first': 'Имя', 'reg.last': 'Фамилия', 'reg.phone': 'Телефон (необязательно)', 'reg.confirm': 'Повторите пароль',
  'reg.hint': 'Не менее 8 символов, не слишком простой.', 'reg.hi': 'Приятно познакомиться', 'reg.create': 'Создать аккаунт',
  'pw.weak': 'Слабый', 'pw.fair': 'Средний', 'pw.good': 'Хороший', 'pw.strong': 'Надёжный',
  'side.tag': 'От идеи до мебели.', 'side.f1': 'Калькулятор панелей и материалов', 'side.f2': 'Оптимизация листов со схемами раскроя', 'side.f3': 'Интерактивное 3D, экспорт GLB / OBJ',
  'role.title': 'Выберите режим работы', 'role.sub': 'Выберите рабочее пространство под ваши задачи. Позже это можно изменить в настройках.',
  'role.maker': 'Мебельщик', 'role.makerText': 'Профессиональное пространство для производства мебели.', 'role.maker1': 'Калькулятор панелей и материалов', 'role.maker2': 'Карты раскроя с оптимизацией листов', 'role.makerCta': 'Продолжить как мебельщик',
  'role.home': 'Владелец дома', 'role.homeText': 'Личное пространство для мебели и дизайна интерьера.', 'role.home1': 'Планируйте комнаты, стили и расстановку', 'role.home2': 'Загружайте фото комнат и собирайте идеи', 'role.homeCta': 'Продолжить как владелец дома',
})

Object.assign(en, { 'chat.notfound': 'This conversation was not found.', 'chat.title': 'How can I help with your furniture?', 'chat.sub': 'I am a built-in, rule-based assistant, not a language model. I turn dimensions into panel lists, areas and sheet counts. Anything else, I will tell you honestly.',
  'chat.placeholder': 'Ask MEBELCHI AI anything about furniture...', 'chat.new': 'New chat', 'chat.history': 'History', 'chat.foot': 'Rule-based assistant. Output is for professional review and is not verified for manufacture.',
  'chat.s1': 'cabinet 800x2000x400 with 3 shelves and 2 doors', 'chat.s2': 'cutting list for wardrobe 1000x2200x580, 4 shelves, 2 doors', 'chat.s3': 'chest 900x1000x480 with 4 drawers', 'chat.s4': 'hello',
  'side.workshop': 'Workshop', 'side.design': 'Design', 'side.library': 'Library', 'side.calc': 'Material calculator', 'side.cuts': 'Cutting lists', 'side.editor': 'Furniture editor', 'side.interior': 'Interior designer' })
Object.assign(uz, { 'chat.notfound': 'Bu suhbat topilmadi.', 'chat.title': 'Mebel bo\'yicha qanday yordam bera olaman?', 'chat.sub': 'Men ichki, qoidalarga asoslangan yordamchiman, til modeli emasman. O\'lchamlarni panel ro\'yxati, maydon va list soniga aylantiraman. Qolgan narsalarda ochiq aytaman.',
  'chat.placeholder': 'MEBELCHI AI dan mebel haqida so\'rang...', 'chat.new': 'Yangi suhbat', 'chat.history': 'Tarix', 'chat.foot': 'Qoidalarga asoslangan yordamchi. Natija mutaxassis tekshiruvi uchun, ishlab chiqarishga tasdiqlanmagan.',
  'chat.s1': 'shkaf 800x2000x400, 3 ta tokcha va 2 ta eshik', 'chat.s2': 'kesish ro\'yxati javon 1000x2200x580, 4 ta tokcha, 2 ta eshik', 'chat.s3': 'komod 900x1000x480, 4 ta yashik', 'chat.s4': 'salom',
  'side.workshop': 'Ustaxona', 'side.design': 'Dizayn', 'side.library': 'Kutubxona', 'side.calc': 'Material kalkulyatori', 'side.cuts': 'Kesish ro\'yxatlari', 'side.editor': 'Mebel muharriri', 'side.interior': 'Interyer dizayneri' })
Object.assign(ru, { 'chat.notfound': 'Эта беседа не найдена.', 'chat.title': 'Чем помочь с вашей мебелью?', 'chat.sub': 'Я встроенный помощник на правилах, а не языковая модель. Превращаю размеры в списки панелей, площади и число листов. В остальном скажу честно.',
  'chat.placeholder': 'Спросите MEBELCHI AI о мебели...', 'chat.new': 'Новый чат', 'chat.history': 'История', 'chat.foot': 'Помощник на правилах. Результат для проверки специалистом, не подтверждён для производства.',
  'chat.s1': 'шкаф 800x2000x400, 3 полки и 2 двери', 'chat.s2': 'раскрой шкаф 1000x2200x580, 4 полки, 2 двери', 'chat.s3': 'комод 900x1000x480, 4 ящика', 'chat.s4': 'привет',
  'side.workshop': 'Мастерская', 'side.design': 'Дизайн', 'side.library': 'Библиотека', 'side.calc': 'Калькулятор материалов', 'side.cuts': 'Карты раскроя', 'side.editor': 'Редактор мебели', 'side.interior': 'Дизайнер интерьера' })

Object.assign(en, { 'sec.features': 'Everything between sketch and saw', 'sec.featuresSub': 'Six tools that share one project, one set of dimensions and one source of truth.', 'sec.how': 'How it works',
  'sec.showcase': 'Generated from parameters', 'sec.showcaseSub': "These are live models built by the platform's geometry engine, not stock renders. Drag to explore.", 'sec.pricing': 'Pricing',
  'sec.pricingSub': 'Start free. Paid plans are activated by an administrator while online payments are being integrated.', 'sec.faq': 'Frequently asked questions', 'sec.about': 'About MEBELCHI AI',
  'sec.aboutText': 'MEBELCHI AI is a furniture design, calculation and production platform built from scratch for workshops and home owners. We favor transparent, checkable engineering over black boxes: every number comes with its assumptions.',
  'cta.account': 'Create your free account', 'cta.open': 'Open workspace', 'stats.note': 'Platform capabilities, not customer statistics.' })
Object.assign(uz, { 'sec.features': 'Eskizdan arragacha hammasi', 'sec.featuresSub': 'Bitta loyiha, bitta o\'lchamlar to\'plami va bitta haqiqat manbasini bo\'lishadigan oltita vosita.', 'sec.how': 'Qanday ishlaydi',
  'sec.showcase': 'Parametrlardan yaratilgan', 'sec.showcaseSub': 'Bu platformaning geometriya dvigateli qurgan jonli modellar, stok rasmlar emas. Aylantirib ko\'ring.', 'sec.pricing': 'Narxlar',
  'sec.pricingSub': 'Bepul boshlang. Onlayn to\'lov ulanguncha pullik rejalarni administrator faollashtiradi.', 'sec.faq': 'Ko\'p beriladigan savollar', 'sec.about': 'MEBELCHI AI haqida',
  'sec.aboutText': 'MEBELCHI AI ustaxonalar va uy egalari uchun noldan qurilgan mebel dizayni, hisob-kitobi va ishlab chiqarish platformasi. Biz qora qutilar o\'rniga shaffof, tekshirsa bo\'ladigan muhandislikni afzal ko\'ramiz: har bir raqam o\'z taxminlari bilan keladi.',
  'cta.account': 'Bepul hisob yarating', 'cta.open': 'Ish maydonini ochish', 'stats.note': 'Platforma imkoniyatlari, mijozlar statistikasi emas.' })
Object.assign(ru, { 'sec.features': 'Всё между эскизом и пилой', 'sec.featuresSub': 'Шесть инструментов с одним проектом, одним набором размеров и одним источником правды.', 'sec.how': 'Как это работает',
  'sec.showcase': 'Создано из параметров', 'sec.showcaseSub': 'Это живые модели, построенные геометрическим движком платформы, а не стоковые рендеры. Потяните, чтобы повернуть.', 'sec.pricing': 'Тарифы',
  'sec.pricingSub': 'Начните бесплатно. Платные тарифы активирует администратор, пока подключаются онлайн-платежи.', 'sec.faq': 'Частые вопросы', 'sec.about': 'О MEBELCHI AI',
  'sec.aboutText': 'MEBELCHI AI — платформа для проектирования, расчёта и подготовки производства мебели, созданная с нуля для мастерских и владельцев домов. Мы выбираем прозрачную, проверяемую инженерию вместо чёрных ящиков: каждое число идёт с допущениями.',
  'cta.account': 'Создать бесплатный аккаунт', 'cta.open': 'Открыть рабочее пространство', 'stats.note': 'Возможности платформы, а не статистика клиентов.' })

export const dictionaries = { en, uz, ru }

export function translate(lang: keyof typeof dictionaries, key: string): string {
  return dictionaries[lang][key] ?? en[key] ?? key
}
/** Picks the current-language string from a backend {en, uz, ru} object. */
export function useL() {
  const lang = useUI((s) => s.language)
  return (o?: Partial<Record<'en' | 'uz' | 'ru', string>>) => o?.[lang] ?? o?.en ?? ''
}
export function useT() {
  const lang = useUI((s) => s.language)
  return (key: string) => translate(lang, key)
}
