from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from google.auth import jwt

KEY_FILE = "service-account.json"
ISSUER_ID = "3388000000023236972"
CLASS_ID = f"{ISSUER_ID}.cafe_test_class"
OBJECT_ID = f"{ISSUER_ID}.test_001"
BASE = "https://walletobjects.googleapis.com/walletobjects/v1"

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE,
    scopes=["https://www.googleapis.com/auth/wallet_object.issuer"],
)
session = AuthorizedSession(creds)

# 1) الـ Class (قالب الكافيه)
loyalty_class = {
    "id": CLASS_ID,
    "issuerName": "Test Cafe",
    "programName": "Test Cafe Stamps",
    "reviewStatus": "UNDER_REVIEW",
    "hexBackgroundColor": "#3b2a20",
    "programLogo": {
        "sourceUri": {
            "uri": "https://drive.google.com/uc?export=view&id=11DtjAtqqlMFiukHR3pPrXUz3bdWZI6PB"
        }
    },
}
r = session.post(f"{BASE}/loyaltyClass", json=loyalty_class)
print("Class:", r.status_code, r.text[:300])  # 409 = موجود قبل كده، عادي

# 2) كارت العميل (Object)
loyalty_object = {
    "id": OBJECT_ID,
    "classId": CLASS_ID,
    "state": "ACTIVE",
    "accountId": "test_001",
    "accountName": "Test Customer",
    "loyaltyPoints": {"label": "Stamps", "balance": {"string": "0 / 8"}},
    "barcode": {"type": "QR_CODE", "value": "test_001"},
}
r = session.post(f"{BASE}/loyaltyObject", json=loyalty_object)
print("Object:", r.status_code, r.text[:300])

# 3) لينك الإضافة (JWT موقّع)
claims = {
    "iss": creds.service_account_email,
    "aud": "google",
    "origins": [],
    "typ": "savetowallet",
    "payload": {"loyaltyObjects": [{"id": OBJECT_ID}]},
}
token = jwt.encode(creds.signer, claims).decode("utf-8")
print("\nAdd to Wallet link:\nhttps://pay.google.com/gp/v/save/" + token)
