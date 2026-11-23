# LOYALTY

Digital loyalty cards for small shops and cafés, delivered through **Google Wallet**.
No app to install, no paper stamp cards.

> **Status: early-stage, working prototype.** The core flow works end to end on a real phone.
> It is not production-ready yet, and contributions and feedback are welcome.

## The problem

Most small cafés and restaurants (especially in Egypt and similar markets) still use paper
punch cards, or nothing at all. Existing loyalty platforms are expensive, need customers to
download a dedicated app, or require special hardware.

## How it works

1. The shop owner sets up a loyalty program (for example, "10 coffees = 1 free").
2. The customer opens a small web page, enters their name and phone number, agrees to the
   terms, and adds the card to **Google Wallet**.
3. After each purchase the cashier records it, and the stamps/points on the customer's
   phone card **update live**.

The design assumes cafés already have a tablet and a cashier who records the customer's
phone number, so rollout should take minutes, not days.

## What works today

- Google Wallet integration: loyalty class and customer card creation, verified on a real
  phone with live stamp updates
- Local database (SQLite) as the source of truth for customers, points and transactions
  (Google Wallet is display only)
- Customer registration page (name + phone + consent)
- Cashier page for recording purchases
- Demo cafe for testing the whole flow

## Roadmap

- [ ] Admin dashboard to manage multiple businesses
- [ ] Camera QR scanner for the cashier
- [ ] Google Wallet publishing access (production issuer)
- [ ] PostgreSQL support
- [ ] Hosting and a pilot with local cafés
- [ ] Setup guide for new shops

## Tech stack

Python, FastAPI, SQLite (PostgreSQL planned), HTML/CSS/JavaScript, Google Wallet API.

## Getting started

### Requirements

- Python 3.10+
- A Google Cloud project with the **Google Wallet API** enabled
- A Google Wallet issuer account and a service account with access to it

### Setup

```bash
git clone https://github.com/3omaroutlook/loyalty.git
cd loyalty
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/macOS: source .venv/bin/activate
pip install fastapi uvicorn google-auth requests
```

Copy `.env.example` to `.env` and fill in your own values. **Never commit your service
account key or your `.env` file.**

### Run

```bash
python setup_demo.py        # creates a demo cafe in the local database
uvicorn app:app --reload
```

Then open the pages served by the app (customer registration and cashier). Run the tests with
`pytest` (or `python test_db.py`).

## Project structure

```
app.py             web app (FastAPI): registration, card and cashier routes
db.py              database layer (customers, points, transactions)
wallet.py          Google Wallet API integration
add_stamp.py       script to add a stamp to a customer's card
setup_demo.py      creates a demo cafe for testing
demo.py            demo script for the full flow
templates/         HTML pages (register, card, cashier, cashier login)
index.html         landing page
test_app.py, test_db.py, wallet_test.py   tests
```

## Security and privacy

Customer names and phone numbers are collected only after explicit consent on the
registration page. Credentials are read from environment variables and are never stored in
the repository.

## Contributing

Issues and pull requests are welcome. This is an early project, so feel free to open an
issue with ideas or questions first.

## License

MIT, see [LICENSE](LICENSE).
