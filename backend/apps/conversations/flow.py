"""Room-design conversation as a state machine. Pure Python: no Django, no external AI.

The web app and the Telegram bot drive the same flow through apps/rooms/services.py. Every step has a *descriptor*
(what to ask: kind, fields, options, limits, texts in uz/ru/en), so both clients render the same questions from one place.

State is a plain dict: {"step": <key>, "answers": {...}}. It is stored by the caller and survives re-entry.

Steps: goal -> photo -> elements -> size -> openings -> style -> generate -> furnish -> done
  * `openings` is skipped when the user asked for no door and no window.
  * `generate` is automatic: the caller builds the 3D room right after `style` and moves the state to `furnish`.
  * Answering a step discards only the answers that depend on it (see DEPENDENTS), so a changed room size or door count
    can never leave stale openings behind, while an independent step (photo, style) never costs the user other answers.

Room photos are only stored as a reference; nothing analyses them.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from apps.designs.presets import STYLES, L
from apps.geometry import room as geo

STEPS = ["goal", "photo", "elements", "size", "openings", "style", "generate", "furnish", "done"]
VISIBLE_STEPS = ["goal", "photo", "elements", "size", "openings", "style", "furnish"]  # what the user sees counted

GOALS = [
    {"id": "kitchen", "label": L("Kitchen", "Oshxona", "Кухня"), "categories": ["kitchen"]},
    {"id": "bedroom", "label": L("Bedroom", "Yotoqxona", "Спальня"), "categories": ["bedroom", "wardrobe"]},
    {"id": "living", "label": L("Living room", "Mehmonxona", "Гостиная"), "categories": ["living", "tv_unit"]},
    {"id": "wardrobe", "label": L("Dressing room", "Kiyim xonasi", "Гардеробная"), "categories": ["wardrobe"]},
    {"id": "office", "label": L("Office", "Ofis", "Офис"), "categories": ["office"]},
    {"id": "other", "label": L("Other", "Boshqa", "Другое"), "categories": []},  # no filter: every template
]
GOAL_IDS = [g["id"] for g in GOALS]
STYLE_IDS = [s["id"] for s in STYLES]

TEMPLATE_LABELS = {
    "base-cabinet": L("Base cabinet", "Pastki shkaf", "Нижний шкаф"),
    "wall-cabinet": L("Wall cabinet", "Osma shkaf", "Навесной шкаф"),
    "drawer-base": L("Drawer base unit", "Yashikli pastki shkaf", "Нижний шкаф с ящиками"),
    "wardrobe-2door": L("Two-door wardrobe", "Ikki eshikli kiyim shkafi", "Шкаф с двумя дверями"),
    "wardrobe-3door": L("Three-door wardrobe", "Uch eshikli kiyim shkafi", "Шкаф с тремя дверями"),
    "tv-unit": L("TV unit", "TV tumba", "ТВ-тумба"),
    "bedside": L("Bedside table", "Karavot yonidagi tumba", "Прикроватная тумба"),
    "dresser": L("Dresser", "Komod", "Комод"),
    "bookcase": L("Bookcase", "Kitob javoni", "Книжный шкаф"),
    "office-cabinet": L("Office cabinet", "Ofis shkafi", "Офисный шкаф"),
}
WALL_LABELS = {"north": L("North wall", "Shimoliy devor", "Северная стена"), "east": L("East wall", "Sharqiy devor", "Восточная стена"),
               "south": L("South wall", "Janubiy devor", "Южная стена"), "west": L("West wall", "G'arbiy devor", "Западная стена")}

TEXT = {
    "goal": (L("What are we designing?", "Nimani loyihalaymiz?", "Что проектируем?"),
             L("Choose the room type.", "Xona turini tanlang.", "Выберите тип помещения.")),
    "photo": (L("Room photo", "Xona rasmi", "Фото комнаты"),
              L("Optional. The photo is saved as a reference only; it is not analysed, so you enter the sizes yourself.",
                "Ixtiyoriy. Rasm faqat ma'lumot uchun saqlanadi, tahlil qilinmaydi, o'lchamlarni o'zingiz kiritasiz.",
                "Необязательно. Фото сохраняется только как справка и не анализируется, размеры вводите сами.")),
    "elements": (L("Room elements", "Xona elementlari", "Элементы комнаты"),
                 L("How many doors and windows, and which furniture do you need?", "Nechta eshik va deraza bor, qanday mebel kerak?",
                   "Сколько дверей и окон и какая мебель нужна?")),
    "size": (L("Room size", "Xona o'lchami", "Размер комнаты"),
             L("Enter the inner size in millimetres.", "Ichki o'lchamni millimetrda kiriting.", "Введите внутренние размеры в миллиметрах.")),
    "openings": (L("Doors and windows", "Eshik va derazalar", "Двери и окна"),
                 L("Choose the wall and the distance from the wall start for each opening.",
                   "Har bir teshik uchun devor va devor boshidan masofani tanlang.", "Для каждого проёма выберите стену и расстояние от начала стены.")),
    "style": (L("Style", "Uslub", "Стиль"), L("Choose a style preset.", "Uslub presetini tanlang.", "Выберите стиль.")),
    "generate": (L("Building the 3D room", "3D xona yaratilmoqda", "Создаём 3D-комнату"), L("", "", "")),
    "furnish": (L("Place the furniture", "Mebelni joylashtiring", "Расставьте мебель"),
                L("Add, move, rotate and resize furniture inside the room.", "Mebel qo'shing, suring, aylantiring va o'lchamini o'zgartiring.",
                  "Добавляйте, двигайте, поворачивайте и меняйте размер мебели в комнате.")),
    "done": (L("Room saved", "Xona saqlandi", "Комната сохранена"), L("Your room design is saved.", "Xona loyihangiz saqlandi.", "Проект комнаты сохранён.")),
}

FIELD_LABELS = {
    "doors": L("Doors", "Eshiklar", "Двери"), "windows": L("Windows", "Derazalar", "Окна"), "furniture": L("Furniture", "Mebel", "Мебель"),
    "width": L("Width (mm)", "Eni (mm)", "Ширина (мм)"), "length": L("Length (mm)", "Bo'yi (mm)", "Длина (мм)"), "height": L("Height (mm)", "Balandligi (mm)", "Высота (мм)"),
}


class FlowError(Exception):
    pass


class StepMismatch(FlowError):
    def __init__(self, expected: str, got: str):
        super().__init__(f"This answer is for step '{got}', but the current step is '{expected}'.")
        self.expected, self.got = expected, got


class FlowValidationError(FlowError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


@dataclass
class FlowContext:
    """What the flow needs from outside: the furniture catalogue (slug, category, name, defaults)."""
    templates: list[dict] = field(default_factory=list)

    def allowed_templates(self, goal: str | None) -> list[dict]:
        cats = next((g["categories"] for g in GOALS if g["id"] == goal), [])
        return [t for t in self.templates if not cats or t["category"] in cats]


def initial() -> dict:
    return {"step": "goal", "answers": {}}


def required_openings(answers: dict) -> tuple[int, int]:
    e = answers.get("elements") or {}
    return int(e.get("doors", 0)), int(e.get("windows", 0))


def _label(slug: str, name: str) -> dict:
    return TEMPLATE_LABELS.get(slug) or L(name, name, name)


def catalog(ctx: FlowContext, goal: str | None = None) -> list[dict]:
    return [{"slug": t["slug"], "category": t["category"], "label": _label(t["slug"], t["name"]), "name": t["name"], "defaults": t["defaults"]}
            for t in (ctx.allowed_templates(goal) if goal else ctx.templates)]


def describe(state: dict, ctx: FlowContext) -> dict:
    """The question for the current step. Safe to send to any client."""
    step, answers = state["step"], state.get("answers", {})
    title, prompt = TEXT[step]
    shown = step if step in VISIBLE_STEPS else ("furnish" if step in ("generate", "done") else step)
    d = {"step": step, "title": title, "prompt": prompt, "index": VISIBLE_STEPS.index(shown) + 1, "total": len(VISIBLE_STEPS),
         "can_back": step in ("photo", "elements", "size", "openings", "style", "furnish"), "optional": step == "photo"}
    d["value"] = answers.get(ANSWER_KEY.get(step, step))  # lets a client prefill the form when the user comes back
    if step == "goal":
        d.update(kind="choice", options=[{"id": g["id"], "label": g["label"]} for g in GOALS])
    elif step == "photo":
        d.update(kind="photo", accepts=["image_id", "skip"])
    elif step == "elements":
        d.update(kind="number_group", fields=[
            {"key": "doors", "type": "number", "label": FIELD_LABELS["doors"], "min": 0, "max": geo.MAX_DOORS, "default": 1},
            {"key": "windows", "type": "number", "label": FIELD_LABELS["windows"], "min": 0, "max": geo.MAX_WINDOWS, "default": 1},
            {"key": "furniture", "type": "multi", "label": FIELD_LABELS["furniture"], "max": geo.MAX_ITEMS,
             "options": [{"id": c["slug"], "label": c["label"], "category": c["category"]} for c in catalog(ctx, answers.get("goal"))]}])
    elif step == "size":
        d.update(kind="number_group", unit="mm", fields=[
            {"key": k, "type": "number", "label": FIELD_LABELS[k], "min": geo.LIMITS[k][0], "max": geo.LIMITS[k][1]} for k in ("width", "length", "height")])
    elif step == "openings":
        doors, windows = required_openings(answers)
        room = answers.get("size") or {}
        d.update(kind="openings", required={"doors": doors, "windows": windows}, room=room, walls=[{"id": w, "label": WALL_LABELS[w]} for w in geo.WALLS],
                 limits={"door": geo.DOOR_LIMITS, "window": geo.WINDOW_LIMITS, "edge_margin": geo.EDGE_MARGIN, "gap": geo.OPENING_GAP},
                 wall_lengths={w: geo.wall_length(room, w) for w in geo.WALLS} if room else {})
    elif step == "style":
        d.update(kind="choice", options=[{"id": s["id"], "label": s["label"], "text": s["text"], "furniture": s["furniture"], "wall": s["wall"]} for s in STYLES])
    elif step == "generate":
        d.update(kind="summary", generating=True)
    elif step == "furnish":
        d.update(kind="furnish", catalog=catalog(ctx), rotations=list(geo.ROTATIONS), max_items=geo.MAX_ITEMS, room=answers.get("size"),
                 limits={k: list(v) for k, v in engine_limits().items()})
    else:  # done
        d.update(kind="summary", answers=answers)
    return d


def engine_limits() -> dict:
    from apps.calculations.engine import LIMITS
    return {k: LIMITS[k] for k in ("width", "height", "depth", "thickness", "shelves", "doors", "drawers")}


# ------------------------------------------------------------------------------------------------ transitions

def _int(errors: dict, key: str, v, lo: int, hi: int):
    if isinstance(v, bool) or not isinstance(v, int):
        errors[key] = "must be a whole number"
    elif not lo <= v <= hi:
        errors[key] = f"must be between {lo} and {hi}"
    else:
        return v
    return None


def _validate(step: str, value, answers: dict, ctx: FlowContext):
    if step == "goal":
        if value not in GOAL_IDS:
            raise FlowValidationError({"value": f"must be one of: {', '.join(GOAL_IDS)}"})
        return value
    if step == "photo":
        if not isinstance(value, dict):
            raise FlowValidationError({"value": "send {\"skip\": true} or {\"image_id\": <id>}"})
        if value.get("skip") is True:
            return {"skipped": True}
        i = value.get("image_id")
        if isinstance(i, bool) or not isinstance(i, int) or i <= 0:
            raise FlowValidationError({"image_id": "must be a positive image id"})
        return {"image_id": i}
    if step == "elements":
        if not isinstance(value, dict):
            raise FlowValidationError({"value": "must be an object"})
        errors: dict[str, str] = {}
        doors = _int(errors, "doors", value.get("doors", 0), 0, geo.MAX_DOORS)
        windows = _int(errors, "windows", value.get("windows", 0), 0, geo.MAX_WINDOWS)
        furniture = value.get("furniture", [])
        allowed = {t["slug"] for t in ctx.allowed_templates(answers.get("goal"))}
        if not isinstance(furniture, list) or not all(isinstance(s, str) for s in furniture):
            errors["furniture"] = "must be a list of furniture ids"
        elif len(furniture) > geo.MAX_ITEMS:
            errors["furniture"] = f"at most {geo.MAX_ITEMS} items"
        elif any(s not in allowed for s in furniture):
            errors["furniture"] = "contains furniture that is not available for this room type"
        if errors:
            raise FlowValidationError(errors)
        return {"doors": doors, "windows": windows, "furniture": list(furniture)}
    if step == "size":
        try:
            return geo.validate_room(value)
        except geo.RoomError as e:
            raise FlowValidationError(e.errors)
    if step == "openings":
        doors, windows = required_openings(answers)
        try:
            ops = geo.validate_openings(value, answers["size"])
        except geo.RoomError as e:
            raise FlowValidationError(e.errors)
        if sum(o["type"] == "door" for o in ops) != doors or sum(o["type"] == "window" for o in ops) != windows:
            raise FlowValidationError({"openings": f"expected {doors} door(s) and {windows} window(s)"})
        return ops
    if step == "style":
        if value not in STYLE_IDS:
            raise FlowValidationError({"value": f"must be one of: {', '.join(STYLE_IDS)}"})
        return value
    if step == "furnish":
        if not (isinstance(value, dict) and value.get("done") is True):
            raise FlowValidationError({"value": "send {\"done\": true} to finish"})
        return {"done": True}
    raise FlowError(f"Step '{step}' cannot be answered.")


ANSWER_KEY = {"goal": "goal", "photo": "photo", "elements": "elements", "size": "size", "openings": "openings", "style": "style", "furnish": "furnish"}
# answers that become invalid when the key step is answered again
DEPENDENTS = {"goal": ["elements", "openings"], "elements": ["openings"], "size": ["openings"]}


def _next(step: str, answers: dict) -> str:
    nxt = STEPS[STEPS.index(step) + 1]
    if nxt == "openings" and sum(required_openings(answers)) == 0:
        answers["openings"] = []
        return "style"
    return nxt


def apply_answer(state: dict, step: str, value, ctx: FlowContext) -> dict:
    """Returns the new state. Raises StepMismatch (409) for an answer to the wrong step, FlowValidationError (400) for a bad value."""
    if step != state["step"]:
        raise StepMismatch(state["step"], step)
    if step in ("generate", "done"):
        raise FlowError(f"Step '{step}' is automatic.")
    new = copy.deepcopy(state)
    answers = new["answers"]
    cleaned = _validate(step, value, answers, ctx)
    for dependent in DEPENDENTS.get(step, []):
        answers.pop(dependent, None)
    answers[ANSWER_KEY[step]] = cleaned
    new["step"] = _next(step, answers)
    return new


def back(state: dict) -> dict:
    """One step back, keeping every answer. `furnish` goes back to `style`; the room is rebuilt when style is answered again."""
    step, answers = state["step"], state.get("answers", {})
    if step not in ("photo", "elements", "size", "openings", "style", "furnish"):
        raise FlowError("There is no earlier step to go back to." if step == "goal" else f"Cannot go back from '{step}'.")
    new = copy.deepcopy(state)
    if step == "furnish":
        new["step"] = "style"
    elif step == "style":
        new["step"] = "openings" if sum(required_openings(answers)) else "size"
    else:
        new["step"] = STEPS[STEPS.index(step) - 1]
    return new


def to_furnish(state: dict) -> dict:
    """Called by the service once the 3D room has been built."""
    if state["step"] != "generate":
        raise FlowError("Not generating.")
    new = copy.deepcopy(state)
    new["step"] = "furnish"
    return new


def finish(state: dict) -> dict:
    return apply_answer(state, "furnish", {"done": True}, FlowContext())
