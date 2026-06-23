"""Deploy NjangiLedger to Celo (Alfajores by default).

Usage:
    CELO_RPC_URL=https://alfajores-forno.celo-testnet.org \
    CELO_PRIVATE_KEY=0x... \
    python3 scripts/deploy.py

Requires the contract to already be compiled into build/NjangiLedger.json
(run `node scripts/compile.js` first). Prints the deployed contract address,
which should be set as CELO_LEDGER_CONTRACT_ADDRESS in the Django backend's
environment.
"""
import json
import os
import sys
from pathlib import Path

from eth_account import Account
from web3 import Web3

BUILD_PATH = Path(__file__).resolve().parent.parent / 'build' / 'NjangiLedger.json'


def main():
    rpc_url = os.environ.get('CELO_RPC_URL', 'https://alfajores-forno.celo-testnet.org')
    private_key = os.environ.get('CELO_PRIVATE_KEY')
    if not private_key:
        sys.exit('CELO_PRIVATE_KEY environment variable is required')

    artifact = json.loads(BUILD_PATH.read_text())

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = Account.from_key(private_key)
    print(f'Deploying from {account.address} via {rpc_url}')

    contract = w3.eth.contract(abi=artifact['abi'], bytecode=artifact['bytecode'])
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.constructor().build_transaction({
        'from': account.address,
        'nonce': nonce,
        'chainId': w3.eth.chain_id,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f'Deployment tx sent: {tx_hash.hex()}')

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f'Contract deployed at: {receipt.contractAddress}')
    print('Set CELO_LEDGER_CONTRACT_ADDRESS to this value in the Django backend .env')


if __name__ == '__main__':
    main()
