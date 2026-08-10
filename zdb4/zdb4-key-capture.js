// Shim BAT KHOA sao lưu. Dat truoc db-cross-v4 trong app de ghi lai khoa that
// tai dung thoi diem nguoi dung bam "khoi phuc".
//
// Cach dung: trong native/nativelibs/db-cross-v4/index.js (hoac noi require .node),
// bọc module goc:
//     const real = require('./prebuilt/.../db-cross-v4-native.node');
//     module.exports = require('/duong/dan/zdb4-key-capture.js')(real);
//
// Khoa se duoc ghi ra ~/zdb4-key.txt (chmod 600). KHONG in ra log app.
const fs = require('fs'), os = require('os'), path = require('path');
module.exports = function wrap(real) {
  const out = path.join(os.homedir(), 'zdb4-key.txt');
  function tap(name, fn) {
    return function (...args) {
      try {
        // chu ky: (inputPath, outputPath, key[, cb])
        const [inp, outp, key] = args;
        const line = JSON.stringify({ t: Date.now(), fn: name, inp, outp, key }) + '\n';
        fs.appendFileSync(out, line, { mode: 0o600 });
        fs.chmodSync(out, 0o600);
      } catch {}
      return fn.apply(this, args);
    };
  }
  const proxy = Object.create(real);
  for (const k of ['DecompressAndDecryptDb', 'DecompressAndDecryptDb_V2',
                   'decompressAndDecryptDb', 'decompressAndDecryptDb_V2']) {
    if (typeof real[k] === 'function') proxy[k] = tap(k, real[k].bind(real));
  }
  return proxy;
};
