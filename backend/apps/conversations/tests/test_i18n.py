from django.test import SimpleTestCase

from apps.conversations import assistant as a


class LanguageTests(SimpleTestCase):
    def test_detect(self):
        self.assertEqual(a.detect_lang("Salom, qalaysan"), "uz")
        self.assertEqual(a.detect_lang("shkaf 800x2000x400 3 ta tokcha"), "uz")
        self.assertEqual(a.detect_lang("Привет, как дела?"), "ru")
        self.assertEqual(a.detect_lang("hello there"), "en")
        self.assertEqual(a.detect_lang("800x2000x400", "ru"), "ru")

    def test_small_talk_in_user_language(self):
        for text, lang in [("Salom", "uz"), ("Assalomu alaykum", "uz"), ("rahmat", "uz"), ("Qalaysan?", "uz"), ("Kimsan sen?", "uz"),
                           ("Привет", "ru"), ("спасибо", "ru"), ("Как дела?", "ru"), ("Ты кто?", "ru"), ("hello", "en"), ("thanks", "en"), ("who are you?", "en")]:
            reply, meta = a.respond(text)
            self.assertEqual(meta["intent"], "smalltalk", text)
            self.assertEqual(meta["lang"], lang, text)
        self.assertIn("Assalomu", a.respond("salom")[0])
        self.assertIn("Здравствуйте", a.respond("привет")[0])

    def test_calculation_in_uzbek_and_russian(self):
        text, meta = a.respond("shkaf 800x2000x400, 3 ta tokcha va 2 ta eshik")
        self.assertEqual(meta["intent"], "calculation")
        self.assertEqual((meta["input"]["shelves"], meta["input"]["doors"]), (3, 2))
        self.assertIn("Yon devor", text)
        self.assertIn("Kromka", text)
        text, meta = a.respond("шкаф 1000x2200x580, 4 полки, 2 двери")
        self.assertEqual((meta["input"]["shelves"], meta["input"]["doors"]), (4, 2))
        self.assertIn("Боковина", text)

    def test_limits_and_errors_localized(self):
        self.assertIn("qoidalarga", a.respond("Menga zo'r dizayn o'ylab top")[0])
        self.assertIn("правил", a.respond("Придумай красивый дизайн")[0])
        self.assertEqual(a.respond("shkaf 800x2000")[1]["intent"], "need_input")
        self.assertIn("eni", a.respond("shkaf 800x2000")[0])

    def test_profile_language_fallback(self):
        text, meta = a.respond("cabinet", default_lang="ru")  # English word -> English
        self.assertEqual(meta["lang"], "en")
        self.assertEqual(a.respond("123", default_lang="uz")[1]["lang"], "uz")
