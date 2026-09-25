// README の WORKS / BLOG セクションを WordPress の REST API から更新する。
// 依存パッケージなし（Node.js 20 以上）。
//
//   node scripts/update-readme.mjs

import { mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const README = path.join(ROOT, 'README.md');
const THUMB_DIR = path.join(ROOT, 'assets', 'works');

const PORTFOLIO = 'https://yuyaoo.com';
const BLOG = 'https://codecabinbyyuya.com';
const WORKS_COUNT = 3;
const BLOG_COUNT = 3;

// 表示しない作品（タイトルに含まれる語 / カテゴリ名）
const EXCLUDE_TITLE = ['練習'];
const EXCLUDE_CATEGORY = ['Uncategorized'];

// サムネイルは 16:10 に切り抜いて高さを揃える
const THUMB_W = 768;
const THUMB_H = 480;

async function fetchWithRetry(url, tries = 3) {
  for (let i = 1; ; i++) {
    try {
      const res = await fetch(url, { headers: { 'User-Agent': 'riu-414-profile-updater' }, signal: AbortSignal.timeout(30_000) });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
      return res;
    } catch (err) {
      if (i >= tries) throw err;
      await new Promise((r) => setTimeout(r, 3000 * i));
    }
  }
}

async function getJSON(url) {
  return (await fetchWithRetry(url)).json();
}

function decodeEntities(str) {
  const named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', hellip: '…' };
  return str
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&([a-z]+);/gi, (m, n) => named[n] ?? m);
}

const escapeHtml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function formatDate(iso) {
  return iso.slice(0, 10).replace(/-/g, '.');
}

// shields.io のバッジ URL（"-" と "_" はエスケープが必要）
function tagBadge(label) {
  const text = encodeURIComponent(label.replace(/-/g, '--').replace(/_/g, '__'));
  return `https://img.shields.io/badge/${text}-A85E36?style=flat-square`;
}

// アイキャッチ画像を埋め込んだ SVG を作る（README では object-fit が使えないため）
async function buildThumb(imageUrl, slug) {
  const res = await fetchWithRetry(imageUrl);
  const type = res.headers.get('content-type') ?? 'image/jpeg';
  const data = Buffer.from(await res.arrayBuffer()).toString('base64');
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${THUMB_W}" height="${THUMB_H}" viewBox="0 0 ${THUMB_W} ${THUMB_H}">` +
    `<defs><clipPath id="r"><rect width="${THUMB_W}" height="${THUMB_H}" rx="10"/></clipPath></defs>` +
    `<image clip-path="url(#r)" width="${THUMB_W}" height="${THUMB_H}" preserveAspectRatio="xMidYMid slice" xlink:href="data:${type};base64,${data}"/>` +
    `</svg>\n`;
  const file = `${slug}.svg`;
  await writeFile(path.join(THUMB_DIR, file), svg);
  return `./assets/works/${file}`;
}

function pickImage(media) {
  const sizes = media?.media_details?.sizes ?? {};
  return (sizes.medium_large ?? sizes.large ?? sizes.full)?.source_url ?? media?.source_url;
}

async function renderWorks() {
  const posts = await getJSON(
    `${PORTFOLIO}/wp-json/wp/v2/posts?per_page=20&_embed=wp:featuredmedia,wp:term&_fields=id,slug,title,link,_links,_embedded`,
  );

  const works = posts
    .map((p) => ({
      id: p.id,
      title: decodeEntities(p.title.rendered),
      link: p.link,
      tags: (p._embedded?.['wp:term'] ?? []).flat().filter((t) => t.taxonomy === 'category').map((t) => t.name),
      image: pickImage(p._embedded?.['wp:featuredmedia']?.[0]),
    }))
    .filter((w) => !EXCLUDE_TITLE.some((word) => w.title.includes(word)))
    .filter((w) => !w.tags.some((t) => EXCLUDE_CATEGORY.includes(t)))
    .slice(0, WORKS_COUNT);

  await mkdir(THUMB_DIR, { recursive: true });
  const keep = new Set();
  const cells = [];
  for (const w of works) {
    const thumb = w.image ? await buildThumb(w.image, `work-${w.id}`) : null;
    if (thumb) keep.add(path.basename(thumb));
    const title = escapeHtml(w.title);
    const tags = w.tags.map((t) => `<img src="${tagBadge(t)}" alt="${escapeHtml(t)}">`).join(' ');
    cells.push(
      [
        `<td width="33%" valign="top">`,
        thumb ? `<a href="${w.link}"><img src="${thumb}" alt="${title}" width="100%"></a><br>` : '',
        `<a href="${w.link}"><b>${title}</b></a><br>`,
        tags,
        `</td>`,
      ].join('\n'),
    );
  }

  // 表示しなくなった作品のサムネイルを消す
  for (const file of await readdir(THUMB_DIR)) {
    if (!keep.has(file)) await rm(path.join(THUMB_DIR, file));
  }

  return `<table>\n<tr>\n${cells.join('\n')}\n</tr>\n</table>`;
}

async function renderBlog() {
  const posts = await getJSON(`${BLOG}/wp-json/wp/v2/posts?per_page=${BLOG_COUNT}&_fields=title,link,date`);
  return posts.map((p) => `- \`${formatDate(p.date)}\` [${decodeEntities(p.title.rendered)}](${p.link})`).join('\n');
}

function replaceSection(md, name, content) {
  const re = new RegExp(`(<!-- ${name}:START -->)[\\s\\S]*?(<!-- ${name}:END -->)`);
  if (!re.test(md)) throw new Error(`marker not found: ${name}`);
  return md.replace(re, `$1\n${content}\n$2`);
}

// 取得に失敗したセクションは前回の内容のまま残す
async function update(md, name, render) {
  try {
    return replaceSection(md, name, await render());
  } catch (err) {
    console.error(`::warning::${name} の更新をスキップしました: ${err.cause?.message ?? err.message}`);
    failed = true;
    return md;
  }
}

let failed = false;
const readme = await readFile(README, 'utf8');
let next = await update(readme, 'WORKS', renderWorks);
next = await update(next, 'BLOG', renderBlog);

if (next !== readme) {
  await writeFile(README, next);
  console.log('README.md updated');
} else {
  console.log('README.md is up to date');
}

if (failed) process.exitCode = 1;
