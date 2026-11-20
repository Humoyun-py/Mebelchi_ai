# Illustrative plan definitions. Prices/limits are editable in the admin panel.
PLANS = [
    dict(slug="free", name="Free", price_usd="0", storage_mb=200, max_projects=5, max_exports_per_month=10, sort_order=1,
         features=["Material calculator", "Cutting list", "3D preview", "5 projects"]),
    dict(slug="starter", name="Starter", price_usd="9", storage_mb=2048, max_projects=25, max_exports_per_month=100, sort_order=2,
         features=["Everything in Free", "PDF and Excel export", "Material optimizer", "25 projects"]),
    dict(slug="professional", name="Professional", price_usd="29", storage_mb=20480, max_projects=0, max_exports_per_month=0, sort_order=3,
         features=["Everything in Starter", "Unlimited projects", "GLB/GLTF/OBJ export", "Priority support"]),
    dict(slug="enterprise", name="Enterprise", price_usd="99", storage_mb=204800, max_projects=0, max_exports_per_month=0, sort_order=4,
         features=["Everything in Professional", "Team workspaces (planned)", "Custom materials catalogue", "Dedicated support"]),
]
