TEMPLATES = [
    ("base-cabinet", "kitchen", "Base cabinet", "Kitchen floor unit with door and shelf", dict(width=600, height=720, depth=560, thickness=18, shelves=1, doors=1, drawers=0)),
    ("wall-cabinet", "kitchen", "Wall cabinet", "Hanging kitchen unit", dict(width=600, height=720, depth=320, thickness=18, shelves=1, doors=1, drawers=0)),
    ("drawer-base", "kitchen", "Drawer base unit", "Three-drawer base unit", dict(width=600, height=720, depth=560, thickness=18, shelves=0, doors=0, drawers=3)),
    ("wardrobe-2door", "wardrobe", "Two-door wardrobe", "Classic hinged wardrobe", dict(width=1000, height=2200, depth=580, thickness=18, shelves=4, doors=2, drawers=0)),
    ("wardrobe-3door", "wardrobe", "Three-door wardrobe", "Wide hinged wardrobe", dict(width=1500, height=2200, depth=580, thickness=18, shelves=5, doors=3, drawers=0)),
    ("tv-unit", "tv_unit", "TV unit", "Low media console", dict(width=1800, height=450, depth=400, thickness=18, shelves=1, doors=2, drawers=0)),
    ("bedside", "bedroom", "Bedside table", "Single drawer bedside", dict(width=450, height=500, depth=400, thickness=18, shelves=0, doors=0, drawers=2)),
    ("dresser", "bedroom", "Dresser", "Four-drawer chest", dict(width=900, height=1000, depth=480, thickness=18, shelves=0, doors=0, drawers=4)),
    ("bookcase", "living", "Bookcase", "Open bookcase", dict(width=800, height=1800, depth=300, thickness=18, shelves=5, doors=0, drawers=0)),
    ("office-cabinet", "office", "Office cabinet", "Filing storage with doors", dict(width=900, height=1200, depth=450, thickness=18, shelves=2, doors=2, drawers=0)),
]
CATEGORIES = [
    {"slug": "kitchen", "name": "Kitchen"}, {"slug": "wardrobe", "name": "Wardrobe"}, {"slug": "tv_unit", "name": "TV unit"},
    {"slug": "bedroom", "name": "Bedroom"}, {"slug": "living", "name": "Living room"}, {"slug": "office", "name": "Office"},
]
