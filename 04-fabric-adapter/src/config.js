'use strict';

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const CCP_PATH = process.env.CCP_PATH || path.resolve(__dirname, '..', '..', '05-fabric-network', 'connection-profiles', 'connection-profile.yaml');
const ORG_BASE = process.env.ORG_BASE || path.resolve(__dirname, '..', '..', '05-fabric-network', 'organizations');
const CHANNEL_NAME = process.env.CHANNEL_NAME || 'auditchannel';
const CHAINCODE_NAME = process.env.CHAINCODE_NAME || 'audit-contract';
const PORT = parseInt(process.env.PORT || '8080', 10);
const MSP_ID = process.env.MSP_ID || 'Org1MSP';

function loadConnectionProfile() {
  const raw = fs.readFileSync(CCP_PATH, 'utf8');
  return yaml.load(raw);
}

function resolveTlsCertPath() {
  const ccp = loadConnectionProfile();
  const peerName = Object.keys(ccp.peers)[0];
  const peer = ccp.peers[peerName];
  const tlsRelPath = peer.tlsCACerts.path;
  const ccpDir = path.dirname(CCP_PATH);
  return path.resolve(ccpDir, tlsRelPath);
}

function findAdminIdentity() {
  const signCerts = path.join(ORG_BASE, 'peerOrganizations', 'org1.example.com', 'users', 'Admin@org1.example.com', 'msp', 'signcerts');
  const keystore = path.join(ORG_BASE, 'peerOrganizations', 'org1.example.com', 'users', 'Admin@org1.example.com', 'msp', 'keystore');
  if (!fs.existsSync(signCerts) || !fs.existsSync(keystore)) {
    return null;
  }
  const certFile = fs.readdirSync(signCerts).find(f => f.endsWith('.pem'));
  const keyFile = fs.readdirSync(keystore).find(f => f.startsWith('priv') || f.endsWith('_sk'));
  if (!certFile || !keyFile) return null;
  return {
    certPath: path.join(signCerts, certFile),
    keyPath: path.join(keystore, keyFile),
  };
}

function getPeerEndpoint() {
  const ccp = loadConnectionProfile();
  const peerName = Object.keys(ccp.peers)[0];
  const url = ccp.peers[peerName].url;
  return url.replace(/^grpcs?:\/\//, '');
}

module.exports = {
  CCP_PATH, ORG_BASE, CHANNEL_NAME, CHAINCODE_NAME, PORT, MSP_ID,
  loadConnectionProfile, resolveTlsCertPath, findAdminIdentity, getPeerEndpoint,
};
