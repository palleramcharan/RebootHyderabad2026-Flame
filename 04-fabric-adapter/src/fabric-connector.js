'use strict';

const grpc = require('@grpc/grpc-js');
const crypto = require('crypto');
const fs = require('fs');
const { connect, signers } = require('@hyperledger/fabric-gateway');
const config = require('./config');

class FabricChaincode {
  constructor() {
    this.gateway = null;
    this.network = null;
    this.contract = null;
  }

  _decode(result) {
    if (result == null) return '';
    return Buffer.from(result).toString('utf8');
  }

  async connect() {
    const peerEndpoint = config.getPeerEndpoint();
    const tlsCertPath = config.resolveTlsCertPath();
    const identityInfo = config.findAdminIdentity();
    if (!identityInfo) {
      throw new Error('Admin identity not found in ORG_BASE. Run cryptogen first.');
    }

    console.log('Connecting to peer:', peerEndpoint);
    console.log('TLS cert path:', tlsCertPath);
    console.log('Identity cert path:', identityInfo.certPath);
    console.log('Identity key path:', identityInfo.keyPath);

    const rootCert = fs.readFileSync(tlsCertPath);
    const client = new grpc.Client(
      peerEndpoint,
      grpc.credentials.createSsl(rootCert),
      { 'grpc.ssl_target_name_override': 'peer0.org1.example.com' }
    );

    const certPem = fs.readFileSync(identityInfo.certPath, 'utf8');
    const keyPem = fs.readFileSync(identityInfo.keyPath, 'utf8');
    const privateKey = crypto.createPrivateKey(keyPem);
    const signer = signers.newPrivateKeySigner(privateKey);
    const identity = { mspId: config.MSP_ID, credentials: Buffer.from(certPem) };

    console.log('Creating gateway...');
    this.gateway = connect({ client, identity, signer });
    console.log('Getting network...');
    this.network = this.gateway.getNetwork(config.CHANNEL_NAME);
    console.log('Getting contract...');
    this.contract = this.network.getContract(config.CHAINCODE_NAME);
    console.log('Connected successfully');
  }

  async close() {
    if (this.gateway) {
      this.gateway.close();
      this.gateway = null;
      this.network = null;
      this.contract = null;
    }
  }

  async submit(fn, ...args) {
    if (!this.contract) await this.connect();
    const result = await this.contract.submitTransaction(fn, ...args);
    return JSON.parse(this._decode(result));
  }

  async evaluate(fn, ...args) {
    if (!this.contract) await this.connect();
    const result = await this.contract.evaluateTransaction(fn, ...args);
    return JSON.parse(this._decode(result));
  }

  async CreateAuditEvent(auditEventJson) { return this.submit('CreateAuditEvent', auditEventJson); }
  async ReadAuditEvent(eventKey) { return this.evaluate('ReadAuditEvent', eventKey); }
  async GetAllAuditEvents() { return this.evaluate('GetAllAuditEvents'); }
  async GetApplicationAuditHistory(applicationId) { return this.evaluate('GetApplicationAuditHistory', applicationId); }
  async GetApplicationTimeline(applicationId) { return this.evaluate('GetApplicationTimeline', applicationId); }
  async GetFieldChangeHistory(applicationId) { return this.evaluate('GetFieldChangeHistory', applicationId); }
  async GetEventsByApplication(applicationId) { return this.evaluate('GetEventsByApplication', applicationId); }
  async GetEventsByService(service) { return this.evaluate('GetEventsByService', service); }
  async GetEventsByUser(userId) { return this.evaluate('GetEventsByUser', userId); }
  async GetEventsByDate(startDate, endDate) { return this.evaluate('GetEventsByDate', startDate, endDate); }
  async GetEventsByCorrelationId(correlationId) { return this.evaluate('GetEventsByCorrelationId', correlationId); }
  async VerifyEvidence(eventKey, expectedEvidenceHash) { return this.evaluate('VerifyEvidence', eventKey, expectedEvidenceHash); }
  async VerifyAuditHashChain(applicationId) { return this.evaluate('VerifyAuditHashChain', applicationId); }
  async VerifyBlockchainIntegrity(applicationId) { return this.evaluate('VerifyBlockchainIntegrity', applicationId); }
  async GetCurrentApplicationState(applicationId) { return this.evaluate('GetCurrentApplicationState', applicationId); }
  async GetAuditStatistics() { return this.evaluate('GetAuditStatistics'); }
  async GetBlockMetadata(blockNumber) { return this.evaluate('GetBlockMetadata', String(blockNumber)); }
  async GetTransactionMetadata(transactionId) { return this.evaluate('GetTransactionMetadata', transactionId); }

  async isNetworkReady() {
    try {
      if (!this.contract) await this.connect();
      await this.contract.evaluateTransaction('GetAllAuditEvents');
      return true;
    } catch (err) {
      return false;
    }
  }
}

module.exports = FabricChaincode;
