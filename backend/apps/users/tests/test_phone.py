import re
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core import sms
from apps.core.tests.helpers import client_for, make_user
from apps.users.models import PhoneVerification, User

REQ, CONF = "/api/v1/users/me/phone/request/", "/api/v1/users/me/phone/confirm/"
PHONE = "+998 90 123 45 67"
NORM = "998901234567"


class FakeSms(sms.SmsSender):
    name = "fake"
    sent: list = []

    def send(self, phone, text):
        FakeSms.sent.append((phone, text))


class Failing(FakeSms):
    def send(self, phone, text):
        raise sms.SmsError("down")


def with_sms(sender_cls=FakeSms):
    return mock.patch("apps.core.sms.get_sms", lambda: sender_cls())


def last_code():
    return re.search(r"\b(\d{6})\b", FakeSms.sent[-1][1]).group(1)


@override_settings(PHONE_CODE_RESEND_SECONDS=0)
class PhoneVerificationTests(TestCase):
    def setUp(self):
        FakeSms.sent = []
        self.u = make_user()
        self.c = client_for(self.u)

    def test_sms_not_configured_is_503_and_stores_nothing(self):
        r = self.c.post(REQ, {"phone": PHONE}, format="json")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(PhoneVerification.objects.count(), 0)

    def test_full_flow_marks_phone_verified(self):
        with with_sms():
            r = self.c.post(REQ, {"phone": PHONE}, format="json")
            self.assertEqual((r.status_code, r.data["phone"]), (200, NORM))
            self.assertEqual(FakeSms.sent[0][0], NORM)
            r = self.c.post(CONF, {"phone": PHONE, "code": last_code()}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["phone_verified"])
        self.u.refresh_from_db()
        self.assertEqual((self.u.phone, self.u.phone_verified_at is not None), (NORM, True))
        self.assertTrue(AuditLog.objects.filter(event="phone.verified").exists())

    def test_code_is_not_stored_in_clear_and_not_in_the_audit_log(self):
        with with_sms():
            self.c.post(REQ, {"phone": PHONE}, format="json")
        code = last_code()
        row = PhoneVerification.objects.get()
        self.assertNotIn(code, row.code_hash)
        self.assertFalse(any(code in str(a.changes) + a.object_repr for a in AuditLog.objects.all()))

    def test_wrong_code_is_refused_and_attempts_are_really_counted(self):
        with with_sms():
            self.c.post(REQ, {"phone": PHONE}, format="json")
            good = last_code()
            bad = "000000" if good != "000000" else "111111"
            for _ in range(5):
                self.assertEqual(self.c.post(CONF, {"phone": PHONE, "code": bad}, format="json").status_code, 400)
            self.assertEqual(PhoneVerification.objects.get().attempts, 5)      # not rolled back by the error
            # after the limit even the right code is dead
            self.assertEqual(self.c.post(CONF, {"phone": PHONE, "code": good}, format="json").status_code, 400)
        self.u.refresh_from_db()
        self.assertIsNone(self.u.phone_verified_at)

    def test_expired_code(self):
        with with_sms():
            self.c.post(REQ, {"phone": PHONE}, format="json")
            PhoneVerification.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(self.c.post(CONF, {"phone": PHONE, "code": last_code()}, format="json").status_code, 400)

    def test_code_works_once_and_a_new_code_supersedes_the_old(self):
        with with_sms():
            self.c.post(REQ, {"phone": PHONE}, format="json")
            first = last_code()
            self.c.post(REQ, {"phone": PHONE}, format="json")
            second = last_code()
            if first != second:
                self.assertEqual(self.c.post(CONF, {"phone": PHONE, "code": first}, format="json").status_code, 400)
            self.assertEqual(self.c.post(CONF, {"phone": PHONE, "code": second}, format="json").status_code, 200)
            self.assertEqual(self.c.post(CONF, {"phone": PHONE, "code": second}, format="json").status_code, 400)

    def test_code_for_another_number_or_user_is_useless(self):
        other = make_user("o@x.com")
        with with_sms():
            self.c.post(REQ, {"phone": PHONE}, format="json")
            code = last_code()
            self.assertEqual(self.c.post(CONF, {"phone": "+998 91 000 00 00", "code": code}, format="json").status_code, 400)
            self.assertEqual(client_for(other).post(CONF, {"phone": PHONE, "code": code}, format="json").status_code, 400)

    def test_a_number_verified_elsewhere_is_refused(self):
        make_user("o@x.com", phone=NORM, phone_verified_at=timezone.now())
        with with_sms():
            r = self.c.post(REQ, {"phone": PHONE}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(FakeSms.sent, [])

    def test_database_forbids_two_verified_owners_but_allows_unverified_duplicates(self):
        make_user("o@x.com", phone=NORM, phone_verified_at=timezone.now())
        make_user("p@x.com", phone=NORM)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_user("q@x.com", phone=NORM, phone_verified_at=timezone.now())

    def test_invalid_phone(self):
        with with_sms():
            for bad in ("12345", "+7 916 123-45-67", ""):
                self.assertEqual(self.c.post(REQ, {"phone": bad}, format="json").status_code, 400, bad)
        self.assertEqual(FakeSms.sent, [])

    def test_unsent_code_is_dead_when_the_provider_fails(self):
        with with_sms(Failing):
            r = self.c.post(REQ, {"phone": PHONE}, format="json")
        self.assertEqual(r.status_code, 502)
        self.assertIsNotNone(PhoneVerification.objects.get().used_at)

    def test_authentication_required(self):
        self.assertEqual(client_for().post(REQ, {"phone": PHONE}, format="json").status_code, 401)
        self.assertEqual(client_for().post(CONF, {"code": "123456"}, format="json").status_code, 401)

    def test_changing_the_profile_phone_drops_verification(self):
        self.u.phone, self.u.phone_verified_at = NORM, timezone.now()
        self.u.save()
        self.c.patch("/api/v1/users/me/", {"phone": NORM}, format="json")
        self.u.refresh_from_db()
        self.assertIsNotNone(self.u.phone_verified_at)                       # same number: still verified
        r = self.c.patch("/api/v1/users/me/", {"phone": "+998 93 111 22 33"}, format="json")
        self.assertFalse(r.data["phone_verified"])

    def test_phone_verified_cannot_be_set_through_the_profile(self):
        r = self.c.patch("/api/v1/users/me/", {"phone": NORM, "phone_verified": True, "phone_verified_at": "2026-01-01T00:00:00Z"}, format="json")
        self.assertFalse(r.data["phone_verified"])


class LimitTests(TestCase):
    def setUp(self):
        FakeSms.sent = []
        self.u = make_user()
        self.c = client_for(self.u)

    @override_settings(PHONE_CODE_RESEND_SECONDS=60)
    def test_resend_cooldown(self):
        with with_sms():
            self.assertEqual(self.c.post(REQ, {"phone": PHONE}, format="json").status_code, 200)
            self.assertEqual(self.c.post(REQ, {"phone": PHONE}, format="json").status_code, 429)
        self.assertEqual(len(FakeSms.sent), 1)

    @override_settings(PHONE_CODE_RESEND_SECONDS=0, PHONE_CODE_MAX_PER_DAY=3)
    def test_daily_cap(self):
        with with_sms():
            codes = [self.c.post(REQ, {"phone": PHONE}, format="json").status_code for _ in range(5)]
        self.assertEqual(codes, [200, 200, 200, 429, 429])
        self.assertEqual(len(FakeSms.sent), 3)
