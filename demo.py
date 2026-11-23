"""تجربة كاملة: كافيه + عميل + كارت على الموبايل + ختم لحظي."""
import db
import wallet

LOGO = "https://drive.google.com/uc?export=view&id=11DtjAtqqlMFiukHR3pPrXUz3bdWZI6PB"

db.init_db()
cafe = db.get_cafe("demo_cafe")
if not cafe:
    db.add_cafe("demo_cafe", "Demo Cafe", LOGO, color="#3b2a20", stamps_required=8)
    cafe = db.get_cafe("demo_cafe")

phone = input("Your phone (01xxxxxxxxx): ")
name = input("Your name: ")

wallet.ensure_class(cafe)
customer = db.register_customer(cafe["id"], phone, name, agreed=True) \
    or db.find_customer(cafe["id"], phone)

print("\nAdd to Wallet link:\n" + wallet.create_card(cafe, customer))
input("\nAdd the card on your phone, then press Enter...")

customer, done = db.add_stamp(cafe["id"], phone)
wallet.push_stamps(cafe, customer)
print("Stamps now:", customer["stamps"], "- check your card")
