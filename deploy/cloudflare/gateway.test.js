import test from 'node:test'
import assert from 'node:assert/strict'
import gateway from './gateway.js'
const env={PUBLIC_APP_ORIGIN:'https://app.vishalkool.top',ADMIN_APP_ORIGIN:'https://admin-app.vishalkool.top',PUBLIC_PAGES_ORIGIN:'https://public.pages.dev',ADMIN_PAGES_ORIGIN:'https://admin.pages.dev',ORIGIN_PROXY_SECRET:'test-proxy-secret'}
test('public host cannot reach operator APIs or mutate public data',async()=>{
 assert.equal((await gateway.fetch(new Request(env.PUBLIC_APP_ORIGIN+'/api/v1/admin/settings'),env)).status,404)
 assert.equal((await gateway.fetch(new Request(env.PUBLIC_APP_ORIGIN+'/api/v1/public/signals',{method:'POST'}),env)).status,404)
})
test('origin request replaces untrusted headers and keeps same hostname',async()=>{
 const previous=globalThis.fetch;let forwarded
 globalThis.fetch=async request=>{forwarded=request;return new Response('{}',{headers:{'Content-Type':'application/json'}})}
 try{
  const response=await gateway.fetch(new Request(env.ADMIN_APP_ORIGIN+'/api/v1/admin/settings',{headers:{'X-Origin-Verify':'forged','X-Forwarded-App-Host':'attacker','CF-Connecting-IP':'203.0.113.10'}}),env)
  assert.equal(forwarded.url,env.ADMIN_APP_ORIGIN+'/api/v1/admin/settings')
  assert.equal(forwarded.headers.get('X-Origin-Verify'),env.ORIGIN_PROXY_SECRET)
  assert.equal(forwarded.headers.get('X-Forwarded-App-Host'),'admin-app.vishalkool.top')
  assert.equal(response.headers.get('Cache-Control'),'no-store')
 }finally{globalThis.fetch=previous}
})
test('static requests select Pages build and strip operator cookies',async()=>{
 const previous=globalThis.fetch;let forwarded
 globalThis.fetch=async request=>{forwarded=request;return new Response('<html/>',{headers:{'Content-Type':'text/html'}})}
 try{
  const result=await gateway.fetch(new Request(env.ADMIN_APP_ORIGIN+'/research',{headers:{Cookie:'private-session'}}),env)
  assert.equal(forwarded.url,'https://admin.pages.dev/research')
  assert.equal(forwarded.headers.get('Cookie'),null)
  assert.equal(result.headers.get('X-Frame-Options'),'DENY')
 }finally{globalThis.fetch=previous}
})
test('websocket requests preserve the upgrade response',async()=>{
 const previous=globalThis.fetch;const upgrade={status:101,webSocket:{}}
 globalThis.fetch=async()=>upgrade
 try{assert.equal(await gateway.fetch(new Request(env.PUBLIC_APP_ORIGIN+'/ws/public',{headers:{Upgrade:'websocket'}}),env),upgrade)}
 finally{globalThis.fetch=previous}
})
test('missing secret fails closed',async()=>{
 assert.equal((await gateway.fetch(new Request(env.PUBLIC_APP_ORIGIN+'/api/v1/public/status'),{...env,ORIGIN_PROXY_SECRET:''})).status,503)
})
