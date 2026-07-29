#!/usr/bin/env bash
# Deploy a chaincode package to auditchannel
# Usage: ./deploy-chaincode.sh <chaincode-name> <chaincode-path> <version> [lang]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"
CHANNEL_NAME="auditchannel"

CC_NAME="${1:?chaincode name required}"
CC_PATH="${2:?chaincode path required}"
CC_VERSION="${3:-1.0}"
CC_LANG="${4:-node}"
CC_SEQUENCE="${5:-1}"
LABEL="${CC_NAME}_${CC_VERSION}"

# Container-rooted paths (Linux paths inside cli container)
CLI_CRYPTO="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto"
ORDERER_CA="${CLI_CRYPTO}/ordererOrganizations/example.com/orderers/orderer0.example.com/tls/ca.crt"
PEER_TLSROOTCERT="${CLI_CRYPTO}/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
ORDERER_ADDRESS="orderer0.example.com:7050"

echo "=== Deploying ${CC_NAME} v${CC_VERSION} (${CC_LANG}) ==="

# Ensure core.yaml is available in CLI container (not bundled in fabric-tools image)
docker exec cli sh -c "test -f /opt/gopath/src/github.com/hyperledger/fabric/peer/core.yaml" 2>/dev/null ||
  docker cp peer0.org1.example.com:/etc/hyperledger/fabric/core.yaml \
    - | docker exec -i cli sh -c "cat > /opt/gopath/src/github.com/hyperledger/fabric/peer/core.yaml"

echo "Packaging chaincode..."
docker exec cli peer lifecycle chaincode package "${CC_NAME}.tar.gz" \
  --path "${CC_PATH}" \
  --lang "${CC_LANG}" \
  --label "${LABEL}"

echo "Installing chaincode..."
docker exec cli peer lifecycle chaincode install "${CC_NAME}.tar.gz"

echo "Querying installed chaincode..."
PACKAGE_ID=$(docker exec cli peer lifecycle chaincode queryinstalled 2>&1 | \
  grep "${LABEL}" | \
  sed -n "s/.*Package ID: //; s/, Label:.*//p")
echo "Package ID: ${PACKAGE_ID}"

echo "Approving chaincode for Org1..."
docker exec cli peer lifecycle chaincode approveformyorg \
  -o "${ORDERER_ADDRESS}" \
  --tls --cafile "${ORDERER_CA}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --package-id "${PACKAGE_ID}" \
  --sequence "${CC_SEQUENCE}" \
  --signature-policy "OR('Org1MSP.member')"

echo "Checking commit readiness..."
docker exec cli peer lifecycle chaincode checkcommitreadiness \
  -o "${ORDERER_ADDRESS}" \
  --tls --cafile "${ORDERER_CA}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --sequence "${CC_SEQUENCE}" \
  --signature-policy "OR('Org1MSP.member')"

echo "Committing chaincode to channel..."
docker exec cli peer lifecycle chaincode commit \
  -o "${ORDERER_ADDRESS}" \
  --tls --cafile "${ORDERER_CA}" \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --sequence "${CC_SEQUENCE}" \
  --signature-policy "OR('Org1MSP.member')" \
  --peerAddresses peer0.org1.example.com:7051 \
  --tlsRootCertFiles "${PEER_TLSROOTCERT}"

echo "=== Chaincode ${CC_NAME} v${CC_VERSION} deployed ==="
echo "Channel: ${CHANNEL_NAME}, Lang: ${CC_LANG}"
