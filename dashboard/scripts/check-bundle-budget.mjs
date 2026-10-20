import { readdir, stat } from 'node:fs/promises'
import { join } from 'node:path'

const assetsDir = new URL('../dist/assets/', import.meta.url)
const files = await readdir(assetsDir)
const measured = []
for (const file of files.filter(name => /\.(js|css)$/.test(name))) {
  measured.push({ file, bytes: (await stat(join(assetsDir.pathname, file))).size })
}

if (!measured.length) throw new Error('No built JS/CSS assets found; run the production build first.')
const totalBytes = measured.reduce((sum, item) => sum + item.bytes, 0)
const largestJs = Math.max(0, ...measured.filter(item => item.file.endsWith('.js')).map(item => item.bytes))
const largestCss = Math.max(0, ...measured.filter(item => item.file.endsWith('.css')).map(item => item.bytes))
const mib = (value) => `${(value / 1024 / 1024).toFixed(2)} MiB`
console.log(`Frontend bundle: ${mib(totalBytes)} JS/CSS total; largest JS ${(largestJs / 1024).toFixed(0)} KiB; largest CSS ${(largestCss / 1024).toFixed(0)} KiB`)

const failures = []
if (totalBytes > 2.5 * 1024 * 1024) failures.push('total JS/CSS exceeds 2.5 MiB')
if (largestJs > 450 * 1024) failures.push('largest JS chunk exceeds 450 KiB')
if (largestCss > 160 * 1024) failures.push('largest CSS chunk exceeds 160 KiB')
if (failures.length) throw new Error(`Bundle budget exceeded: ${failures.join('; ')}`)
