"""Interior designer presets (served to the client through /api/v1/meta/)."""


def L(en: str, uz: str, ru: str) -> dict:
    return {"en": en, "uz": uz, "ru": ru}


ROOMS = [
    {"id": "kitchen", "label": L("Kitchen", "Oshxona", "Кухня"), "categories": ["kitchen"]},
    {"id": "bedroom", "label": L("Bedroom", "Yotoqxona", "Спальня"), "categories": ["bedroom", "wardrobe"]},
    {"id": "living", "label": L("Living room", "Mehmonxona", "Гостиная"), "categories": ["living", "tv_unit"]},
    {"id": "office", "label": L("Office", "Ofis", "Офис"), "categories": ["office"]},
]
STYLES = [
    {"id": "modern", "label": L("Modern", "Zamonaviy", "Современный"), "text": L("Clean lines, neutral palette", "Aniq chiziqlar, neytral ranglar", "Чистые линии, нейтральная палитра"), "furniture": "#e5e7eb", "wall": "#cbd5e1"},
    {"id": "classic", "label": L("Classic", "Klassik", "Классический"), "text": L("Warm wood, traditional detail", "Issiq yog'och, an'anaviy bezak", "Тёплое дерево, традиционный декор"), "furniture": "#8b6f4e", "wall": "#e7dcc8"},
    {"id": "minimal", "label": L("Minimal", "Minimalizm", "Минимализм"), "text": L("Light, simple, uncluttered", "Yengil, sodda, ortiqcha narsasiz", "Светло, просто, ничего лишнего"), "furniture": "#f8fafc", "wall": "#ffffff"},
    {"id": "luxury", "label": L("Luxury", "Hashamatli", "Люкс"), "text": L("Rich finishes and contrast", "Boy qoplamalar va kontrast", "Богатая отделка и контраст"), "furniture": "#1e293b", "wall": "#94a3b8"},
]
