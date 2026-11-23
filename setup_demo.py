"""يجهّز كافيه تجريبي + كود كاشير، ويطبع الروابط."""
import db
import wallet

LOGO = "https://drive.google.com/uc?export=view&id=11DtjAtqqlMFiukHR3pPrXUz3bdWZI6PB"
PIN = "1234"   # للتجربة فقط

db.init_db()
if not db.get_cafe("demo_cafe"):
    db.add_cafe("demo_cafe", "Demo Cafe", LOGO, color="#3b2a20", stamps_required=8)
db.set_cashier_pin("demo_cafe", PIN)
wallet.ensure_class(db.get_cafe("demo_cafe"))

print("تمام. افتح الروابط دي (بدّل localhost بعنوان اللابتوب لو من الموبايل):")
print("  صفحة العميل : http://localhost:8000/c/demo_cafe")
print("  صفحة الكاشير: http://localhost:8000/cashier/demo_cafe   (الكود:", PIN + ")")
