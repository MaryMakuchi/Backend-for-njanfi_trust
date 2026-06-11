// Standalone compiler that does not require downloading a native solc
// binary (useful in network-restricted environments). Uses the solc npm
// package (solcjs) directly and writes ABI + bytecode to build/NjangiLedger.json.
const fs = require('fs');
const path = require('path');
const solc = require('solc');

const contractPath = path.join(__dirname, '..', 'contracts', 'NjangiLedger.sol');
const source = fs.readFileSync(contractPath, 'utf8');

const input = {
  language: 'Solidity',
  sources: {
    'NjangiLedger.sol': { content: source },
  },
  settings: {
    outputSelection: {
      '*': { '*': ['abi', 'evm.bytecode.object'] },
    },
  },
};

const output = JSON.parse(solc.compile(JSON.stringify(input)));

if (output.errors) {
  const fatal = output.errors.filter((e) => e.severity === 'error');
  output.errors.forEach((e) => console.error(e.formattedMessage));
  if (fatal.length) process.exit(1);
}

const contract = output.contracts['NjangiLedger.sol']['NjangiLedger'];

const buildDir = path.join(__dirname, '..', 'build');
fs.mkdirSync(buildDir, { recursive: true });
fs.writeFileSync(
  path.join(buildDir, 'NjangiLedger.json'),
  JSON.stringify(
    {
      abi: contract.abi,
      bytecode: '0x' + contract.evm.bytecode.object,
    },
    null,
    2,
  ),
);

console.log('Compiled NjangiLedger -> build/NjangiLedger.json');
