"""Payme (Paycom) Merchant API, implemented from the official documentation at https://developer.help.paycom.uz/ (read 2026-11-27).

Payme calls US: one JSON-RPC endpoint, HTTP POST, `Authorization: Basic base64(login:key)`, amounts in tiyin, always HTTP 200 (errors travel in
the body). Methods: CheckPerformTransaction, CreateTransaction, PerformTransaction, CancelTransaction, CheckTransaction, GetStatement.

What the documentation does NOT state, and what was decided here (review before going live):
  * the error for a failed Basic authorisation: the documented -32504 ("insufficient privileges") is used;
  * PerformTransaction timeout: only the 12 h limit for a *created* transaction is documented, and that one is enforced;
  * the individual codes inside -31050..-31099: -31050 order not found, -31051 order cannot be paid (wrong state or currency),
    -31099 another payment for the order is waiting;
  * repeated PerformTransaction / CancelTransaction answer with the stored result (the docs only say retries happen).

Mapping: account field `order_id` (setting PAYME_ACCOUNT_FIELD) carries our `Order.order_number`. Only marketplace orders in UZS can be paid,
for exactly the amount still due. A performed payment becomes a confirmed `OrderPayment` (method=provider) in the same database transaction.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
import time
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.workshops.models import Order

from .. import services
from ..models import PaymentTransaction as Tx
from .base import PaymentProvider

logger = logging.getLogger("mebelchi.payments")

TIMEOUT_MS = 43_200_000                      # 12 hours, documented
STATE = {Tx.Status.CREATED: 1, Tx.Status.PERFORMED: 2, Tx.Status.CANCELLED: -1, Tx.Status.REFUNDED: -2}
REASON_TIMEOUT = 4
MAX_BODY = 64 * 1024
PAYABLE_STATUSES = (Order.Status.CONFIRMED, Order.Status.IN_PRODUCTION, Order.Status.QUALITY_CHECK, Order.Status.READY, Order.Status.DELIVERY)


def _m(ru: str, uz: str, en: str) -> dict:
    return {"ru": ru, "uz": uz, "en": en}


class PaymeError(Exception):
    def __init__(self, code: int, message: dict, data=None):
        super().__init__(code)
        self.code, self.message, self.data = code, message, data


E_AUTH = lambda: PaymeError(-32504, _m("Недостаточно привилегий", "Ruxsat yetarli emas", "Insufficient privileges"))
E_NOT_POST = lambda: PaymeError(-32300, _m("Метод запроса не POST", "So'rov usuli POST emas", "Request method is not POST"))
E_PARSE = lambda: PaymeError(-32700, _m("Ошибка разбора JSON", "JSON xato", "JSON parse error"))
E_INVALID = lambda: PaymeError(-32600, _m("Неверный запрос", "Noto'g'ri so'rov", "Invalid request"))
E_AMOUNT = lambda: PaymeError(-31001, _m("Неверная сумма", "Noto'g'ri summa", "Invalid amount"))
E_NO_TX = lambda: PaymeError(-31003, _m("Транзакция не найдена", "Tranzaksiya topilmadi", "Transaction not found"))
E_CANT_CANCEL = lambda: PaymeError(-31007, _m("Заказ выполнен, отмена невозможна", "Buyurtma bajarilgan, bekor qilib bo'lmaydi", "Order is fulfilled; cannot cancel"))
E_STATE = lambda: PaymeError(-31008, _m("Операция невозможна в этом состоянии", "Bu holatda amalni bajarib bo'lmaydi", "Operation not allowed in this state"))


def E_ACCOUNT(code: int, ru: str, uz: str, en: str, field: str):
    return PaymeError(code, _m(ru, uz, en), field)


def _field() -> str:
    return settings.PAYME_ACCOUNT_FIELD


def _now_ms() -> int:
    return int(time.time() * 1000)


def checkout_url(order: Order) -> str:
    """Payment link `<checkout>/base64(m=..;ac.<field>=..;a=<tiyin>)` exactly as in the documentation example (standard base64)."""
    tiyin = int(((order.total_price - order.paid_amount) * 100).to_integral_value())
    raw = f"m={settings.PAYME_MERCHANT_ID};ac.{_field()}={order.order_number};a={tiyin}"
    return f"{settings.PAYME_CHECKOUT_URL.rstrip('/')}/{base64.b64encode(raw.encode()).decode()}"


def _due_tiyin(order: Order) -> int:
    return int(((order.total_price - order.paid_amount) * Decimal(100)).to_integral_value())


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _find_order(params: dict, *, lock=False) -> Order:
    account = params.get("account")
    value = account.get(_field()) if isinstance(account, dict) else None
    f = _field()
    if not isinstance(value, str) or not value.strip():
        raise E_ACCOUNT(-31050, "Заказ не найден", "Buyurtma topilmadi", "Order not found", f)
    qs = Order.objects.filter(order_number=value.strip(), source=Order.Source.MARKETPLACE)
    order = (qs.select_for_update(of=("self",)) if lock else qs).first()
    if order is None:
        raise E_ACCOUNT(-31050, "Заказ не найден", "Buyurtma topilmadi", "Order not found", f)
    return order


def _check_payable(order: Order, amount) -> None:
    f = _field()
    if not _is_int(amount) or amount <= 0:
        raise E_AMOUNT()
    if (order.quote or {}).get("currency") != "UZS":
        raise E_ACCOUNT(-31051, "Заказ не оплачивается в UZS", "Buyurtma UZS da to'lanmaydi", "Order is not payable in UZS", f)
    if order.status not in PAYABLE_STATUSES or order.payment_status not in (Order.PaymentStatus.UNPAID, Order.PaymentStatus.PARTIALLY_PAID):
        raise E_ACCOUNT(-31051, "Заказ нельзя оплатить", "Buyurtmani to'lab bo'lmaydi", "Order cannot be paid now", f)
    if amount != _due_tiyin(order):
        raise E_AMOUNT()


def _expired(tx: Tx) -> bool:
    return _now_ms() - tx.created_ms > TIMEOUT_MS


def _result_create(tx: Tx) -> dict:
    return {"create_time": tx.created_ms, "transaction": str(tx.pk), "state": STATE[tx.status]}


def _audit(tx: Tx, event: str):
    record("update", model="finance.PaymentTransaction", object_id=tx.pk, object_repr=f"payme {tx.external_id} {tx.amount_minor}", actor=None, event=event)


# ----------------------------------------------------------------------------------------------------------------- methods
def check_perform(params: dict) -> dict:
    _check_payable(_find_order(params), params.get("amount"))
    return {"allow": True}


def create(params: dict) -> dict:
    ext, amount, t = params.get("id"), params.get("amount"), params.get("time")
    if not isinstance(ext, str) or not ext.strip() or len(ext) > 64 or not _is_int(t):
        raise E_INVALID()
    expired = False
    with transaction.atomic():
        # The order row is locked FIRST: parallel calls for one order are serialised here, so a retry that lost the race finds the winner's
        # transaction below and gets its answer, instead of looking like a second invoice.
        order = _find_order(params, lock=True)
        tx = Tx.objects.select_for_update().filter(provider="payme", external_id=ext).first()
        if tx:
            if tx.status != Tx.Status.CREATED:
                raise E_STATE()
            if _expired(tx):
                _cancel_row(tx, REASON_TIMEOUT)
                expired = True
            else:
                return _result_create(tx)
        else:
            _check_payable(order, amount)
            if Tx.objects.filter(order=order, status=Tx.Status.CREATED).exists():
                raise E_ACCOUNT(-31099, "Ожидается другой платёж по заказу", "Buyurtma uchun boshqa to'lov kutilmoqda", "Another payment for this order is pending", _field())
            tx = Tx.objects.create(provider="payme", external_id=ext, order=order, amount_minor=amount, currency="UZS", provider_time_ms=t, created_ms=_now_ms())
            _audit(tx, "payment.provider_created")
            return _result_create(tx)
    if expired:                                      # the cancellation above is committed; now tell Payme the call is refused
        raise E_STATE()


def _cancel_row(tx: Tx, reason: int) -> None:
    tx.status, tx.reason, tx.cancelled_ms = Tx.Status.CANCELLED, reason, _now_ms()
    tx.save(update_fields=["status", "reason", "cancelled_ms", "updated_at"])
    _audit(tx, "payment.provider_cancelled")


def perform(params: dict) -> dict:
    ext = params.get("id")
    if not isinstance(ext, str):
        raise E_INVALID()
    expired = False
    with transaction.atomic():
        tx = Tx.objects.select_for_update().filter(provider="payme", external_id=ext).first()
        if tx is None:
            raise E_NO_TX()
        if tx.status == Tx.Status.PERFORMED:
            return {"transaction": str(tx.pk), "perform_time": tx.performed_ms, "state": 2}
        if tx.status != Tx.Status.CREATED:
            raise E_STATE()
        if _expired(tx):
            _cancel_row(tx, REASON_TIMEOUT)
            expired = True
        else:
            try:
                with transaction.atomic():
                    row = services.settle_provider_payment(tx.order_id, kind="payment", amount=Decimal(tx.amount_minor) / 100,
                                                           reference=f"payme:{tx.external_id}", idempotency_key=f"payme:{tx.external_id}:pay")
            except ValidationError:
                raise E_STATE()
            tx.status, tx.performed_ms, tx.payment = Tx.Status.PERFORMED, _now_ms(), row
            tx.save(update_fields=["status", "performed_ms", "payment", "updated_at"])
            _audit(tx, "payment.provider_performed")
            return {"transaction": str(tx.pk), "perform_time": tx.performed_ms, "state": 2}
    if expired:
        raise E_STATE()


def cancel(params: dict) -> dict:
    ext, reason = params.get("id"), params.get("reason")
    if not isinstance(ext, str) or not _is_int(reason):
        raise E_INVALID()
    with transaction.atomic():
        tx = Tx.objects.select_for_update().filter(provider="payme", external_id=ext).first()
        if tx is None:
            raise E_NO_TX()
        if tx.status == Tx.Status.CREATED:
            _cancel_row(tx, reason)
        elif tx.status == Tx.Status.PERFORMED:
            order = Order.objects.select_for_update(of=("self",)).get(pk=tx.order_id)
            if order.status in (Order.Status.DELIVERED,):
                raise E_CANT_CANCEL()                # goods or service already provided
            try:
                with transaction.atomic():
                    row = services.settle_provider_payment(order.pk, kind="refund", amount=Decimal(tx.amount_minor) / 100,
                                                           reference=f"payme:{tx.external_id}", idempotency_key=f"payme:{tx.external_id}:refund")
            except ValidationError:
                raise E_CANT_CANCEL()
            tx.status, tx.reason, tx.cancelled_ms, tx.refund_payment = Tx.Status.REFUNDED, reason, _now_ms(), row
            tx.save(update_fields=["status", "reason", "cancelled_ms", "refund_payment", "updated_at"])
            _audit(tx, "payment.provider_refunded")
        return {"transaction": str(tx.pk), "cancel_time": tx.cancelled_ms, "state": STATE[tx.status]}


def _view(tx: Tx) -> dict:
    return {"create_time": tx.created_ms, "perform_time": tx.performed_ms or 0, "cancel_time": tx.cancelled_ms or 0, "transaction": str(tx.pk),
            "state": STATE[tx.status], "reason": tx.reason}


def check_transaction(params: dict) -> dict:
    ext = params.get("id")
    tx = Tx.objects.filter(provider="payme", external_id=ext).first() if isinstance(ext, str) else None
    if tx is None:
        raise E_NO_TX()
    return _view(tx)


def get_statement(params: dict) -> dict:
    lo, hi = params.get("from"), params.get("to")
    if not _is_int(lo) or not _is_int(hi):
        raise E_INVALID()
    qs = Tx.objects.filter(provider="payme", provider_time_ms__gte=lo, provider_time_ms__lte=hi).select_related("order").order_by("provider_time_ms", "id")
    return {"transactions": [{"id": t.external_id, "time": t.provider_time_ms, "amount": t.amount_minor, "account": {_field(): t.order.order_number},
                              **_view(t), "receivers": None} for t in qs]}


METHODS = {"CheckPerformTransaction": check_perform, "CreateTransaction": create, "PerformTransaction": perform, "CancelTransaction": cancel,
           "CheckTransaction": check_transaction, "GetStatement": get_statement}


class PaymeProvider(PaymentProvider):
    name = "payme"

    @property
    def enabled(self) -> bool:
        return bool(settings.PAYME_LOGIN and settings.PAYME_KEY)

    def _authorised(self, header: str) -> bool:
        scheme, _, token = (header or "").partition(" ")
        if scheme.lower() != "basic" or not token:
            return False
        try:
            given = base64.b64decode(token.strip(), validate=True)
        except (binascii.Error, ValueError):
            return False
        wanted = f"{settings.PAYME_LOGIN}:{settings.PAYME_KEY}".encode()
        return hmac.compare_digest(given, wanted)

    @staticmethod
    def _error(err: PaymeError, rid) -> dict:
        return {"error": {"code": err.code, "message": err.message, "data": err.data}, "id": rid}

    def handle_webhook(self, *, method: str, body: bytes, headers: dict) -> tuple[int, dict]:
        if method != "POST":
            return 200, self._error(E_NOT_POST(), None)
        if not self._authorised(headers.get("Authorization", "")):
            logger.warning("payme webhook: authorisation failed")
            return 200, self._error(E_AUTH(), None)
        if len(body) > MAX_BODY:
            return 200, self._error(E_INVALID(), None)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return 200, self._error(E_PARSE(), None)
        if not isinstance(payload, dict) or not isinstance(payload.get("method"), str) or not isinstance(payload.get("params"), dict):
            return 200, self._error(E_INVALID(), None)
        rid = payload.get("id")
        fn = METHODS.get(payload["method"])
        if fn is None:
            return 200, self._error(PaymeError(-32601, _m("Метод не найден", "Metod topilmadi", "Method not found"), payload["method"]), rid)
        try:
            return 200, {"result": fn(payload["params"]), "id": rid}
        except PaymeError as err:
            return 200, self._error(err, rid)
        except Exception:                        # noqa: BLE001  never leak internals to the caller; Payme retries on -32400
            logger.exception("payme %s failed", payload["method"])
            return 200, self._error(PaymeError(-32400, _m("Внутренняя ошибка", "Ichki xato", "Internal error")), rid)
