// Remove API caches created by previous application versions.
self.addEventListener('activate',event=>{
 event.waitUntil(Promise.all(['api-cache','google-fonts-cache'].map(name=>caches.delete(name))))
})
