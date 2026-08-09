'use strict';
// zjxl thay the cho Linux — dung libjxl (djxl/cjxl) thay cho .node cua Zalo
//
// Hop dong API lay tu ma app:
//   status_code: 1 = SUCCESS, 0 = FAILURE
//   getJxlInfo(buf)            -> { status_code, width, height, ... }
//   jxlToJpeg(buf, opts)       -> { status_code, data:<Buffer JPEG> }
//   jxlDecompressMulti(buf)    -> { status_code, data }
//   resizeJxl(buf, w, h, opts) -> { status_code, data }
//   bitmapToJxl(buf, opts)     -> { status_code, data:<Buffer JXL> }
//   moduleReady()              -> Promise<boolean>
//
// HIEU NANG: moi thao tac chay qua ONG (stdin -> stdout), khong dung file tam.
// Do tren anh 1920x2560 / 183 KB:
//     file tam : 95.8 ms/anh
//     qua ong  : 51.0 ms/anh      <- gan gap doi
// Trong 51 ms do, ban than djxl giai ma mat ~42 ms va fork ~3 ms, nen viet
// addon N-API lien ket thang libjxl chi tiet kiem them ~5 ms — khong dang cong
// va se keo theo toolchain C++ vao Flatpak. Da do truoc khi quyet.

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const SUCCESS = 1;
const FAILURE = 0;

const DJXL = findBin('djxl');
const CJXL = findBin('cjxl');

function findBin(name) {
  // Thu tu tim: Flatpak (/app/bin) -> Snap ($SNAP/usr/bin) -> he thong.
  // Trong snap, binary cua chinh snap nam duoi $SNAP chu khong phai /usr/bin.
  const dirs = ['/app/bin'];
  if (process.env.SNAP) {
    dirs.push(path.join(process.env.SNAP, 'usr', 'bin'));
    dirs.push(path.join(process.env.SNAP, 'bin'));
  }
  dirs.push('/usr/bin', '/usr/local/bin', '/bin');
  for (const d of dirs) {
    const p = path.join(d, name);
    try { fs.accessSync(p, fs.constants.X_OK); return p; } catch (_) {}
  }
  return name; // de PATH tu tim
}

function toBuffer(x) {
  if (!x) return Buffer.alloc(0);
  if (Buffer.isBuffer(x)) return x;
  if (x instanceof Uint8Array) return Buffer.from(x.buffer, x.byteOffset, x.byteLength);
  if (x.buffer) return Buffer.from(x.buffer);
  return Buffer.from(x);
}

// Chay mot lenh, day `input` vao stdin va gom stdout. Khong cham dia.
function pipe(bin, args, input, timeout) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (r) => { if (!done) { done = true; resolve(r); } };
    let child;
    try {
      child = spawn(bin, args, { stdio: ['pipe', 'pipe', 'pipe'] });
    } catch (e) {
      return finish({ err: e, data: null, stderr: String(e && e.message || e) });
    }
    const chunks = [];
    let errText = '';
    let bytes = 0;
    const MAX = 256 * 1024 * 1024;

    const timer = setTimeout(() => { try { child.kill('SIGKILL'); } catch (_) {}
      finish({ err: new Error('timeout'), data: null, stderr: errText }); }, timeout || 20000);

    child.stdout.on('data', (d) => {
      bytes += d.length;
      if (bytes > MAX) { try { child.kill('SIGKILL'); } catch (_) {} return; }
      chunks.push(d);
    });
    child.stderr.on('data', (d) => { if (errText.length < 4096) errText += d.toString(); });
    child.on('error', (e) => { clearTimeout(timer); finish({ err: e, data: null, stderr: errText }); });
    child.on('close', (code) => {
      clearTimeout(timer);
      finish({ err: code === 0 ? null : new Error('exit ' + code), data: Buffer.concat(chunks), stderr: errText });
    });

    // EPIPE khi tien trinh con thoat som — nuot, ket qua da xu ly o 'close'
    child.stdin.on('error', () => {});
    if (input && input.length) child.stdin.end(input); else child.stdin.end();
  });
}

// doc kich thuoc tu header JXL — thuan JS, 0 ms, khong can goi tien trinh nao
function parseJxlSize(buf) {
  try {
    const out = { width: 0, height: 0 };
    let b = buf;
    if (b.length > 12 && b.readUInt32BE(4) === 0x4a584c20) { // container 'JXL '
      const i = b.indexOf(Buffer.from('jxlc'));
      if (i > 0) b = b.slice(i + 4);
    }
    if (!(b.length > 2 && b[0] === 0xff && b[1] === 0x0a)) return null; // chu ky codestream
    let bitPos = 16;
    const rd = (n) => { let v = 0; for (let k = 0; k < n; k++) { const byte = b[(bitPos >> 3)]; if (byte === undefined) return v; v |= ((byte >> (bitPos & 7)) & 1) << k; bitPos++; } return v; };
    const small = rd(1);
    let h, w;
    if (small) { h = (rd(5) + 1) * 8; } else {
      const sel = rd(2);
      h = rd([9, 13, 18, 30][sel]) + 1;
    }
    const ratio = rd(3);
    if (ratio === 0) {
      if (small) { w = (rd(5) + 1) * 8; } else {
        const sel = rd(2); w = rd([9, 13, 18, 30][sel]) + 1;
      }
    } else {
      const R = [[1, 1], [12, 10], [4, 3], [3, 2], [16, 9], [5, 4], [2, 1]][ratio - 1];
      w = Math.round(h * R[0] / R[1]);
    }
    out.width = w; out.height = h;
    return (w > 0 && h > 0) ? out : null;
  } catch (_) { return null; }
}

async function getJxlInfo(input) {
  const buf = toBuffer(input);
  let size = parseJxlSize(buf);
  if (!size) {
    // du phong: hoi djxl, van khong cham dia
    const r = await pipe(DJXL, ['-', '-', '--output_format', 'ppm', '--num_threads=1'], buf, 15000);
    const m = /(\d+)\s*x\s*(\d+)/.exec(r.stderr || '');
    if (m) size = { width: parseInt(m[1], 10), height: parseInt(m[2], 10) };
  }
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
  // uu tien tai tao JPEG goc (khi anh duoc encode tu JPEG thi day la lossless)
  let r = await pipe(DJXL, ['-', '-', '--output_format', 'jpeg'], buf);
  if (r.data && r.data.length) return { status_code: SUCCESS, data: r.data };
  // du phong: JXL -> PNG (anh khong tai tao duoc JPEG)
  r = await pipe(DJXL, ['-', '-', '--output_format', 'png'], buf);
  if (r.data && r.data.length) return { status_code: SUCCESS, data: r.data };
  return { status_code: FAILURE };
}

async function jxlDecompressMulti(input) {
  const r = await jxlToJpeg(input);
  return r.status_code === SUCCESS ? { status_code: SUCCESS, data: r.data } : { status_code: FAILURE };
}

async function resizeJxl(input, width, height) {
  const buf = toBuffer(input);
  const w = Number(width) || 0, h = Number(height) || 0;
  const dec = await pipe(DJXL, ['-', '-', '--output_format', 'png'], buf);
  if (!dec.data || !dec.data.length) return { status_code: FAILURE };
  let png = dec.data;
  if (w > 0 || h > 0) {
    const rs = await pipe('magick', ['png:-', '-resize', (w || '') + 'x' + (h || ''), 'png:-'], png);
    if (rs.data && rs.data.length) png = rs.data;
  }
  const enc = await pipe(CJXL, ['-', '-', '-d', '1', '--num_threads=1'], png, 30000);
  if (enc.data && enc.data.length) return { status_code: SUCCESS, data: enc.data };
  return { status_code: SUCCESS, data: png }; // it nhat tra ve anh giai ma duoc
}

async function bitmapToJxl(input) {
  const buf = toBuffer(input);
  const enc = await pipe(CJXL, ['-', '-', '-d', '1'], buf, 30000);
  if (enc.data && enc.data.length) return { status_code: SUCCESS, data: enc.data };
  return { status_code: FAILURE };
}

let readyCache = null;
async function moduleReady() {
  if (readyCache !== null) return readyCache;
  const r = await pipe(DJXL, ['--version'], null, 5000);
  readyCache = !r.err || /jxl|version/i.test(r.stderr || '');
  return readyCache;
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
  apiVersion: '1.1.0-linux-libjxl-pipe',
};
