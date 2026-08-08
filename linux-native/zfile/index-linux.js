'use strict';
// zfile thay the cho Linux (ban goc chi ho tro Windows)
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const { execFileSync } = require('child_process');

async function walk(root) {
  let size = 0, fileNumber = 0, n = 0;
  const stack = [String(root)];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try { entries = await fsp.readdir(dir, { withFileTypes: true }); } catch (_) { continue; }
    for (const e of entries) {
      const p = path.join(dir, e.name);
      try {
        if (e.isDirectory()) { stack.push(p); continue; }
        if (!e.isFile()) continue;
        const st = await fsp.stat(p);
        size += st.size; fileNumber++;
      } catch (_) {}
      if (++n % 300 === 0) await new Promise(r => setImmediate(r));
    }
  }
  return { size, fileNumber };
}

async function statPath(p, isFolder) {
  try {
    const st = await fsp.stat(p);
    if (isFolder || st.isDirectory()) {
      const r = await walk(p);
      // tra ve nhieu ten truong de tuong thich cac cho goi khac nhau
      return {
        size: r.size, totalSize: r.size,
        fileNumber: r.fileNumber, fileCount: r.fileNumber, numberOfFiles: r.fileNumber,
        isFolder: true, exists: true,
        createdTime: st.birthtimeMs, modifiedTime: st.mtimeMs
      };
    }
    return {
      size: st.size, totalSize: st.size,
      fileNumber: 1, fileCount: 1, numberOfFiles: 1,
      isFolder: false, exists: true,
      createdTime: st.birthtimeMs, modifiedTime: st.mtimeMs
    };
  } catch (_) {
    return { size: 0, totalSize: 0, fileNumber: 0, fileCount: 0, numberOfFiles: 0, isFolder: !!isFolder, exists: false };
  }
}

function can(p, mode) {
  try { fs.accessSync(String(p), mode); return true; } catch (_) { return false; }
}

// chi hoi df cho tung duong dan cu the -> tranh mount hong lam df loi
function dfFor(target) {
  try {
    const out = execFileSync('df', ['-B1', '--output=target,size,avail', String(target)],
      { encoding: 'utf8', timeout: 4000, stdio: ['ignore', 'pipe', 'ignore'] });
    const line = String(out).trim().split('\n')[1];
    if (!line) return null;
    const parts = line.trim().split(/\s+/);
    const avail = Number(parts[parts.length - 1]) || 0;
    const total = Number(parts[parts.length - 2]) || 0;
    const mount = parts.slice(0, parts.length - 2).join(' ') || String(target);
    return { name: mount, path: mount, totalSpace: total, freeSpace: avail, availableSpace: avail };
  } catch (_) { return null; }
}

function diskInfoSync() {
  const targets = [];
  try { targets.push(require('os').homedir()); } catch (_) {}
  targets.push('/');
  const seen = new Set();
  const out = [];
  for (const t of targets) {
    const d = dfFor(t);
    if (d && !seen.has(d.path)) { seen.add(d.path); out.push(d); }
  }
  return out.length ? out : [{ name: '/', path: '/', totalSpace: 0, freeSpace: 0, availableSpace: 0 }];
}

let copyCancelled = false;

module.exports = {
  stat: (p, isFolder) => statPath(p, isFolder),
  statFolder: (p) => statPath(p, true),
  diskInfo: async () => diskInfoSync(),
  canRead: (p) => can(p, fs.constants.R_OK),
  canWrite: (p) => can(p, fs.constants.W_OK),
  canReadAndWrite: (p) => can(p, fs.constants.R_OK | fs.constants.W_OK),
  cancelCopy: async () => { copyCancelled = true; return true; },
  copyFolder: async (src, dest, callback) => {
    copyCancelled = false;
    try {
      await fsp.cp(String(src), String(dest), { recursive: true, force: true });
      if (typeof callback === 'function') callback(null, { done: true });
      return { done: true };
    } catch (e) {
      if (typeof callback === 'function') callback(e);
      return { done: false, error: String(e && e.message || e) };
    }
  },
};
