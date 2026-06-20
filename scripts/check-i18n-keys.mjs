#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const zhPath = resolve(__dirname, '..', 'web/src/i18n/locales/zh.json');
const enPath = resolve(__dirname, '..', 'web/src/i18n/locales/en.json');

const zh = JSON.parse(readFileSync(zhPath, 'utf8'));
const en = JSON.parse(readFileSync(enPath, 'utf8'));

const zhKeys = new Set(Object.keys(zh));
const enKeys = new Set(Object.keys(en));

const onlyZh = [...zhKeys].filter((k) => !enKeys.has(k));
const onlyEn = [...enKeys].filter((k) => !zhKeys.has(k));

if (onlyZh.length || onlyEn.length) {
  console.error('i18n key mismatch:');
  if (onlyZh.length) console.error('  only in zh.json:', onlyZh);
  if (onlyEn.length) console.error('  only in en.json:', onlyEn);
  process.exit(1);
}

console.log(`i18n check ok: ${zhKeys.size} keys present in both locales.`);
