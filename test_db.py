import os, tempfile, time
import db

db.DB_PATH = os.path.join(tempfile.mkdtemp(), "t.db")
db.MIN_SECONDS_BETWEEN_STAMPS = 1
db.init_db()

cid = db.add_cafe("test_cafe", "Test Cafe", "https://example.com/logo.png", stamps_required=2)
assert db.normalize_phone("+20 100 123 4567") == "01001234567"
c = db.register_customer(cid, "01001234567", "Ahmed", True)
assert c["stamps"] == 0
assert db.register_customer(cid, "01001234567", "Ahmed", True) is None      # مسجّل قبل كده
try: db.register_customer(cid, "01001234568", "Ali", False); assert False
except db.LoyaltyError: pass

cu, done = db.add_stamp(cid, "01001234567", idem_key="k1"); assert done and cu["stamps"] == 1
cu, done = db.add_stamp(cid, "01001234567", idem_key="k1"); assert not done and cu["stamps"] == 1  # تكرار
try: db.add_stamp(cid, "01001234567", idem_key="k2"); assert False                              # بدري
except db.LoyaltyError: pass
time.sleep(1.1)
cu, done = db.add_stamp(cid, "01001234567", idem_key="k3"); assert cu["stamps"] == 2
cu, done = db.redeem(cid, "01001234567", idem_key="r1"); assert cu["stamps"] == 0
try: db.redeem(cid, "01001234567"); assert False
except db.LoyaltyError: pass
print("كل الاختبارات نجحت")
