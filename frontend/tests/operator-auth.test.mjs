import assert from 'node:assert/strict';
import { test } from 'node:test';
import { operatorAccess } from '../src/lib/operator-auth.ts';

const credentials = { username: 'operator', password: 'synthetic-private-password-for-tests' };
const authorization = `Basic ${Buffer.from(`${credentials.username}:${credentials.password}`).toString('base64')}`;

test('operator authentication fails closed for missing or weak configuration', () => {
  for (const config of [{}, { username: 'operator', password: 'short' }, { ...credentials, username: 'bad:user' }]) {
    const response = operatorAccess(new Request('http://localhost/runs'), config);
    assert.equal(response.status, 503);
    assert.equal(response.headers.get('cache-control'), 'no-store');
  }
});

test('pages and sensitive paths require valid Basic authentication', () => {
  for (const path of ['/', '/runs', '/settings', '/api/v1/runs', '/api/v1/policies', '/api/v1/runs/id/stt-review/audio', '/_next/static/test.js']) {
    for (const value of ['', 'Bearer synthetic', 'Basic !!!!', 'Basic Og==', `Basic ${Buffer.from('operator:wrong').toString('base64')}`]) {
      const response = operatorAccess(new Request(`https://private.example${path}`, { headers: { authorization: value } }), credentials);
      assert.equal(response.status, 401);
      assert.match(response.headers.get('www-authenticate'), /^Basic /);
      assert.equal(response.headers.get('cache-control'), 'no-store');
    }
    assert.equal(operatorAccess(new Request(`https://private.example${path}`, { headers: { authorization } }), credentials), null);
  }
});

test('Basic credentials require TLS except for loopback and reject cross-origin browser access', () => {
  assert.equal(operatorAccess(new Request('http://public.example/runs', { headers: { authorization } }), credentials).status, 403);
  assert.equal(operatorAccess(new Request('http://127.0.0.1/runs', { headers: { authorization } }), credentials), null);
  for (const headers of [{ authorization, origin: 'https://attacker.example' }, { authorization, 'sec-fetch-site': 'cross-site' }]) {
    assert.equal(operatorAccess(new Request('https://private.example/api/v1/analyze', { method: 'POST', headers }), credentials).status, 403);
  }
  assert.equal(operatorAccess(new Request('https://private.example/api/v1/analyze', { method: 'POST', headers: { authorization, origin: 'https://private.example' } }), credentials), null);
});

test('operator links and identity-provider redirects can navigate but cannot bypass authentication or allow frames', () => {
  const headers = { authorization, 'sec-fetch-site': 'cross-site', 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document' };
  assert.equal(operatorAccess(new Request('https://private.example/runs', { headers }), credentials), null);
  assert.equal(operatorAccess(new Request('https://private.example/runs', { headers: { ...headers, authorization: '' } }), credentials).status, 401);
  assert.equal(operatorAccess(new Request('https://private.example/api/v1/analyze', { method: 'POST', headers }), credentials).status, 403);
  assert.equal(operatorAccess(new Request('https://private.example/runs', { headers: { ...headers, 'sec-fetch-dest': 'iframe' } }), credentials).status, 403);
});


test('NextRequest preserves the exact browser loopback origin through normalization', async () => {
  const { NextRequest } = await import('next/server.js');
  for (const host of ['127.0.0.1:3089', 'localhost:3089', '[::1]:3089']) {
    const request = new NextRequest(`http://${host}/api/v1/policies/rules`, {
      method: 'POST', headers: { authorization, host, origin: `http://${host}` },
    });
    assert.equal(operatorAccess(request, credentials), null, host);
  }
  for (const origin of ['http://localhost:3089', 'http://127.0.0.1:3090', 'https://attacker.example', 'null']) {
    const request = new NextRequest('http://127.0.0.1:3089/api/v1/policies/rules', {
      method: 'POST', headers: { authorization, host: '127.0.0.1:3089', origin },
    });
    assert.equal(operatorAccess(request, credentials).status, 403, origin);
  }
  for (const host of ['attacker.example:3089', '127.0.0.1:3090', 'user@127.0.0.1:3089', '127.0.0.1:99999']) {
    const request = new NextRequest('http://127.0.0.1:3089/api/v1/policies/rules', {
      method: 'POST', headers: { authorization, host, origin: 'http://127.0.0.1:3089' },
    });
    assert.equal(operatorAccess(request, credentials).status, 403, host);
  }
});
