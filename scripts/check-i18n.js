#!/usr/bin/env node
/**
 * Translation key completeness checker.
 *
 * Scans .tsx/.ts frontend source files and both locale files, then reports:
 * 1. Keys used in source but missing from locale files
 * 2. Keys defined in one locale but missing from the other
 * 3. Keys defined in locales but unused in source (dead keys)
 *
 * Usage: node scripts/check-i18n.js
 */

const fs = require('fs')
const path = require('path')

const FRONTEND_SRC = path.resolve(__dirname, '..', 'frontend', 'src')
const ZH_FILE = path.join(FRONTEND_SRC, 'i18n', 'locales', 'zh-CN.ts')
const EN_FILE = path.join(FRONTEND_SRC, 'i18n', 'locales', 'en-US.ts')

/** Extract translation keys from a locale TS file. */
function extractLocaleKeys(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8')
  const re = /'([a-zA-Z0-9_.]+)':/g
  const keys = new Set()
  let match
  while ((match = re.exec(content)) !== null) {
    keys.add(match[1])
  }
  return { keys, content }
}

/** Extract t('...') and t("...") keys from source files. */
function extractSourceKeys(dir) {
  const keys = new Set()
  const re = /[^a-zA-Z]t\(["']([^"']+)["']\)/g

  function walk(d) {
    const entries = fs.readdirSync(d, { withFileTypes: true })
    for (const e of entries) {
      const full = path.join(d, e.name)
      if (e.isDirectory() && !e.name.startsWith('.') && e.name !== 'node_modules') {
        walk(full)
      } else if (e.isFile() && /\.(tsx|ts)$/.test(e.name)) {
        const content = fs.readFileSync(full, 'utf-8')
        let m
        while ((m = re.exec(content)) !== null) {
          keys.add(m[1])
        }
      }
    }
  }

  walk(dir)
  return keys
}

// ── Main ────────────────────────────────────────────────────────

const zh = extractLocaleKeys(ZH_FILE)
const en = extractLocaleKeys(EN_FILE)
const sourceKeys = extractSourceKeys(FRONTEND_SRC)

let exitCode = 0

// 1. Source → locale missing
const zhMissing = [...sourceKeys].filter(k => !zh.keys.has(k))
const enMissing = [...sourceKeys].filter(k => !en.keys.has(k))

if (zhMissing.length > 0) {
  console.log(`\n❌ Missing in zh-CN (${zhMissing.length}):`)
  zhMissing.forEach(k => console.log(`   '${k}'`))
  exitCode = 1
}

if (enMissing.length > 0) {
  console.log(`\n❌ Missing in en-US (${enMissing.length}):`)
  enMissing.forEach(k => console.log(`   '${k}'`))
  exitCode = 1
}

// 2. Asymmetric between locales
const onlyZh = [...zh.keys].filter(k => !en.keys.has(k))
const onlyEn = [...en.keys].filter(k => !zh.keys.has(k))

if (onlyZh.length > 0) {
  console.log(`\n⚠️  Only in zh-CN (${onlyZh.length}):`)
  onlyZh.forEach(k => console.log(`   '${k}'`))
  exitCode = 1
}

if (onlyEn.length > 0) {
  console.log(`\n⚠️  Only in en-US (${onlyEn.length}):`)
  onlyEn.forEach(k => console.log(`   '${k}'`))
  exitCode = 1
}

// 3. Dead keys (in locale but not in source)
const deadZh = [...zh.keys].filter(k => !sourceKeys.has(k) && !k.startsWith('wizard.field.') && !k.startsWith('wizard.option.') && !k.startsWith('wizard.help.') && !k.startsWith('template.arch.') && !k.startsWith('template.step.') && !k.startsWith('cluster.syncModule.'))
const deadEn = [...en.keys].filter(k => !sourceKeys.has(k) && !k.startsWith('wizard.field.') && !k.startsWith('wizard.option.') && !k.startsWith('wizard.help.') && !k.startsWith('template.arch.') && !k.startsWith('template.step.') && !k.startsWith('cluster.syncModule.'))

// Dead keys are informational, don't fail the build
if (deadZh.length > 0) {
  console.log(`\n💤 Potentially unused in zh-CN (${deadZh.length}):`)
  deadZh.slice(0, 10).forEach(k => console.log(`   '${k}'`))
  if (deadZh.length > 10) console.log(`   ... and ${deadZh.length - 10} more`)
}

// ── Summary ─────────────────────────────────────────────────────

const totalSource = sourceKeys.size
const totalZh = zh.keys.size
const totalEn = en.keys.size

console.log(`\n📊 Summary: ${totalZh} zh-CN keys, ${totalEn} en-US keys, ${totalSource} source usages`)

if (exitCode === 0) {
  console.log('✅ All translation keys in sync!\n')
} else {
  console.log('\n❌ Issues found. Please fix before committing.\n')
}

process.exit(exitCode)
