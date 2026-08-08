'use strict';
// zjxl thay the cho Linux — dung libjxl (djxl/cjxl) thay cho .node cua Zalo
// Hop dong API lay tu ma app:
//   status_code: 1 = SUCCESS, 0 = FAILURE
//   getJxlInfo(buf)            -> { status_code, width, height, ... }
//   jxlToJpeg(buf, opts)       -> { status_code, data:<Buffer JPEG> }
//   jxlDecompressMulti(buf)    -> { status_code, data }
//   resizeJxl(buf, w, h, opts) -> { status_code, data }
//   bitmapToJxl(buf, opts)     -> { status_code, data:<Buffer JXL> }
//   moduleReady()              -> Promise<boolean>

const fs = require('fs');
const fsp = fs.promises;
const os = require('os');
const path = require('path');
const { execFile } = require('child_process');

const SUCCESS = 1;
const FAILURE = 0;

const DJXL = findBin('djxl');
const CJXL = findBin('cjxl');

function findBin(name) {
  const dirs = ['/usr/bin', '/usr/local/bin', '/app/bin', '/bin'];
  for (const d of dirs) {
    const p = path.join(d, name);
    try { fs.accessSync(p, fs.constants.X_OK); return p; } catch (_) {}
  }
  return name; // de PATH tu tim
}

function run(bin, args, timeout) {
  return new Promise((resolve) => {
    execFile(bin, args, { timeout: timeout || 20000, maxBuffer: 256 * 1024 * 1024, encoding: 'buffer' },
      (err, stdout, stderr) => resolve({ err, stdout, stderr: String(stderr || '') }));
  });
}

let tmpSeq = 0;
async function withTemp(inputBuf, inExt, outExt, fn) {
  const base = path.join(os.tmpdir(), 'zjxl-' + process.pid + '-' + (tmpSeq++));
  const fin = base + '.' + inExt;
  const fout = base + '.' + outExt;
  try {
    if (inputBuf) await fsp.writeFile(fin, inputBuf);
    const r = await fn(fin, fout);
    let data = null;
    try { data = await fsp.readFile(fout); } catch (_) {}
    return { r, data };
  } finally {
    fsp.unlink(fin).catch(() => {});
    fsp.unlink(fout).catch(() => {});
  }
}

function toBuffer(x) {
  if (!x) return Buffer.alloc(0);
  if (Buffer.isBuffer(x)) return x;
  if (x instanceof Uint8Array) return Buffer.from(x.buffer, x.byteOffset, x.byteLength);
  if (x.buffer) return Buffer.from(x.buffer);
  return Buffer.from(x);
}

// doc kich thuoc tu header JXL (khong can goi tien trinh ngoai)
function parseJxlSize(buf) {
  try {
    const out = { width: 0, height: 0 };
    // container ISOBMFF: tim box 'jxlc' hoac dung codestream truc tiep
    let b = buf;
    if (b.length > 12 && b.readUInt32BE(4) === 0x4a584c20) { // 'JXL '
      const i = b.indexOf(Buffer.from('jxlc'));
      if (i > 0) b = b.slice(i + 4);
    }
    if (!(b.length > 2 && b[0] === 0xff && b[1] === 0x0a)) return null; // signature codestream
    // giai ma SizeHeader toi thieu (bit-reader)
    let bitPos = 16;
    const rd = (n) => { let v = 0; for (let k = 0; k < n; k++) { const byte = b[(bitPos >> 3)]; if (byte === undefined) return v; v |= ((byte >> (bitPos & 7)) & 1) << k; bitPos++; } return v; };
    const small = rd(1);
    let h, w;
    if (small) { h = (rd(5) + 1) * 8; } else {
      const sel = rd(2);
      const bits = [9, 13, 18, 30][sel];
      h = rd(bits) + 1;
    }
    const ratio = rd(3);
    if (ratio === 0) {
      if (small) { w = (rd(5) + 1) * 8; } else {
        const sel = rd(2); const bits = [9, 13, 18, 30][sel]; w = rd(bits) + 1;
      }
    } else {
      const R = [[1, 1], [12, 10], [4, 3], [3, 2], [16, 9], [5, 4], [2, 1]][ratio - 1];
      w = Math.round(h * R[0] / R[1]);
    }
    out.width = w; out.height = h;
    return (w > 0 && h > 0) ? out : null;
  } catch (_) { return null; }
}

async function infoViaDjxl(buf) {
  const { r } = await withTemp(buf, 'jxl', 'ppm', async (fin, fout) => run(DJXL, [fin, fout, '--num_threads=1']));
  const m = /(\d+)\s*x\s*(\d+)/.exec(r.stderr || '');
  if (m) return { width: parseInt(m[1], 10), height: parseInt(m[2], 10) };
  return null;
}

async function getJxlInfo(input) {
  const buf = toBuffer(input);
  let size = parseJxlSize(buf);
  if (!size) size = await infoViaDjxl(buf);
  if (!size) return { status_code: FAILURE };
  return {
    status_code: SUCCESS,
    width: size.width, height: size.height,
    xsize: size.width, ysize: size.height,
    have_animation: false, num_color_channels: 3, alpha_bits: 0,
  };
}

async function jxlToJpeg(input) {
  const buf = toBuffer(input);
  // uu tien tai tao JPEG goc (neu anh duoc encode tu JPEG)
  let out = await withTemp(buf, 'jxl', 'jpg', async (fin, fout) => run(DJXL, [fin, fout]));
  if (out.data && out.data.length) return { status_code: SUCCESS, data: out.data };
  // fallback: JXL -> PNG
  out = await withTemp(buf, 'jxl', 'png', async (fin, fout) => run(DJXL, [fin, fout]));
  if (out.data && out.data.length) return { status_code: SUCCESS, data: out.data };
  return { status_code: FAILURE };
}

async function jxlDecompressMulti(input) {
  const r = await jxlToJpeg(input);
  return r.status_code === SUCCESS ? { status_code: SUCCESS, data: r.data } : { status_code: FAILURE };
}

async function resizeJxl(input, width, height) {
  const buf = toBuffer(input);
  const w = Number(width) || 0, h = Number(height) || 0;
  // giai ma -> PNG, thu nho bang ImageMagick neu co, roi encode lai JXL
  const dec = await withTemp(buf, 'jxl', 'png', async (fin, fout) => run(DJXL, [fin, fout]));
  if (!dec.data || !dec.data.length) return { status_code: FAILURE };
  let png = dec.data;
  if (w > 0 || h > 0) {
    const rs = await withTemp(png, 'png', 'png', async (fin, fout) =>
      run('magick', [fin, '-resize', (w || '') + 'x' + (h || ''), fout]));
    if (rs.data && rs.data.length) png = rs.data;
  }
  const enc = await withTemp(png, 'png', 'jxl', async (fin, fout) => run(CJXL, [fin, fout, '-d', '1', '--num_threads=1']));
  if (enc.data && enc.data.length) return { status_code: SUCCESS, data: enc.data };
  return { status_code: SUCCESS, data: png }; // it nhat tra ve anh giai ma duoc
}

async function bitmapToJxl(input) {
  const buf = toBuffer(input);
  const enc = await withTemp(buf, 'png', 'jxl', async (fin, fout) => run(CJXL, [fin, fout, '-d', '1']));
  if (enc.data && enc.data.length) return { status_code: SUCCESS, data: enc.data };
  return { status_code: FAILURE };
}

async function moduleReady() {
  const r = await run(DJXL, ['--version'], 5000);
  return !r.err || /jxl|version/i.test(r.stderr);
}

module.exports = {
  // KHONG co truong `error` — app kiem tra T.error de bao "Failed to load JXL Native library"
  getJxlInfo,
  jxlToJpeg,
  jxlToJpegMulti: jxlDecompressMulti,
  jxlDecompressMulti,
  resizeJxl,
  bitmapToJxl,
  generatePreview: resizeJxl,
  moduleReady,
  apiVersion: '1.0.0-linux-libjxl',
};
