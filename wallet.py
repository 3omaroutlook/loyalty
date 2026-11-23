"""التعامل مع Google Wallet API. بيعرض بس، والحقيقة في قاعدة البيانات."""
import os

from google.auth import jwt
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

KEY_FILE = os.environ.get("WALLET_KEY_FILE", "service-account.json")
ISSUER_ID = os.environ.get("WALLET_ISSUER_ID", "3388000000023236972")
BASE = "https://walletobjects.googleapis.com/walletobjects/v1"
SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

_creds = None
_session = None


class WalletError(Exception):
    pass


def _auth():
    global _creds, _session
    if _session is None:
        _creds = service_account.Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
        _session = AuthorizedSession(_creds)
    return _creds, _session


def class_id(cafe):
    return f"{ISSUER_ID}.cafe_{cafe['slug']}"


def object_id(cafe, customer):
    return f"{ISSUER_ID}.c{cafe['id']}_{customer['id']}"


def balance_text(cafe, stamps):
    return f"{stamps} / {cafe['stamps_required']}"


def ensure_class(cafe):
    """ينشئ كلاس الكافيه، ولو موجود يحدّث شكله."""
    _, session = _auth()
    body = {
        "id": class_id(cafe),
        "issuerName": cafe["name"],
        "programName": cafe["name"],
        "hexBackgroundColor": cafe["color"],
        "programLogo": {"sourceUri": {"uri": cafe["logo_url"]}},
        "textModulesData": [{
            "id": "reward",
            "header": "المكافأة",
            "body": f"كل {cafe['stamps_required']} ختم = {cafe['reward_text']}",
        }],
    }
    r = session.post(f"{BASE}/loyaltyClass", json={**body, "reviewStatus": "UNDER_REVIEW"})
    if r.status_code == 409:  # موجود: نحدّثه
        r = session.patch(f"{BASE}/loyaltyClass/{body['id']}",
                          json={**body, "reviewStatus": "UNDER_REVIEW"})
    if r.status_code != 200:
        raise WalletError(f"class: {r.status_code} {r.text[:300]}")


def create_card(cafe, customer):
    """ينشئ كارت العميل ويرجّع لينك Add to Google Wallet."""
    creds, session = _auth()
    oid = object_id(cafe, customer)
    obj = {
        "id": oid,
        "classId": class_id(cafe),
        "state": "ACTIVE",
        "accountId": oid.split(".")[1],
        "accountName": customer["name"],
        "loyaltyPoints": {"label": "الأختام",
                          "balance": {"string": balance_text(cafe, customer["stamps"])}},
        "barcode": {"type": "QR_CODE", "value": oid.split(".")[1]},
    }
    r = session.post(f"{BASE}/loyaltyObject", json=obj)
    if r.status_code not in (200, 409):
        raise WalletError(f"object: {r.status_code} {r.text[:300]}")
    claims = {
        "iss": creds.service_account_email,
        "aud": "google",
        "origins": [],
        "typ": "savetowallet",
        "payload": {"loyaltyObjects": [{"id": oid}]},
    }
    token = jwt.encode(creds.signer, claims).decode("utf-8")
    return f"https://pay.google.com/gp/v/save/{token}"


def push_stamps(cafe, customer):
    """يحدّث رقم الأختام على كارت العميل."""
    _, session = _auth()
    patch = {"loyaltyPoints": {"label": "الأختام",
                               "balance": {"string": balance_text(cafe, customer["stamps"])}}}
    r = session.patch(f"{BASE}/loyaltyObject/{object_id(cafe, customer)}", json=patch)
    if r.status_code != 200:
        raise WalletError(f"patch: {r.status_code} {r.text[:300]}")
