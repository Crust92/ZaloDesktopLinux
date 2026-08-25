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
const os = require('os');
const fsp = require('fs').promises;
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

// ---------------------------------------------------------------- chay qua FILE
// libjxl 0.7 (ban co trong Ubuntu 24.04 / core24) KHONG doc duoc stdin va
// KHONG co --output_format:
//     cjxl - - -d 1      -> "Reading image data failed."   (0 byte)
//     djxl - - ...       -> exit 1
// Cu phap dung la:  cjxl IN OUT [-d N]  /  djxl IN OUT   (dinh dang theo DUOI file).
// Ban shim cu dung ong (-) nen MOI thao tac JXL deu that bai: dan anh vao khung
// chat bao "Handle blob fail", va anh .jxl cung khong hien duoc.
let tmpSeq = 0;
function tmpPath(ext) {
  return path.join(os.tmpdir(), `zjxl-${process.pid}-${Date.now()}-${tmpSeq++}${ext}`);
}

async function runFile(bin, mkArgs, input, inExt, outExt, timeout) {
  const inP = tmpPath(inExt), outP = tmpPath(outExt);
  try {
    if (input) await fsp.writeFile(inP, input);
    const r = await pipe(bin, mkArgs(inP, outP), null, timeout);
    let data = null;
    try { data = await fsp.readFile(outP); } catch (_) {}
    return { err: r.err, data, stderr: r.stderr };
  } catch (e) {
    return { err: e, data: null, stderr: String(e && e.message || e) };
  } finally {
    fsp.unlink(inP).catch(() => {});
    fsp.unlink(outP).catch(() => {});
  }
}

function pngSize(buf) {
  if (!buf || buf.length < 24) return null;
  if (buf[0] !== 0x89 || buf[1] !== 0x50) return null;
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

async function getJxlInfo(input) {
  const buf = toBuffer(input);
  let size = parseJxlSize(buf);
  if (!size) {
    const r = await runFile(DJXL, (i, o) => [i, o], buf, '.jxl', '.png', 15000);
    size = pngSize(r.data);
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
  // 1) tai tao JPEG goc (lossless khi anh von duoc encode tu JPEG)
  let r = await runFile(DJXL, (i, o) => [i, o], buf, '.jxl', '.jpg', 20000);
  if (r.data && r.data.length) return { status_code: SUCCESS, data: r.data };
  // 2) khong tai tao duoc -> ep giai ma ra pixel roi encode JPEG moi
  r = await runFile(DJXL, (i, o) => [i, o, '-j'], buf, '.jxl', '.jpg', 20000);
  if (r.data && r.data.length) return { status_code: SUCCESS, data: r.data };
  // 3) du phong: tra ve PNG
  r = await runFile(DJXL, (i, o) => [i, o], buf, '.jxl', '.png', 20000);
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
  const dec = await runFile(DJXL, (i, o) => [i, o], buf, '.jxl', '.png', 20000);
  if (!dec.data || !dec.data.length) return { status_code: FAILURE };
  let png = dec.data;
  if (w > 0 || h > 0) {
    // Flatpak/snap KHONG co ImageMagick; ffmpeg thi co (da dong goi cho P10).
    const scale = `scale=${w > 0 ? w : -1}:${h > 0 ? h : -1}`;
    const rs = await runFile('ffmpeg', (i, o) => ['-y', '-loglevel', 'error', '-i', i, '-vf', scale, o],
                             png, '.png', '.png', 20000);
    if (rs.data && rs.data.length) png = rs.data;
  }
  const enc = await runFile(CJXL, (i, o) => [i, o, '-d', '1'], png, '.png', '.jxl', 30000);
  if (enc.data && enc.data.length) return { status_code: SUCCESS, data: enc.data };
  return { status_code: SUCCESS, data: png }; // it nhat tra ve anh giai ma duoc
}

async function bitmapToJxl(input) {
  const buf = toBuffer(input);
  const enc = await runFile(CJXL, (i, o) => [i, o, '-d', '1'], buf, '.png', '.jxl', 30000);
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
  apiVersion: '2.0.0-linux-libjxl-file',
};
