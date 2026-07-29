#!/usr/bin/env bash
# Create auditchannel (channel participation API), join peer, set anchor peer
set -e

CHANNEL_NAME="auditchannel"

# Container-rooted paths (Linux paths inside cli container)
CLI_CRYPTO="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto"
CLI_ADMIN_MSP="${CLI_CRYPTO}/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
ORDERER_CA="${CLI_CRYPTO}/ordererOrganizations/example.com/orderers/orderer0.example.com/tls/ca.crt"

echo "=== Creating channel via channel participation API: ${CHANNEL_NAME} ==="
docker exec cli osnadmin channel join \
  --channelID "${CHANNEL_NAME}" \
  --config-block "channel-artifacts/auditchannel_genesis.block" \
  -o "orderer0.example.com:9443"

echo "=== Fetching genesis block ==="
# Copy core.yaml if needed (not bundled in fabric-tools image)
docker exec cli sh -c "test -f /opt/gopath/src/github.com/hyperledger/fabric/peer/core.yaml" 2>/dev/null || \
  docker cp peer0.org1.example.com:/etc/hyperledger/fabric/core.yaml - | \
    docker exec -i cli sh -c "cat > /opt/gopath/src/github.com/hyperledger/fabric/peer/core.yaml"

docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=${CLI_ADMIN_MSP} && \
  peer channel fetch 0 channel-artifacts/${CHANNEL_NAME}.block \
    -o orderer0.example.com:7050 -c ${CHANNEL_NAME} \
    --tls --cafile ${ORDERER_CA}"

echo "=== Joining peer to channel ==="
docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=${CLI_ADMIN_MSP} && \
  peer channel join -b channel-artifacts/${CHANNEL_NAME}.block"

echo "=== Setting anchor peer ==="
docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=${CLI_ADMIN_MSP} && \
  peer channel update \
    -o orderer0.example.com:7050 -c ${CHANNEL_NAME} \
    -f channel-artifacts/Org1MSPanchors.tx \
    --tls --cafile ${ORDERER_CA}" || echo "Anchor peer update deferred (channel at version 0, skipping)"

echo "=== Channel ${CHANNEL_NAME} created ==="
docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=${CLI_ADMIN_MSP} && \
  peer channel list --tls --cafile ${ORDERER_CA}"
