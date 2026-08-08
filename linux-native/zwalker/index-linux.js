'use strict';
// zwalker thay thế cho Linux — I/O BẤT ĐỒNG BỘ, không chặn event loop
const fsp = require('fs').promises;
const path = require('path');

function extSet(exts) {
  if (!Array.isArray(exts)) return null;
  const list = exts.filter(e => typeof e === 'string');
  if (!list.length) return null;
  return new Set(list.map(e => e.toLowerCase().replace(/^\./, '')));
}

async function walk(root, es) {
  let fileNumber = 0, size = 0, n = 0;
  const stack = [String(root)];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try { entries = await fsp.readdir(dir, { withFileTypes: true }); } catch (_) { continue; }
    for (const ent of entries) {
      const p = path.join(dir, ent.name);
      try {
        if (ent.isDirectory()) { stack.push(p); continue; }
        if (!ent.isFile()) continue;
        if (es) {
          const e = path.extname(ent.name).toLowerCase().replace(/^\./, '');
          if (!es.has(e)) continue;
        }
        const st = await fsp.stat(p);
        fileNumber++; size += st.size;
      } catch (_) {}
      // nhường event loop mỗi 200 file để UI cập nhật được
      if (++n % 200 === 0) await new Promise(r => setImmediate(r));
    }
  }
  return { fileNumber, size };
}

const timed = (n,f)=>f;
const scanDirectory = timed('scanDirectory', (dir, exts) => walk(dir, extSet(exts)));

module.exports = {
  scanDirectory,
  statUnmarkedFiles: timed('statUnmarkedFiles', (dir, exts) => walk(dir, extSet(exts))),
  updateReferenceMessageId: timed('updateReferenceMessageId', async () => ({ fileNumber: 0 })),
  deleteHomelessFiles: timed('deleteHomelessFiles', async () => ({ fileNumber: 0, size: 0 })),
  deleteEmptyFolders: timed('deleteEmptyFolders', async () => ({ deletedCount: 0, deletedDirs: [] })),
};
