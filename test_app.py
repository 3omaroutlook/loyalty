import os, tempfile
import db
db.DB_PATH = os.path.join(tempfile.mkdtemp(), "t.db")
db.MIN_SECONDS_BETWEEN_STAMPS = 0

import wallet
calls = {"push": 0, "fail_card": False}
wallet.ensure_class = lambda cafe: None
def fake_card(cafe, cust):
    if calls["fail_card"]:
        raise wallet.WalletError("boom")
    return "https://pay.google.com/gp/v/save/FAKE"
wallet.create_card = fake_card
def fake_push(cafe, cust): calls["push"] += 1
wallet.push_stamps = fake_push

from fastapi.testclient import TestClient
import app as appmod
c = TestClient(appmod.app)
db.add_cafe("demo", "Demo Cafe", "https://x/y.png", stamps_required=2)
db.set_cashier_pin("demo", "1234")

assert c.get("/c/demo").status_code == 200 and "Demo Cafe" in c.get("/c/demo").text
assert c.get("/c/nope").status_code == 404

r = c.post("/c/demo/register", data={"name": "Ahmed", "phone": "01001234567", "agree": "yes"})
assert "FAKE" in r.text, r.text[:400]
r = c.post("/c/demo/register", data={"name": "Ahmed", "phone": "01001234567", "agree": "yes"})
assert "مسجّل بالفعل" in r.text
r = c.post("/c/demo/register", data={"name": "Ali", "phone": "01001234568", "agree": ""})
assert "توافق" in r.text
calls["fail_card"] = True
r = c.post("/c/demo/register", data={"name": "Omar", "phone": "01001234569", "agree": "yes"})
assert "مشكلة مؤقتة" in r.text and db.find_customer(1, "01001234569") is None
calls["fail_card"] = False

# الكاشير
assert c.post("/cashier/demo/stamp", json={"phone": "01001234567"}).status_code == 401
assert "الكود غلط" in c.post("/cashier/demo/login", data={"pin": "9999"}).text
r = c.post("/cashier/demo/login", data={"pin": "1234"}, follow_redirects=True)
assert "صرف مكافأة" in r.text
r = c.post("/cashier/demo/stamp", json={"phone": "01001234567", "key": "a1"}).json()
assert r["ok"] and "1 / 2" in r["message"], r
r = c.post("/cashier/demo/stamp", json={"phone": "01001234567", "key": "a1"}).json()
assert "قبل كده" in r["message"]
r = c.post("/cashier/demo/redeem", json={"phone": "01001234567", "key": "r1"}).json()
assert not r["ok"]
r = c.post("/cashier/demo/stamp", json={"phone": "01001234567", "key": "a2"}).json()
assert "جاهز" in r["message"]
r = c.post("/cashier/demo/redeem", json={"phone": "01001234567", "key": "r2"}).json()
assert r["ok"] and "0 / 2" in r["message"]
r = c.post("/cashier/demo/stamp", json={"phone": "123", "key": "z"}).json()
assert not r["ok"]
assert calls["push"] == 3, calls
# تحديد المحاولات
c2 = TestClient(appmod.app)
for _ in range(5): c2.post("/cashier/demo/login", data={"pin": "0000"})
assert "محاولات كتير" in c2.post("/cashier/demo/login", data={"pin": "1234"}).text
print("كل اختبارات الويب نجحت")
