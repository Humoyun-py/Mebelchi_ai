# API integration smoke test for a RUNNING stack (staging!). It registers three throwaway users and creates a workshop, an order and a task.
# Needs a superuser smoke-admin@example.com whose password is in the file given as argument; BASE below must point at the stack.
# Used for the Phase 4 check against `docker compose -p p4test` on port 18080. Never run it against production.
import json, sys, urllib.request, urllib.error
BASE = "http://localhost:18080/api/v1/"; PW = open(sys.argv[1]).read().strip()
fails = []
def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"null")
        except Exception: return e.code, None
def check(name, got, want):
    ok = got == want or (callable(want) and want(got))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   got={got!r}")); 
    if not ok: fails.append(name)
def reg(email):
    s, d = call("POST", "auth/register/", {"first_name": "T", "last_name": "U", "email": email, "password": PW, "confirm_password": PW}); assert s == 201, (s, d); return d
def login(email):
    s, d = call("POST", "auth/login/", {"email": email, "password": PW}); assert s == 200, (s, d); return d["access"] if "access" in d else d["tokens"]["access"]
import time; tag = str(int(time.time()))
owner_e, other_e, emp_e = f"o{tag}@example.com", f"x{tag}@example.com", f"e{tag}@example.com"
for e in (owner_e, other_e, emp_e): reg(e)
admin, owner, other, emp = login("smoke-admin@example.com"), login(owner_e), login(other_e), login(emp_e)
uid = {e: call("GET", "admin-api/users/?search=" + e, token=admin)[1]["results"][0]["id"] for e in (owner_e, emp_e)}

check("normal user cannot call the admin API", call("GET", "admin-api/workshops/", token=owner)[0], 403)
check("normal user cannot assign roles", call("PATCH", f"admin-api/users/{uid[owner_e]}/", {"role": "workshop"}, token=owner)[0], 403)
check("a workshop cannot be created without the Workshop role", call("POST", "workshops/", {"name": "Nope"}, token=owner)[0], 403)
check("admin assigns the workshop role", call("PATCH", f"admin-api/users/{uid[owner_e]}/", {"role": "workshop"}, token=admin)[0], 200)
s, ws = call("POST", "workshops/", {"name": f"Smoke Shop {tag}", "city": "Samarkand"}, token=owner)
check("workshop created as pending", (s, ws.get("status"), ws.get("my_role")), (201, "pending", "owner"))
wid = ws["id"]
check("orders are closed while pending", call("POST", "orders/", {"workshop": wid, "title": "K", "customer_name": "Ali"}, token=owner)[0], 403)
check("owner cannot approve own workshop", call("POST", f"admin-api/workshops/{wid}/approve/", {}, token=owner)[0], 403)
check("owner cannot self-activate via PATCH", call("PATCH", f"workshops/{wid}/", {"status": "active"}, token=owner)[0], 403)
s, lst = call("GET", "admin-api/workshops/?status=pending&search=" + tag, token=admin)
check("admin sees it in the pending list", (s, [w["id"] for w in lst["results"]]), (200, [wid]))
check("reject without a reason is refused", call("POST", f"admin-api/workshops/{wid}/reject/", {}, token=admin)[0], 400)
s, r = call("POST", f"admin-api/workshops/{wid}/reject/", {"note": "Please add a phone number"}, token=admin)
check("reject with a reason", (s, r.get("status"), r.get("review_note")), (200, "rejected", "Please add a phone number"))
check("owner sees the reason", call("GET", f"workshops/{wid}/", token=owner)[1].get("review_note"), "Please add a phone number")
check("rejected workshop accepts no orders", call("POST", "orders/", {"workshop": wid, "title": "K", "customer_name": "Ali"}, token=owner)[0], 403)
check("admin approves (reconsiders)", call("POST", f"admin-api/workshops/{wid}/approve/", {}, token=admin)[1].get("status"), "active")
check("a second approval is refused", call("POST", f"admin-api/workshops/{wid}/approve/", {}, token=admin)[0], 400)
s, o = call("POST", "orders/", {"workshop": wid, "title": "Kitchen", "customer_name": "Ali Valiyev", "total_price": "1000.00"}, token=owner)
check("owner creates an order", (s, o.get("status"), o.get("order_number", "").startswith("ORD-")), (201, "new", True))
s, inv = call("POST", f"workshops/{wid}/members/", {"email": emp_e}, token=owner)
check("owner invites an employee", s, 201)
check("employee accepts", call("PATCH", f"workshops/{wid}/members/{inv['id']}/", {"status": "active"}, token=emp)[0], 200)
s, mem = call("GET", f"workshops/{wid}/members/", token=owner)
emp_member = [m for m in mem["results"] if m.get("status") == "active" and m.get("role") == "employee"][0]["id"]
s, t = call("POST", "tasks/", {"workshop": wid, "order": o["id"], "title": "Cut panels", "assigned_to": emp_member}, token=owner)
check("owner assigns a task", (s, t.get("status")), (201, "pending"))
check("employee sees only their task", call("GET", "tasks/", token=emp)[1]["count"], 1)
check("employee moves it to in_progress", call("PATCH", f"tasks/{t['id']}/", {"status": "in_progress"}, token=emp)[0], 200)
s, od = call("GET", f"orders/{o['id']}/", token=emp)
check("employee sees the order without money fields", (s, "total_price" in od), (200, False))
check("employee cannot read statistics", call("GET", f"workshops/{wid}/statistics/", token=emp)[0], 403)
check("owner reads statistics", call("GET", f"workshops/{wid}/statistics/", token=owner)[0], 200)
check("a stranger gets 404 for the workshop", call("GET", f"workshops/{wid}/", token=other)[0], 404)
check("a stranger gets 404 for the order", call("GET", f"orders/{o['id']}/", token=other)[0], 404)
check("a stranger sees no tasks", call("GET", "tasks/", token=other)[1]["count"], 0)
s, h = call("GET", f"admin-api/audit-logs/?model=workshops.workshop&object_id={wid}", token=admin)
check("audit history of the workshop", [e["event"] for e in h["results"]][::-1], ["workshop.created", "workshop.rejected", "workshop.approved"])
check("owner cannot read the audit log", call("GET", "admin-api/audit-logs/", token=owner)[0], 403)
check("anonymous request is 401", call("GET", "workshops/")[0], 401)
print("\nAPI integration:", "ALL PASSED" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
