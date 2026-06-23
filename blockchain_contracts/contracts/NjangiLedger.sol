// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title NjangiLedger
/// @notice Append-only on-chain record of Njangi Trust transactions.
/// Each entry mirrors a Transaction in the Django backend, identified by
/// its off-chain UUID, so the app can prove a transaction was recorded
/// on the Celo chain at a given time.
contract NjangiLedger {
    address public owner;

    enum TxType {
        Contribution,
        Payout,
        LoanDisbursement,
        LoanRepayment,
        SocialFund,
        WalletTopup,
        WalletWithdrawal,
        SavingsDeposit,
        SavingsWithdrawal
    }

    struct Entry {
        bytes32 referenceId; // off-chain Transaction UUID (as bytes32)
        address user;        // celo address representing the user (may be zero)
        uint256 amount;      // amount in smallest currency unit (e.g. cents)
        TxType txType;
        uint256 timestamp;
    }

    Entry[] private entries;
    mapping(bytes32 => uint256) private referenceIndex; // referenceId => entries index + 1 (0 = not found)

    event TransactionRecorded(
        bytes32 indexed referenceId,
        address indexed user,
        uint256 amount,
        TxType txType,
        uint256 timestamp,
        uint256 entryIndex
    );

    modifier onlyOwner() {
        require(msg.sender == owner, 'NjangiLedger: caller is not the owner');
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Record a transaction on-chain. Only the backend signer can call this.
    function recordTransaction(
        bytes32 referenceId,
        address user,
        uint256 amount,
        TxType txType
    ) external onlyOwner returns (uint256) {
        require(referenceIndex[referenceId] == 0, 'NjangiLedger: reference already recorded');

        entries.push(Entry({
            referenceId: referenceId,
            user: user,
            amount: amount,
            txType: txType,
            timestamp: block.timestamp
        }));

        uint256 index = entries.length - 1;
        referenceIndex[referenceId] = entries.length; // store index + 1

        emit TransactionRecorded(referenceId, user, amount, txType, block.timestamp, index);
        return index;
    }

    function totalEntries() external view returns (uint256) {
        return entries.length;
    }

    function getEntry(uint256 index) external view returns (Entry memory) {
        require(index < entries.length, 'NjangiLedger: index out of range');
        return entries[index];
    }

    function getEntryByReference(bytes32 referenceId) external view returns (Entry memory) {
        uint256 idx = referenceIndex[referenceId];
        require(idx != 0, 'NjangiLedger: reference not found');
        return entries[idx - 1];
    }

    function isRecorded(bytes32 referenceId) external view returns (bool) {
        return referenceIndex[referenceId] != 0;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), 'NjangiLedger: new owner is zero address');
        owner = newOwner;
    }
}
