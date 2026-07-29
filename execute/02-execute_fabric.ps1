Write-Host "============================================"
Write-Host "  Step 0: Start Fabric network (if not running)"
Write-Host "============================================"
$peer = docker ps --filter "name=peer0.org1.example.com" --format "{{.Names}}" 2>$null
if (-not $peer) {
  Write-Host "Fabric network not running. Starting it now..."
  $rootDir = "$([System.IO.Path]::GetFullPath("$PSScriptRoot\.."))"
  $netDir = "$rootDir\05-fabric-network"

  Write-Host "Running crypto generation (docker run cryptogen)..."
  Push-Location $netDir
  docker run --rm -v "${netDir}:/workspace" -w /workspace hyperledger/fabric-tools:2.5 cryptogen generate --config=./channel-artifacts/crypto-config.yaml --output=./organizations
  if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "ERROR: cryptogen failed."; exit 1 }

  Write-Host "Creating MSP config.yaml..."
@"
NodeOUs:
  Enable: false
"@ | Set-Content -Path "$netDir/organizations/peerOrganizations/org1.example.com/msp/config.yaml"

@"
NodeOUs:
  Enable: false
"@ | Set-Content -Path "$netDir/organizations/ordererOrganizations/example.com/msp/config.yaml"

  Copy-Item "$netDir/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp/signcerts/Admin@org1.example.com-cert.pem" "$netDir/organizations/peerOrganizations/org1.example.com/msp/admincerts/" -Force

  # Also copy orderer admin cert to its admincerts directory
  $ordererAdminCertDir = "$netDir/organizations/ordererOrganizations/example.com/msp/admincerts"
  if (-not (Test-Path $ordererAdminCertDir)) { New-Item -ItemType Directory -Path $ordererAdminCertDir -Force | Out-Null }
  Copy-Item "$netDir/organizations/ordererOrganizations/example.com/users/Admin@example.com/msp/signcerts/Admin@example.com-cert.pem" "$ordererAdminCertDir/" -Force

  Write-Host "Generating channel genesis block..."
  docker run --rm -v "${netDir}:/workspace" -w /workspace hyperledger/fabric-tools:2.5 configtxgen -profile ChannelUsingRaft -channelID auditchannel -outputBlock ./channel-artifacts/auditchannel_genesis.block -configPath ./channel-artifacts
  if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "ERROR: genesis block failed."; exit 1 }

  Write-Host "Starting core Fabric containers (excluding adapter)..."
  docker compose up -d ca-org1 orderer0 peer0.org1.example.com couchdb0 cli
  if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "ERROR: docker compose up failed."; exit 1 }
  Pop-Location
  Write-Host "Waiting for all containers to be healthy..."
  $containers = @("orderer0.example.com", "peer0.org1.example.com", "ca-org1")
  for ($i = 0; $i -lt 20; $i++) {
    $allHealthy = $true
    foreach ($c in $containers) {
      $s = docker inspect $c --format "{{.State.Health.Status}}" 2>$null
      if ($s -ne "healthy") { $allHealthy = $false; Write-Host "... $c = $s" }
    }
    if ($allHealthy) { Write-Host "All containers healthy!"; break }
    Start-Sleep -Seconds 3
  }
  if (-not $allHealthy) { Pop-Location; Write-Host "ERROR: containers not healthy in time."; exit 1 }

  Write-Host "Adding channel to orderer via osnadmin (channel participation API)..."
  Push-Location $netDir
  docker exec cli osnadmin channel join --channelID auditchannel --config-block ./channel-artifacts/auditchannel_genesis.block -o orderer0.example.com:9443
  if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "ERROR: osnadmin channel join failed."; exit 1 }
  # Copy core.yaml from peer to CLI if missing
  docker exec cli sh -c "test -f /opt/gopath/src/github.com/hyperledger/fabric/peer/core.yaml" 2>$null
  if ($LASTEXITCODE -ne 0) {
    docker cp peer0.org1.example.com:/etc/hyperledger/fabric/core.yaml "$netDir/core.yaml"
    docker cp "$netDir/core.yaml" cli:/opt/gopath/src/github.com/hyperledger/fabric/peer/core.yaml
    Remove-Item "$netDir/core.yaml"
  }
  # Fetch genesis block from orderer and join peer
  $cafile = "/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/example.com/orderers/orderer0.example.com/tls/ca.crt"
  docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp && peer channel fetch 0 auditchannel.block -c auditchannel -o orderer0.example.com:7050 --tls --cafile $cafile"
  if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "ERROR: peer channel fetch failed."; exit 1 }
  docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp && peer channel join -b auditchannel.block"
  if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "ERROR: peer join failed."; exit 1 }
  Pop-Location

  Write-Host "Deploying chaincode..."
  Push-Location $netDir
  docker exec cli mkdir -p /opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode/audit-contract/lib/models 2>$null
  $chaincodeDir = "$([System.IO.Path]::GetFullPath("$PSScriptRoot\..\06-chaincode\audit-contract"))"
  docker cp "$chaincodeDir\." cli:/opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode/audit-contract/
  docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp && peer lifecycle chaincode package cc.tar.gz --path /opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode/audit-contract --lang node --label audit-contract_1.0 && peer lifecycle chaincode install cc.tar.gz"
  $pkgId = docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp && peer lifecycle chaincode queryinstalled 2>&1" | Select-String "Package ID:" | ForEach-Object { $_.ToString().Trim().Split(' ')[2].Trim(',') }
  Write-Host "Package ID: $pkgId"
  docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp && peer lifecycle chaincode approveformyorg -o orderer0.example.com:7050 --channelID auditchannel --name audit-contract --version 1.0 --package-id '$pkgId' --sequence 1 --tls --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/example.com/orderers/orderer0.example.com/tls/ca.crt"
  docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp && peer lifecycle chaincode checkcommitreadiness -o orderer0.example.com:7050 --channelID auditchannel --name audit-contract --version 1.0 --sequence 1 --tls --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/example.com/orderers/orderer0.example.com/tls/ca.crt"
  docker exec cli sh -c "export CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp && peer lifecycle chaincode commit -o orderer0.example.com:7050 --channelID auditchannel --name audit-contract --version 1.0 --sequence 1 --tls --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/example.com/orderers/orderer0.example.com/tls/ca.crt"

  Write-Host "Starting Fabric Adapter..."
  docker compose up -d fabric-adapter
  Pop-Location
  Write-Host "Waiting for Fabric Adapter to be ready..."
  $adapterReady = $false
  for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    try { $null = Invoke-WebRequest -Uri http://localhost:8080/health/live -UseBasicParsing -ErrorAction Stop; $adapterReady = $true; break }
    catch { }
  }
  if (-not $adapterReady) { Write-Host "ERROR: Fabric Adapter not reachable after 30s."; exit 1 }
  Write-Host "Fabric Adapter ready."
  Write-Host "Fabric network and adapter started."
} else {
  Write-Host "Fabric network already running."
}

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 1: Start MongoDB (if not running)"
Write-Host "============================================"
$mongo = docker ps --filter "name=^mongodb$" --format "{{.Names}}" 2>$null
if ($mongo) {
  Write-Host "MongoDB already running."
} else {
  Write-Host "Starting MongoDB container..."
  docker rm mongodb 2>$null
  docker run -d --name mongodb -p 27017:27017 mongo:7
}

Write-Host ""
Write-Host "  Waiting for Fabric Adapter on http://localhost:8080 ..."
$adapterReady = $false
for ($i = 0; $i -lt 15; $i++) {
  Start-Sleep -Seconds 2
  try { $null = Invoke-WebRequest -Uri http://localhost:8080/health/live -UseBasicParsing -ErrorAction Stop; $adapterReady = $true; break }
  catch { Write-Host "  ... attempt $($i+1): not ready yet" }
}
if (-not $adapterReady) { Write-Host "ERROR: Fabric Adapter not reachable."; exit 1 }
Write-Host "Fabric Adapter is ready."

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 3: Copy chaincode to CLI container"
Write-Host "============================================"
$rootDir = "$([System.IO.Path]::GetFullPath("$PSScriptRoot\.."))"
docker exec cli mkdir -p /opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode/audit-contract/lib/models 2>$null
docker cp "$rootDir\06-chaincode\audit-contract\." cli:/opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode/audit-contract/
Write-Host "Chaincode copied."

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 4: Seed transaction queue from existing submissions"
Write-Host "============================================"
$rootDir = "$([System.IO.Path]::GetFullPath("$PSScriptRoot\.."))"
& "$rootDir\.venv\Scripts\python" "$rootDir\scripts\enqueue_submissions.py"

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 5: Process queue items"
Write-Host "============================================"
$env:ADAPTER_URL = "http://localhost:8080"

$maxAttempts = 10
$totalProcessed = 0

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
  Write-Host ""
  Write-Host "--- Batch attempt $attempt ---"
  $output = & "$rootDir\.venv\Scripts\python" "$rootDir\02-transaction-orchestrator\app\worker.py" --once 2>&1
  $outputText = ($output | Out-String)
  Write-Host "$outputText"

  if ($outputText -match "processed=(\d+)") {
    $processed = [int]$matches[1]
    if ($processed -eq 0) {
      Write-Host "No more items to process. Done."
      break
    }
    $totalProcessed += $processed
  } else {
    Write-Host "No more items to process. Done."
    break
  }
  Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Total processed across all batches: $totalProcessed"

Write-Host ""
Write-Host "============================================"
Write-Host "  Step 6: Verify events on Fabric Adapter"
Write-Host "============================================"
$events = Invoke-RestMethod -Uri http://localhost:8080/audit/events -UseBasicParsing
Write-Host "$($events.Count) audit event(s) on Fabric ledger:"
foreach ($e in $events) {
  Write-Host "  $($e.eventKey)  |  $($e.service)  |  $($e.eventType)"
}

Write-Host ""
Write-Host "=== Fabric execution complete ==="
