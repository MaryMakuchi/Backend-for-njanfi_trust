# Njangi Ledger — Celo Smart Contract

This folder contains `NjangiLedger.sol`, an append-only on-chain ledger
contract used to anchor Njangi Trust transactions on the Celo blockchain
(Alfajores testnet by default).

## How it fits together

```
MTN MoMo confirms payment
        │
        ▼
Django webhook (payments/webhook/momo/)
        │  creates ledger.Transaction (status=completed)
        ▼
blockchain.services.record_on_chain()
        │
        ├─ BLOCKCHAIN_ENABLED=False  → simulated SHA-256 hash (status stays 'completed')
        │
        └─ BLOCKCHAIN_ENABLED=True   → calls NjangiLedger.recordTransaction() on Celo
                                         → status becomes 'verified', hash = real tx hash
        ▼
Notifications sent to the user + group members
        ▼
Flutter "Blockchain Ledger" screen shows the tx hash and a Celoscan link
```

The Django app works in **simulated mode** by default (`BLOCKCHAIN_ENABLED=False`),
so the rest of the product functions normally without any blockchain setup.
Follow the steps below to switch on real on-chain recording.

## 1. Backend signer wallet

A signer keypair was generated for this project:

- **Address:** `0x5aEdd9F7E9D69a9Ad6B9948796831f10E8ac3d50`
- **Private key:** stored only in your local `.env` (never commit it!) — see
  the session output where it was generated, or generate a new one:

  ```bash
  python3 -c "from eth_account import Account; a = Account.create(); print(a.address); print(a.key.hex())"
  ```

Fund this address with test CELO from the Alfajores faucet so it can pay gas
for `recordTransaction` calls:

https://faucet.celo.org/alfajores

## 2. Install dependencies & compile

```bash
cd blockchain_contracts
npm install
node scripts/compile.js   # writes build/NjangiLedger.json (ABI + bytecode)
```

`scripts/compile.js` uses the `solc` npm package directly (no native binary
download required), which is useful in network-restricted environments.
If you have unrestricted network access you can alternatively run
`npx hardhat compile`.

## 3. Deploy to Alfajores

```bash
CELO_RPC_URL=https://alfajores-forno.celo-testnet.org \
CELO_PRIVATE_KEY=<signer-private-key> \
python3 scripts/deploy.py
```

This prints the deployed contract address. Copy `build/NjangiLedger.json`
into the Django app if it changes:

```bash
cp build/NjangiLedger.json ../blockchain/contracts/NjangiLedger.json
```

(Already done for the current contract version.)

## 4. Configure the Django backend

Add to `Backend-for-njanfi_trust/.env`:

```env
BLOCKCHAIN_ENABLED=True
CELO_NETWORK=alfajores
CELO_RPC_URL=https://alfajores-forno.celo-testnet.org
CELO_PRIVATE_KEY=<signer-private-key>
CELO_LEDGER_CONTRACT_ADDRESS=<address-from-step-3>
CELO_EXPLORER_BASE_URL=https://alfajores.celoscan.io/tx/
```

Once set, every transaction created via `accounts.services.record_transaction`
or the contribution/loan/payment flows will be submitted to
`NjangiLedger.recordTransaction()` and the resulting Celo transaction hash
will be stored on the `Transaction.hash` field with `status='verified'`.

## 5. Mainnet

To move to Celo mainnet, redeploy the contract against the `celo` network in
`hardhat.config.js` (or `scripts/deploy.py` with
`CELO_RPC_URL=https://forno.celo.org`), then update:

```env
CELO_NETWORK=celo
CELO_RPC_URL=https://forno.celo.org
CELO_LEDGER_CONTRACT_ADDRESS=<mainnet-address>
CELO_EXPLORER_BASE_URL=https://celoscan.io/tx/
```

**Use a dedicated, funded mainnet wallet for `CELO_PRIVATE_KEY` and keep it
out of version control.**

## Contract overview

`NjangiLedger.sol`:

- `recordTransaction(bytes32 referenceId, address user, uint256 amount, TxType txType)`
  — owner-only; records one entry and emits `TransactionRecorded`.
  `referenceId` is the Njangi Trust `Transaction.id` (UUID) encoded as
  `bytes32`.
- `getEntry(uint256 index)`, `getEntryByReference(bytes32 referenceId)`,
  `isRecorded(bytes32 referenceId)`, `totalEntries()` — read-only views.
- `transferOwnership(address newOwner)` — owner-only.

## MTN MoMo webhook (stub)

`POST /api/v1/payments/webhook/momo/`, header `X-Momo-Signature: <MOMO_WEBHOOK_SECRET>`:

```json
{
  "reference_id": "ext-12345",
  "status": "SUCCESSFUL",
  "amount": "50000",
  "currency": "XAF",
  "payer_phone": "+237671111111",
  "external_id": "<njangi-user-uuid>",
  "purpose": "contribution",
  "group_id": "<group-uuid>"
}
```

`purpose` is either `contribution` (requires `group_id`) or `wallet_topup`.
On `SUCCESSFUL`, the view creates the Transaction, records it on-chain (or
simulates a hash), and notifies the payer + (for contributions) all other
group members. Replace the signature check and payload shape with MTN's real
Collections callback once sandbox credentials are available.
