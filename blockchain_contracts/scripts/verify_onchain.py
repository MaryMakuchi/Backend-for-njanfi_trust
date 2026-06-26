"""Verify Njangi transactions are truly stored on-chain.

Reads directly from the deployed NjangiLedger contract (NOT Django's
database) and prints every entry. Use this in front of the jury to prove
the hashes correspond to real on-chain records.

Usage:
    CELO_RPC_URL=http://127.0.0.1:7545 \
    CELO_LEDGER_CONTRACT_ADDRESS=0x... \
    python3 scripts/verify_onchain.py

Optionally pass a transaction hash to look up its receipt:
    ... python3 scripts/verify_onchain.py 0x<txhash>
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from web3 import Web3

ARTIFACT = Path(__file__).resolve().parent.parent / 'build' / 'NjangiLedger.json'

TX_TYPE_NAMES = [
    'Contribution', 'Payout', 'LoanDisbursement', 'LoanRepayment',
    'SocialFund', 'WalletTopup', 'WalletWithdrawal',
    'SavingsDeposit', 'SavingsWithdrawal',
]


def main():
    rpc_url = os.environ.get('CELO_RPC_URL', 'http://127.0.0.1:7545')
    address = os.environ.get('CELO_LEDGER_CONTRACT_ADDRESS')
    if not address:
        sys.exit('CELO_LEDGER_CONTRACT_ADDRESS environment variable is required')

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    print(f'Connected to {rpc_url} (chainId={w3.eth.chain_id})')
    print(f'Reading NjangiLedger contract at {address}\n')

    artifact = json.loads(ARTIFACT.read_text())
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=artifact['abi'],
    )

    # If a tx hash was supplied, show its on-chain receipt.
    if len(sys.argv) > 1:
        tx_hash = sys.argv[1]
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        print('--- Transaction receipt (proof this hash is on-chain) ---')
        print(f'  blockNumber: {receipt.blockNumber}')
        print(f'  from:        {receipt["from"]}')
        print(f'  to:          {receipt.to}')
        print(f'  gasUsed:     {receipt.gasUsed}')
        print(f'  status:      {"SUCCESS" if receipt.status == 1 else "FAILED"}\n')

    total = contract.functions.totalEntries().call()
    print(f'Total entries recorded on-chain: {total}\n')

    for i in range(total):
        entry = contract.functions.getEntry(i).call()
        reference_id, user, amount, tx_type, timestamp = entry
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%d %b %Y %H:%M:%S UTC')
        print(f'  Entry #{i}')
        print(f'    type:        {TX_TYPE_NAMES[tx_type]}')
        print(f'    amount:      {amount / 100:,.0f} CFA')
        print(f'    recorded at: {dt}')
        print(f'    tx hash:     0x{reference_id.hex()[:16]}...')
        print()


if __name__ == '__main__':
    main()
