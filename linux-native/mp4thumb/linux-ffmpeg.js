// Backend Linux cho mp4thumb — dựng thumbnail video bằng ffmpeg.
// Cùng lối với zjxl (djxl): native module của Windows/macOS không dùng được trên
// Linux, nên thay bằng công cụ hệ thống, giữ nguyên hợp đồng public.
//   MP4Thumb().generateThumbnailAsync(inputPath, outputPath, maxWidth, maxHeight) -> Promise<bool>
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

function findBin(name) {
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
    return name; // để PATH tự lo
}
const FFMPEG = findBin('ffmpeg');

function MP4Thumb() {
    let proc = null;
    let cancelled = false;

    function run(inputPath, outputPath, maxWidth, maxHeight, seek) {
        return new Promise((resolve, reject) => {
            if (cancelled) return reject(new Error('cancelled'));
            const w = Number(maxWidth) > 0 ? Math.floor(maxWidth) : 320;
            const h = Number(maxHeight) > 0 ? Math.floor(maxHeight) : 320;
            // vừa khít trong khung, giữ tỉ lệ, ép chiều chẵn cho codec
            const vf = `scale='min(${w},iw)':'min(${h},ih)':force_original_aspect_ratio=decrease,` +
                       `scale=trunc(iw/2)*2:trunc(ih/2)*2`;
            const args = ['-y', '-loglevel', 'error'];
            if (seek > 0) args.push('-ss', String(seek));
            args.push('-i', inputPath, '-frames:v', '1', '-vf', vf, '-f', 'image2', outputPath);
            proc = spawn(FFMPEG, args, { stdio: ['ignore', 'ignore', 'pipe'] });
            let err = '';
            proc.stderr.on('data', d => { err += d.toString(); });
            proc.on('error', e => reject(e));
            proc.on('close', code => {
                proc = null;
                let ok = false;
                try { ok = code === 0 && fs.statSync(outputPath).size > 0; } catch (_) {}
                ok ? resolve(true) : reject(new Error(err.trim() || `ffmpeg exit ${code}`));
            });
        });
    }

    this.generateThumbnailAsync = async function (inputPath, outputPath, maxWidth, maxHeight) {
        if (!inputPath || !outputPath) throw { error: 'INVALID_PARAMS', message: 'thiếu đường dẫn' };
        try { fs.mkdirSync(path.dirname(outputPath), { recursive: true }); } catch (_) {}
        // thử lấy khung ở giây 1 (tránh khung đen đầu video); thất bại thì lấy khung 0
        try { return await run(inputPath, outputPath, maxWidth, maxHeight, 1); }
        catch (_) { return await run(inputPath, outputPath, maxWidth, maxHeight, 0); }
    };

    this.generateThumbnail = function () {
        throw { error: 'LIB_ERR', message: 'dùng generateThumbnailAsync trên Linux' };
    };

    this.cancel = function () {
        cancelled = true;
        if (proc) { try { proc.kill('SIGKILL'); } catch (_) {} proc = null; }
    };
}

module.exports = { MP4Thumb };
