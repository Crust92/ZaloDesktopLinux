'use strict';
// file-utilities thay the cho Linux (Zalo khong phat hanh .node cho Linux)
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { execFileSync } = require('child_process');

// Hop dong `deep` (bat buoc cho man "Quan ly du lieu -> Tin nhan media"):
//   getDirectorySizeAsync(dir, { deep: { maxDepth: 3 } })
//     -> { totalSize, fileCount, tree: [ { relativePath, totalSize, fileCount }, ... ] }
// Ben goi (calculateConvDataForResMntV2) doc `e.tree` roi cong `totalSize` theo
// ten thu muc con cap 1: video | picture | file | fileNoise | folder | fileThumb
// | voice | richThumb. Thieu truong `tree` thi app nem TypeError o `a.tree.length`
// va tien trinh quet khong bao gio ket thuc -> man hinh quay vong mai.
function maxDepthOf(options) {
  const d = options && options.deep;
  if (!d) return 0;
  const n = Number(d.maxDepth);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

async function walkSize(root, filter, options) {
  const maxDepth = maxDepthOf(options);
  const rootPath = String(root);
  let totalSize = 0, fileCount = 0, n = 0;
  // gom theo thu muc tuong doi, chi giu den maxDepth
  const agg = maxDepth ? new Map() : null;

  const add = (relDir, size) => {
    if (!agg || !relDir) return;
    // cong don cho chinh no va moi to tien trong pham vi maxDepth
    const parts = relDir.split('/');
    for (let i = 1; i <= Math.min(parts.length, maxDepth); i++) {
      const key = parts.slice(0, i).join('/');
      const cur = agg.get(key) || { totalSize: 0, fileCount: 0 };
      cur.totalSize += size; cur.fileCount += 1;
      agg.set(key, cur);
    }
  };

  const stack = [rootPath];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try { entries = await fsp.readdir(dir, { withFileTypes: true }); } catch (_) { continue; }
    for (const e of entries) {
      const p = path.join(dir, e.name);
      try {
        if (e.isDirectory()) { stack.push(p); continue; }
        if (!e.isFile()) continue;
        if (filter && !filter(p)) continue;
        const st = await fsp.stat(p);
        totalSize += st.size; fileCount++;
        if (agg) add(path.relative(rootPath, dir).split(path.sep).join('/'), st.size);
      } catch (_) {}
      if (++n % 300 === 0) await new Promise(r => setImmediate(r));
    }
  }

  const out = { totalSize, fileCount };
  if (agg) {
    out.tree = [...agg.entries()]
      .map(([relativePath, v]) => ({ relativePath, totalSize: v.totalSize, fileCount: v.fileCount }))
      .sort((a, b) => b.totalSize - a.totalSize);
  }
  return out;
}

function walkSizeSync(root, filter, options) {
  const maxDepth = maxDepthOf(options);
  const rootPath = String(root);
  let totalSize = 0, fileCount = 0;
  const agg = maxDepth ? new Map() : null;

  const add = (relDir, size) => {
    if (!agg || !relDir) return;
    const parts = relDir.split('/');
    for (let i = 1; i <= Math.min(parts.length, maxDepth); i++) {
      const key = parts.slice(0, i).join('/');
      const cur = agg.get(key) || { totalSize: 0, fileCount: 0 };
      cur.totalSize += size; cur.fileCount += 1;
      agg.set(key, cur);
    }
  };

  const stack = [rootPath];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { continue; }
    for (const e of entries) {
      const p = path.join(dir, e.name);
      try {
        if (e.isDirectory()) { stack.push(p); continue; }
        if (!e.isFile()) continue;
        if (filter && !filter(p)) continue;
        const size = fs.statSync(p).size;
        totalSize += size; fileCount++;
        if (agg) add(path.relative(rootPath, dir).split(path.sep).join('/'), size);
      } catch (_) {}
    }
  }

  const out = { totalSize, fileCount };
  if (agg) {
    out.tree = [...agg.entries()]
      .map(([relativePath, v]) => ({ relativePath, totalSize: v.totalSize, fileCount: v.fileCount }))
      .sort((a, b) => b.totalSize - a.totalSize);
  }
  return out;
}

function escapeRe(s) {
  return s.replace(/[.+^${}()|[\]\\]/g, '\\$&');
}

// glob "/duong/dan/*/Cache/**" -> goc co dinh + regex
function globParts(g) {
  const s = String(g).split('\\').join('/');
  const i = s.search(/[*?]/);
  let base = s;
  if (i >= 0) {
    const cut = s.lastIndexOf('/', i);
    base = cut > 0 ? s.slice(0, cut) : '/';
  }
  const pat = escapeRe(s)
    .split('**').join('\u0001')
    .split('*').join('[^/]*')
    .split('\u0001').join('.*')
    .split('?').join('.');
  return { base, rx: new RegExp('^' + pat + '$') };
}

function fsType(p) {
  try {
    const out = execFileSync('stat', ['-f', '-c', '%T', String(p)], { encoding: 'utf8', timeout: 3000 });
    return String(out).trim() || 'ext4';
  } catch (_) { return 'ext4'; }
}

module.exports = {
  getDirectorySizeAsync: (d, options) => walkSize(d, null, options),
  getDirectorySizeSync: (d, options) => walkSizeSync(d, null, options),
  getDirectorySizeByGlobAsync: (g, options) => { const q = globParts(g); return walkSize(q.base, (p) => q.rx.test(p), options); },
  getDirectorySizeByGlobSync: (g, options) => { const q = globParts(g); return walkSizeSync(q.base, (p) => q.rx.test(p), options); },
  detectHardlinksAsync: async (a, b) => {
    try {
      const sa = await fsp.stat(a), sb = await fsp.stat(b);
      return (sa.ino === sb.ino && sa.dev === sb.dev) ? [String(b)] : [];
    } catch (_) { return []; }
  },
  detectHardlinksSync: (a, b) => {
    try {
      const sa = fs.statSync(a), sb = fs.statSync(b);
      return (sa.ino === sb.ino && sa.dev === sb.dev) ? [String(b)] : [];
    } catch (_) { return []; }
  },
  detectFilesystemAsync: async (p) => ({ filesystemType: fsType(p) }),
  detectFilesystemSync: (p) => ({ filesystemType: fsType(p) }),
};
