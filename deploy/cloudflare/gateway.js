// Worker ROUTES run ahead of the Tunnel origin. fetch(request) continues to DNS origin.
// Static frontend builds remain hosted in Cloudflare Pages.
export default {
 async fetch(request, env) {
  const url=new URL(request.url)
  const admin=url.origin===env.ADMIN_APP_ORIGIN
  if(!admin&&url.origin!==env.PUBLIC_APP_ORIGIN)return new Response('Unknown application',{status:404})
  const p=url.pathname
  const api=p.startsWith('/api/'),auth=p.startsWith('/auth/'),ws=p.startsWith('/ws/'),webhook=p==='/webhook/telegram'
  if(api||auth||ws||webhook){
   const allowed=admin
    ?p.startsWith('/api/v1/admin/')||p.startsWith('/api/v1/public/')||['/auth/google','/auth/callback/google','/auth/session','/auth/logout','/ws/admin','/webhook/telegram'].includes(p)
    :p.startsWith('/api/v1/public/')||p==='/ws/public'
   if(!allowed||(!admin&&!['GET','HEAD'].includes(request.method)))return new Response('Not found',{status:404})
   if(!env.ORIGIN_PROXY_SECRET)return new Response('Gateway is not configured',{status:503})
   if(ws&&request.headers.get('Upgrade')?.toLowerCase()!=='websocket')return new Response('WebSocket upgrade required',{status:426})
   const length=Number(request.headers.get('Content-Length')||0)
   if(length>65536)return new Response('Request too large',{status:413})
   const headers=new Headers(request.headers)
   headers.set('X-Origin-Verify',env.ORIGIN_PROXY_SECRET)
   headers.set('X-Forwarded-App-Host',url.host)
   headers.set('X-Visitor-IP',request.headers.get('CF-Connecting-IP')||'unknown')
   try{
    const response=await fetch(new Request(request,{headers,redirect:'manual'}))
    if(response.status===101)return response
    return secure(response,url,false)
   }catch{
    return secure(new Response(JSON.stringify({detail:'Backend connection unavailable'}),{status:503,headers:{'Content-Type':'application/json'}}),url,false)
   }
  }
  if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405})
  const pages=admin?env.ADMIN_PAGES_ORIGIN:env.PUBLIC_PAGES_ORIGIN
  if(!pages)return new Response('Pages origin is not configured',{status:503})
  const destination=new URL(url.pathname+url.search,pages)
  const headers=new Headers(request.headers)
  headers.delete('Cookie');headers.delete('Authorization');headers.delete('X-Origin-Verify')
  try{return secure(await fetch(new Request(destination,{method:request.method,headers,redirect:'manual'})),url,admin)}
  catch{return new Response('Frontend is temporarily unavailable',{status:503})}
 }
}
function secure(response,url,admin){
 const headers=new Headers(response.headers)
 headers.set('X-Content-Type-Options','nosniff')
 headers.set('Referrer-Policy','strict-origin-when-cross-origin')
 headers.set('X-Frame-Options','DENY')
 headers.set('Permissions-Policy','camera=(), microphone=(), geolocation=()')
 headers.set('Strict-Transport-Security','max-age=31536000')
 headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self' wss://"+url.host+"; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
 if(admin||url.pathname.startsWith('/api/')||url.pathname.startsWith('/auth/'))headers.set('Cache-Control','no-store')
 if(url.pathname==='/sw.js'){headers.set('Cache-Control','no-cache');headers.set('Service-Worker-Allowed','/')}
 return new Response(response.body,{status:response.status,statusText:response.statusText,headers})
}
