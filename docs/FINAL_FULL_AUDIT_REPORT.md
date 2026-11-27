# Mebelchi AI — To'liq audit va barqarorlash hisoboti

Yozilgan sana: 2026-11-27. Yozilgan til: o'zbekcha. Auditorlar uchun.

## Xulosa (holat)

**READY WITH LIMITATIONS.** Backend (SQLite va PostgreSQL 16), frontend (unit, build, TypeScript), Telegram bot va Flutter mobile (analyze, unit, jonli backend e2e, imzolangan APK) testlari yashil. Cheklovlar: brauzer E2E va emulyator/qurilma testi bu sessiyada bajarilmadi; Render'dagi jonli saytga 1.0.6 APK hali ro'yxatga olinmagan.

Bu sessiyada kodda yangi xato topilmadi va kod o'zgartirilmadi. Oldingi ishdan qolgan o'zgarishlar `0bab803` commit'ida (1.0.6) branch'ga push qilingan, APK GitHub release `v1.0.6` ga yuklangan.

## 1. Loyiha va Git

- Branch: `integrate/remote-main`. HEAD: `0bab803` (1.0.6). Ish daraxti toza.
- Oxirgi commitlar: `0bab803` fix(mobile,bot,rooms) 1.0.6; `b9c2268`; `594f428`; `39f05fc`; `1fda7c5`.
- Remote branchlar: `origin/main`, `origin/integrate/remote-main`, `origin/feat/telegram-bot`, `origin/feat/room-chat-flow`, `origin/feat/foundation-roles-audit`, `origin/feat/db-fallback-and-system-status`, `origin/docs/*`.
- CI: `.github/workflows/ci.yml` mavjud. Lokal ravishda uning backend, frontend va mobile joblari takrorlandi. Actions'ning o'zi bu hisobotda tekshirilmagan.
- Inventarizatsiya: backend `apps/` ichida 25 ta app; `docs/` da 9 ta hujjat; `deploy/` (backup, restore, deploy skriptlari). `node_modules`, `.venv`, `build`, `dist`, `__pycache__` source sifatida tahlil qilinmagan.

## 2. Backend

### 2.1 Endpointlar
- Jami URL pattern: 252. API (`api/v1/`): **169**.
- Ochiq (`AllowAny` yoki permission yo'q) endpointlar: 21. Ularning ko'pchiligi kutilgan: meta, register/login/refresh/google/config, password reset, subscriptions plans, Android release yuklab olish, schema/docs.
- Tekshirilgan ochiq endpointlar:
  - `payments/webhook/<provider>/` — permission yo'q, lekin `apps/finance/providers/payme.py` da `Authorization` Basic tekshiruvi `hmac.compare_digest` bilan bajariladi. Xavf topilmadi.
  - `files/<pk>/download/`, `gallery/<pk>/file/`, `users/<pk>/avatar/`, `workshops/<pk>/logo-file/` — `apps/core/signing.verify_file` imzo bilan himoyalangan (signed link).
  - `geometry/preview/` — `ExportRateThrottle` bilan cheklangan.
- Dev-only: `schema/` va `docs/` (Swagger) `DEBUG` bo'lmaganda ham mavjud. Production'da ochiq qolishi mumkin; ko'rib chiqish tavsiya etiladi (P3).

### 2.2 Testlar
| Test | Natija |
|---|---|
| SQLite, `--parallel 2` | 898 Ran, **OK**, skipped 13 (15 s) |
| PostgreSQL 16 (vaqtinchalik klaster, port 55999) | 898 Ran, **OK** (20 s) |
| `manage.py check` | No issues |
| `makemigrations --check` | No changes detected (migration drift yo'q) |

PostgreSQL uchun 55432 (boshqa loyiha) ga tegilmagan. Klaster sessiya oxirida to'xtatildi.

### 2.3 Kod belgilari
- TODO/FIXME/NOT IMPLEMENTED: backend, bot, frontend, mobile source'da 0 ta.
- `except Exception: return None` — `backend/apps/accounts/services.py:43` (Google id_token tekshiruvi). Fail-closed, ya'ni login rad etiladi. Log yozilmaydi (P3).

### 2.4 Topilgan va tuzatilgan (bu sessiyada)
Oldingi sessiyada tuzatilgan va `0bab803` da commit qilingan: GLB cutaway (`apps/rooms/services.py`, `views.py`) va regressiya testlari.

## 3. Frontend (web)

- Route'lar (`frontend/src/App.tsx` va boshqa joylar): `/`, `/login`, `/register`, `/forgot-password`, `/reset-password`, `/choose-role`, `/privacy`, `/terms`, `/android`, `/admin`, `/app`, `/app/designs`, `/app/interior`, `/app/rooms/new`, `/app/rooms/import/:designId`, `projects`, `projects/:id`, `calculator`, `cutting-lists`, `cutting-lists/:id`, `designs`, `editor`, `files`, `gallery`, `interior`, `rooms`, `rooms/:id`, `rooms/new`, `rooms/import/:designId`, `settings`, `workshops`, `workshops/:id`, `assistant`, `assistant/:id`.
- Tugma inventarizatsiyasi (grep): `onClick`/`Link`/`button` ga oid ~226 qator. Bo'sh handler (`onClick={() => {}}`), `href="#"`, `as any`, `@ts-ignore` topilmadi.
- Testlar:

| Test | Natija |
|---|---|
| Vitest (unit/component) | **225 passed**, 23 fayl (10.8 s) |
| TypeScript (`tsc -b`) | Xatosiz |
| ESLint | 0 xato, ogohlantirishlar bor (react-refresh, set-state-in-effect, purity) — P3 |
| Production build (`vite build`) | **OK** (951 ms). Chunk > 900 kB ogohlantirishi — P3 (code splitting) |
| Browser E2E (Playwright) | **BLOCKED** bu sessiyada: alohida E2E run qilinmadi (oldingi sessiyada 16 qadamli e2e o'tgan edi) |

## 4. Telegram bot

- Stek: aiogram 3, Django API'ga HTTP orqali ulanadi, DB yo'q.
- Testlar (alohida venv, `requirements.txt`): **52 passed** (0.08 s). Telegram API mock qilingan.
- Callback va keyboard: `order_actions_keyboard` faqat serverdan kelgan `allowed_next_statuses` ni ko'rsatadi; tartib `sorted_order_statuses` bilan (oldingi tuzatish, `0bab803`).
- Bu sessiyada haqiqiy Telegram xabari yuborilmagan.

## 5. Flutter mobile

| Test | Natija |
|---|---|
| `flutter analyze` | **No issues found** |
| `flutter test -j 1` (birlik + widget) | **+70 passed**, e2e skip (MEBELCHI_E2E_URL berilmagan) |
| Jonli backend e2e (`backend_e2e`, `calculator_e2e`, `rooms_e2e`) | **+3 passed** (127.0.0.1:8765, SQLite) |
| Buyurtmalar e2e (`orders_e2e`) | **SKIPPED** — seeded sex akkaunti va buyurtma yo'q |
| Android release APK 1.0.6+7 | **OK**: imzolangan, v2 scheme true, 38 MB, SHA-256 `2cf4bb0c137d3834176f5003ee87f08763686be1e8befd5bef8c0fbf9f6ec941` |
| Emulyator/qurilma (integration_test) | **BLOCKED**: `adb` qurilma yo'q, `emulator` buyrug'i yo'q |

GitHub release `v1.0.6` yaratilgan; yuklab olish havolasi 200 (39 671 594 bayt).

## 6. Integratsiya (cross-platform)

- Backend ↔ mobile: ro'yxatdan o'tish, login, token rotation, xona dizayni, kalkulyator — jonli e2e orqali **PASS**.
- Backend ↔ web: `frontend/nginx.conf` va Render rewrite (`/api/*` → backend) mavjud. Jonli `https://mebelchi-web.onrender.com/` 200, `/django-admin/login/` 200, `/android` 200.
- Backend ↔ bot: bot testlari mock; haqiqiy end-to-end (bog'lash → buyurtma → qabul) BLOCKED (seeded akkaunt va bot token yo'q).
- Jonli backend `https://mebelchi-backend.onrender.com/api/v1/app/android/` bu sessiyada **000** (timeout) qaytardi, keyingi tekshiruvda 200 bo'lishi mumkin — jonli holat o'zgaruvchan (free plan, uyqu rejimi).
- Mobile `1.0.6` ni server ro'yxatiga qo'shish: **BLOCKED** — Render bazasi kalitlari berilmagan. Hozirgi jonli ro'yxat: `latest` = 1.0.5.

## 7. Security audit (lokal, statik + konfiguratsiya)

- Auth: JWT, `ROTATE_REFRESH_TOKENS`, `BLACKLIST_AFTER_ROTATION` yoqilgan. Throttle: anon 60/min, user 600/min, auth 10/min, sms 5/soat.
- Production sozlamalari (`DEBUG` false): `SECURE_SSL_REDIRECT`, HSTS, secure cookies, `SECRET_KEY` majburiy (yo'q bo'lsa xato beradi). Yaxshi.
- CORS: `CORS_ALLOW_CREDENTIALS=False`, origin ro'yxati env orqali.
- Webhook: Basic + `compare_digest`. Yaxshi.
- Signed file linklar: `verify_file`. Yaxshi.
- Maxfiy kalitlar: hisobotda qiymat yozilmagan. `.env` fayllari o'qilmagan.
- Dependency audit (pip-audit / npm audit): **BLOCKED** bu sessiyada — vositalar o'rnatilmagan, internetga so'rov yuborilmagan.
- Xatolik: `Render API kaliti` oldingi sessiyada chatga yozilgan. **Foydalanuvchi uni bekor qilishi kerak (revoke).**

## 8. Performance va RAM monitoring

Kuzatuv nuqtalari (`free -m`, sessiya davomida, 5 ta namuna):

| Vaqt | Used | Available | Izoh |
|---|---|---|---|
| Boshlanish | 10 043 MB (66%) | 5 162 MB (34%) | Minecraft Java ~3 GB, Firefox, VS Code, Flutter LSP |
| Backend SQLite test (parallel 2) | 10 369 MB (68%) | 4 836 MB (32%) | |
| Backend PostgreSQL test | 10 509 MB (69%) | 4 696 MB (31%) | **Eng yuqori ko'rsatkich** |
| Eng past available | — | **4 696 MB (31%)** | Chegara 20% dan yuqori |
| Swap | 0 MB | — | Swap ishlatilmagan |

- Eng yuqori RAM ishlatilishi (kuzatilgan): ~69%. 80% chegarasi oshmagan.
- Eng ko'p RAM ishlatgan jarayon: `java` (Minecraft, ~2.9 GB) — loyihaga aloqasi yo'q, to'xtatilmagan.
- CPU: `nproc` = 12. Testlar ketma-ket yoki `--parallel 2` bilan bajarilgan.
- Diqqat: bu **nuqtali namunalar**, uzluksiz monitoring emas. Docker stats tekshirilmagan (`smartschool-test-db` boshqa loyihaniki).
- Performance (N+1, bundle size, 3D render FPS): to'liq profil qilinmagan. Bundle size: chunk > 900 kB (P3). N+1 va query profiling — keyingi bosqich.

## 9. Topilgan xatolar

| ID | Daraja | Modul | Fayl | Muammo | Holat |
|---|---|---|---|---|---|
| A-01 | P3 | accounts | `backend/apps/accounts/services.py:43` | Google token tekshiruvidagi `except Exception` log yozmaydi | Ochiq |
| A-02 | P3 | core | `backend/config/urls.py` | `schema/` va `docs/` production'da ochiq bo'lishi mumkin | Ochiq (tekshirish kerak) |
| A-03 | P3 | frontend | `frontend/src/**` | ESLint ogohlantirishlari (react-refresh, set-state-in-effect) | Ochiq |
| A-04 | P3 | frontend | build | Bundle > 900 kB | Ochiq |
| A-05 | P2 | release | Render | 1.0.6 APK server ro'yxatida yo'q; saytda 1.0.5 | Ochiq — kalit kerak |
| A-06 | P1 | security | chat | Render API kaliti chatga yozilgan | **Foydalanuvchi revoke qilishi kerak** |

Bu sessiyada yangi P0/P1 backend, frontend yoki mobile xatosi topilmadi.

## 10. Tuzatilgan xatolar

Oldingi ishda (commit `0bab803`, 1.0.6): tarmoq uzilganda GET qayta urinish; to'liq uz/ru/en tarjimalar; 3D xona ko'rinishi uchun GLB cutaway; bot buyurtma tugmalari tartibi. Har biriga regressiya testi qo'shilgan.

## 11. Test natijalari jadvali

| Modul | Test | Natija | Izoh |
|---|---|---|---|
| Backend | Unit/API/Permission (SQLite) | PASS | 898 ran, 13 skipped |
| Backend | PostgreSQL 16 | PASS | 898 ran |
| Backend | Migration drift | PASS | No changes |
| Backend | Django check | PASS | |
| Frontend | Unit (vitest) | PASS | 225 |
| Frontend | TypeScript | PASS | |
| Frontend | Production build | PASS | |
| Frontend | ESLint | PASS (warnings) | 0 xato |
| Frontend | E2E (Playwright) | BLOCKED | bu sessiyada bajarilmagan |
| Telegram | Pytest | PASS | 52 |
| Telegram | Callback tests | PASS | mock |
| Mobile | flutter analyze | PASS | |
| Mobile | flutter test | PASS | +70 |
| Mobile | Live e2e | PASS (3) / SKIP (orders) | |
| Mobile | Android release build | PASS | 1.0.6+7 |
| Mobile | Device/emulator | BLOCKED | qurilma yo'q |
| Integration | Cross-platform e2e | PARTIAL | backend↔mobile PASS; bot BLOCKED |
| Security | Statik + konfiguratsiya | PASS (qisman) | dependency audit BLOCKED |
| Performance | RAM | PASS | max 69%, min available 31% |

## 12. Cheklovlar va BLOCKED funksiyalar

- AI provayder: yo'q (foydalanuvchi qaroriga ko'ra). Rasm tahlili va AI chat — mock/disabled.
- SMS, Payme/Click/Uzum tranzaksiyalari: haqiqiy chaqiruv qilinmagan (ruxsat yo'q). Faqat unit testlar.
- Telegram: haqiqiy xabar yuborilmagan.
- Emulyator/qurilma: yo'q.
- Brauzer E2E: bu sessiyada bajarilmagan.
- Dependency vulnerability scan: vositalar yo'q.
- Production DB: tegilmagan.

## 13. Yakuniy holat

**READY WITH LIMITATIONS.** Asosiy biznes jarayonlari (ro'yxatdan o'tish, login, loyiha, kalkulyator, xona dizayni, buyurtma API'si) backend testlari va mobile jonli e2e bilan tasdiqlangan. Cheklovlar yuqoridagi 12-bo'limda.

## 14. Keyingi tavsiyalar

1. Render API kalitini revoke qilish (A-06).
2. Render bazasiga 1.0.6 APK ni ro'yxatga olish (`publish_android_release`) — A-05.
3. Brauzer E2E'ni (Playwright, oldingi e2e skriptlari) qayta ishga tushirish.
4. Production'da `schema/` va `docs/` ni yopish yoki admin'ga cheklash (A-02).
5. Google auth xatolarini log qilish (A-01).
6. Frontend code splitting (A-04) va ESLint ogohlantirishlarini kamaytirish (A-03).
7. Dependency audit: `pip-audit` va `npm audit` ni CI'ga qo'shish.
8. Uzluksiz RAM/CPU monitoring uchun test vaqtida `vmstat 5` yozib borish.
