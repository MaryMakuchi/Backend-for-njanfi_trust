"""Celo blockchain integration for the Njangi ledger.

When ``BLOCKCHAIN_ENABLED`` is true (and the RPC/contract are reachable),
``record_on_chain`` submits a transaction to the deployed ``NjangiLedger``
smart contract on Celo and returns the resulting on-chain transaction hash.

When disabled (the default until a contract is deployed and funded), a
deterministic SHA-256 "simulated" hash is returned instead, keeping the rest
of the application working exactly as before.
"""
import hashlib
import json
import logging
import uuid
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

CONTRACT_ARTIFACT_PATH = Path(__file__).resolve().parent / 'contracts' / 'NjangiLedger.json'

# Order must match the `enum TxType` declared in NjangiLedger.sol
TX_TYPE_ENUM = {
    'contribution': 0,
    'payout': 1,
    'loan_disbursement': 2,
    'loan_repayment': 3,
    'social_fund': 4,
    'wallet_topup': 5,
    'wallet_withdrawal': 6,
    'savings_deposit': 7,
    'savings_withdrawal': 8,
}


def simulated_hash(transaction):
    """Deterministic placeholder hash used when on-chain recording is disabled."""
    raw = f'{transaction.id}{transaction.amount}{transaction.created_at.isoformat()}'
    return '0x' + hashlib.sha256(raw.encode()).hexdigest()


class CeloService:
    """Thin wrapper around web3.py for the NjangiLedger contract."""

    _instance = None

    def __init__(self):
        self._w3 = None
        self._contract = None
        self._account = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_configured(self):
        return bool(
            settings.BLOCKCHAIN_ENABLED
            and settings.CELO_PRIVATE_KEY
            and settings.CELO_LEDGER_CONTRACT_ADDRESS
        )

    def _connect(self):
        if self._w3 is not None:
            return
        from eth_account import Account
        from web3 import Web3

        self._w3 = Web3(Web3.HTTPProvider(settings.CELO_RPC_URL))
        self._account = Account.from_key(settings.CELO_PRIVATE_KEY)

        artifact = json.loads(CONTRACT_ARTIFACT_PATH.read_text())
        self._contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(settings.CELO_LEDGER_CONTRACT_ADDRESS),
            abi=artifact['abi'],
        )

    def record_transaction(self, transaction):
        """Submit `transaction` to the NjangiLedger contract.

        Returns the on-chain transaction hash (hex string) on success, or
        ``None`` if the call fails for any reason (caller should fall back
        to `simulated_hash`).
        """
        if not self.is_configured:
            return None

        try:
            self._connect()
            from web3 import Web3

            reference_id = Web3.to_bytes(hexstr='0x' + uuid.UUID(str(transaction.id)).hex)
            user_address = getattr(transaction.user, 'celo_address', '') or '0x' + '00' * 20
            tx_type = TX_TYPE_ENUM.get(transaction.transaction_type, 0)
            amount = int(transaction.amount * 100)  # store as smallest unit (cents)

            nonce = self._w3.eth.get_transaction_count(self._account.address)
            tx = self._contract.functions.recordTransaction(
                reference_id,
                Web3.to_checksum_address(user_address),
                amount,
                tx_type,
            ).build_transaction({
                'from': self._account.address,
                'nonce': nonce,
                'chainId': self._w3.eth.chain_id,
            })
            signed = self._account.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return tx_hash.hex()
        except Exception:
            logger.exception('Failed to record transaction %s on-chain', transaction.id)
            return None


def record_on_chain(transaction):
    """Record `transaction` on-chain if enabled, else return a simulated hash.

    Always returns a hash string suitable for storage in
    ``Transaction.hash`` and updates `transaction.status` to ``'verified'``
    when the on-chain call succeeds.
    """
    tx_hash = CeloService.instance().record_transaction(transaction)
    if tx_hash:
        # web3.py's `.hex()` may return the hash without a leading '0x' and
        # at 64 chars; normalise to the canonical 0x-prefixed 66-char form so
        # the API's on_chain check (0x prefix + length 66) recognises it.
        if not tx_hash.startswith('0x'):
            tx_hash = '0x' + tx_hash
        transaction.status = 'verified'
        transaction.hash = tx_hash
    else:
        transaction.hash = transaction.hash or simulated_hash(transaction)
    return transaction.hash
