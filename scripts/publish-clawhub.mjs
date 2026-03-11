#!/usr/bin/env node
/**
 * Publish moltbillboard skill to ClawHub with acceptLicenseTerms: true.
 * Workaround for CLI v0.7.0 bug: https://github.com/openclaw/clawhub/issues/660
 *
 * Usage: from repo root, run: node scripts/publish-clawhub.mjs
 * Requires: clawhub login first (token in ~/Library/Application Support/clawhub/config.json)
 */

import { readFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

const CONFIG_PATH = process.env.CLAWHUB_CONFIG_PATH ||
  process.env.CLAWDHUB_CONFIG_PATH ||
  resolve(process.env.HOME || process.env.USERPROFILE, 'Library/Application Support/clawhub/config.json');

const REGISTRY = process.env.CLAWHUB_REGISTRY || process.env.CLAWDHUB_REGISTRY || 'https://clawhub.ai';

async function main() {
  const skillPath = resolve(ROOT, 'skill.json');
  const skill = JSON.parse(await readFile(skillPath, 'utf8'));

  let config;
  try {
    config = JSON.parse(await readFile(CONFIG_PATH, 'utf8'));
  } catch (e) {
    console.error('ClawHub config not found. Run: clawhub login');
    process.exit(1);
  }
  const token = config.token || config.accessToken;
  if (!token) {
    console.error('No token in ClawHub config. Run: clawhub login');
    process.exit(1);
  }

  const payload = {
    slug: skill.slug,
    displayName: skill.displayName,
    version: skill.version,
    changelog: skill.changelog || '',
    tags: Array.isArray(skill.tags) ? skill.tags : ['latest'],
    acceptLicenseTerms: true,
  };

  const form = new FormData();
  form.set('payload', JSON.stringify(payload));

  const files = skill.files || ['SKILL.md', 'llms.txt'];
  for (const name of files) {
    const path = resolve(ROOT, name);
    const bytes = await readFile(path);
    const blob = new Blob([bytes], { type: 'text/plain' });
    form.append('files', blob, name);
  }

  const url = `${REGISTRY.replace(/\/$/, '')}/api/v1/skills`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });

  if (!res.ok) {
    const text = await res.text();
    console.error(`Publish failed ${res.status}: ${text}`);
    process.exit(1);
  }

  const data = await res.json();
  console.log(`OK. Published ${skill.slug}@${skill.version} (${data.versionId || 'done'})`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
