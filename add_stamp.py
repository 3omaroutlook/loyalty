import sys
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

KEY_FILE = "service-account.json"
ISSUER_ID = "3388000000023236972"
OBJECT_ID = f"{ISSUER_ID}.test_001"
BASE = "https://walletobjects.googleapis.com/walletobjects/v1"

stamps = int(sys.argv[1])  # عدد الأختام الجديد

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE,
    scopes=["https://www.googleapis.com/auth/wallet_object.issuer"],
)
session = AuthorizedSession(creds)

patch = {"loyaltyPoints": {"label": "Stamps", "balance": {"string": f"{stamps} / 8"}}}
r = session.patch(f"{BASE}/loyaltyObject/{OBJECT_ID}", json=patch)
print(r.status_code, r.text[:200])
