require('@nomicfoundation/hardhat-toolbox');
require('dotenv').config();

const PRIVATE_KEY = process.env.CELO_PRIVATE_KEY || '';

module.exports = {
  solidity: '0.8.24',
  networks: {
    alfajores: {
      url: process.env.CELO_RPC_URL || 'https://alfajores-forno.celo-testnet.org',
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
      chainId: 44787,
    },
    celo: {
      url: process.env.CELO_MAINNET_RPC_URL || 'https://forno.celo.org',
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
      chainId: 42220,
    },
  },
};
