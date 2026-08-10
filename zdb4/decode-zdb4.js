#!/usr/bin/env node
// Giải mã file sao lưu ZDB4.0 (.zl.zip) -> SQLite, độc lập với app Zalo.
// Dùng chính native module db-cross-v4 (bản Linux) để tái lập ĐÚNG thuật toán:
//   AES-256-CBC (no pad, khoá hex 64 ký tự) -> LZMA -> SQLite.
//
//   node decode-zdb4.js <input.zl.zip> <output.sqlite> <KEY_HEX_64>
//
// KEY lấy từ zdb4-key-capture.js (bắt lúc app khôi phục) hoặc từ tài khoản.
const path = require('path');

function findNative() {
  const cands = [
    process.env.ZDB4_NATIVE,
    path.join(__dirname, 'db-cross-v4-native.node'),
    path.join(__dirname, '..', '..', 'zalo-clean', 'app', 'native', 'nativelibs',
      'db-cross-v4', 'prebuilt', 'linux', 'electron', 'x64', 'db-cross-v4-native.node'),
    '/app/zalo/native/nativelibs/db-cross-v4/prebuilt/linux/electron/x64/db-cross-v4-native.node',
  ].filter(Boolean);
  for (const c of cands) { try { require.resolve(c); return c; } catch {} }
  throw new Error('Khong tim thay db-cross-v4-native.node — dat bien ZDB4_NATIVE.');
}

async function main() {
  const [inp, outp, key] = process.argv.slice(2);
  if (!inp || !outp || !key) {
    console.error('Dung: node decode-zdb4.js <input.zl.zip> <output.sqlite> <KEY_HEX_64>');
    process.exit(2);
  }
  if (!/^[0-9a-fA-F]{64}$/.test(key)) {
    console.error('Canh bao: khoa khong phai 64 hex — van thu, nhung nhieu kha nang sai.');
  }
  const mod = require(findNative());
  const fn = mod.DecompressAndDecryptDb_V2 || mod.decompressAndDecryptDb_V2;
  if (!fn) { console.error('Native thieu DecompressAndDecryptDb_V2. Export:', Object.keys(mod)); process.exit(3); }

  let last = -1;
  const onProgress = () => { /* callback dem block; im lang */ };
  const t0 = Date.now();
  // Native tra { result, inner_error, error_message }
  const r = fn(inp, outp, key.toUpperCase(), onProgress);
  const dt = ((Date.now() - t0) / 1000).toFixed(1);
  if (r && (r.result === 0 || r === 0)) {
    console.log(`OK sau ${dt}s -> ${outp}`);
  } else {
    console.error('That bai:', JSON.stringify(r));
    process.exit(1);
  }
}
main().catch(e => { console.error(e); process.exit(1); });
