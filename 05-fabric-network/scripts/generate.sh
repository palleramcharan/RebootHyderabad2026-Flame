#!/usr/bin/env bash
# Generate crypto material + genesis block + channel tx
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Generating crypto material ==="
docker run --rm \
  -v "${NETWORK_DIR}:/workspace" \
  -w /workspace \
  hyperledger/fabric-tools:2.5 \
  cryptogen generate \
    --config=./channel-artifacts/crypto-config.yaml \
    --output=./organizations

echo "=== Generating genesis block (RAFT) ==="
docker run --rm \
  -v "${NETWORK_DIR}:/workspace" \
  -w /workspace \
  hyperledger/fabric-tools:2.5 \
  configtxgen \
    -profile ChannelUsingRaft \
    -channelID auditchannel \
    -outputBlock ./channel-artifacts/genesis.block \
    -configPath ./channel-artifacts

echo "=== Generating channel creation tx ==="
docker run --rm \
  -v "${NETWORK_DIR}:/workspace" \
  -w /workspace \
  hyperledger/fabric-tools:2.5 \
  configtxgen \
    -profile ChannelUsingRaft \
    -channelID auditchannel \
    -outputCreateChannelTx ./channel-artifacts/auditchannel.tx \
    -configPath ./channel-artifacts

echo "=== Generating anchor peer update tx ==="
docker run --rm \
  -v "${NETWORK_DIR}:/workspace" \
  -w /workspace \
  hyperledger/fabric-tools:2.5 \
  configtxgen \
    -profile ChannelUsingRaft \
    -channelID auditchannel \
    -outputAnchorPeersUpdate ./channel-artifacts/Org1MSPanchors.tx \
    -asOrg Org1MSP \
    -configPath ./channel-artifacts

echo "=== Creating MSP config.yaml files ==="
cat > "${NETWORK_DIR}/organizations/peerOrganizations/org1.example.com/msp/config.yaml" << 'MSPEOF'
NodeOUs:
  Enable: true
  ClientOUIdentifier:
    Certificate: cacerts/ca.org1.example.com-cert.pem
    OrganizationalUnitIdentifier: client
  PeerOUIdentifier:
    Certificate: cacerts/ca.org1.example.com-cert.pem
    OrganizationalUnitIdentifier: peer
  AdminOUIdentifier:
    Certificate: cacerts/ca.org1.example.com-cert.pem
    OrganizationalUnitIdentifier: admin
  OrdererOUIdentifier:
    Certificate: cacerts/ca.org1.example.com-cert.pem
    OrganizationalUnitIdentifier: orderer
MSPEOF

cat > "${NETWORK_DIR}/organizations/ordererOrganizations/example.com/msp/config.yaml" << 'MSPEOF'
NodeOUs:
  Enable: true
  ClientOUIdentifier:
    Certificate: cacerts/ca.example.com-cert.pem
    OrganizationalUnitIdentifier: client
  PeerOUIdentifier:
    Certificate: cacerts/ca.example.com-cert.pem
    OrganizationalUnitIdentifier: peer
  AdminOUIdentifier:
    Certificate: cacerts/ca.example.com-cert.pem
    OrganizationalUnitIdentifier: admin
  OrdererOUIdentifier:
    Certificate: cacerts/ca.example.com-cert.pem
    OrganizationalUnitIdentifier: orderer
MSPEOF

echo "=== Copy admin cert to msp/admincerts (required by configtxgen with NodeOUs) ==="
cp "${NETWORK_DIR}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp/signcerts/Admin@org1.example.com-cert.pem" \
   "${NETWORK_DIR}/organizations/peerOrganizations/org1.example.com/msp/admincerts/"

echo "=== Generation complete ==="
echo "  organizations/  -- MSP and TLS certs + config.yaml"
echo "  genesis.block  -- RAFT genesis block"
echo "  auditchannel.tx -- channel creation tx"
