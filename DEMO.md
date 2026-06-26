# Dissertation Demo Runbook

Run these in order. Each step must succeed before starting the next.

---

## Step 1 — Start Ganache

```bash
ganache --port 7545 --chainId 1337 --deterministic
```

Leave this terminal open. Copy the **private key of Account 0** — you need it in `.env` as `CELO_PRIVATE_KEY`.

---

## Step 2 — Deploy the Smart Contract (only if first run)

```bash
cd blockchain_contracts
truffle migrate --reset --network development
```

Copy the deployed `NjangiLedger` address from the output into `.env` as `CELO_LEDGER_CONTRACT_ADDRESS`.

---

## Step 3 — Start Django Backend

```bash
cd /path/to/Backend-for-njanfi_trust
pip install -r requirements.txt   # first time only
python manage.py migrate           # first time only
python manage.py runserver
```

Backend runs at **http://127.0.0.1:8000**

---

## Step 4 — Start Flutter Frontend

```bash
cd /path/to/Frontend-for-njangi_trust
flutter pub get   # first time only
flutter run -d chrome
```

Or run on your Android phone:

```bash
flutter run -d <device-id>
```

---

## Step 5 — Make a Test Contribution (triggers on-chain recording)

1. Log in as a member
2. Open a group → contribute
3. Go to **Blockchain Ledger** screen — confirm the transaction shows **On-chain** status and a `0x...` hash

---

## Step 6 — Live Jury Demo: Prove On-Chain (run this when asked)

```bash
cd blockchain_contracts
CELO_RPC_URL=http://127.0.0.1:7545 \
CELO_LEDGER_CONTRACT_ADDRESS=0x<your-contract-address> \
python3 scripts/verify_onchain.py
```

This reads **directly from the smart contract**, not from the Django database.
Every entry printed here is immutable proof.

**To verify a specific transaction hash:**

```bash
python3 scripts/verify_onchain.py 0x<txhash>
```

---

## Step 7 — Demonstrate Tamper Detection

1. Note a transaction hash from the Blockchain Ledger screen
2. Open Django admin → change that transaction's amount to a different value
3. Re-run `verify_onchain.py` — the on-chain entry still shows the **original amount**
4. The mismatch between database and chain is the tamper detection mechanism

---

## Key Facts to Say Confidently

| Question | Answer |
|---|---|
| Contract name | `NjangiLedger` |
| Function called | `recordTransaction()` |
| Business logic location | Django backend (Python) |
| Contract role | Append-only immutable notary |
| Money custodian | MTN MoMo (not the app) |
| Password hashing | PBKDF2 with SHA-256 (Django default) |
| Private key location | `.env` file, never committed to git |
| Celo vs Ganache | Ganache is local simulation; one RPC URL change deploys to Celo Alfajores |
| MRI active components | Payment punctuality + contribution consistency (50% weight combined) |
| Attendance component | Designed in; proxied by consistency in prototype; future work for full tracking |
