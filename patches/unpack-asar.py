#!/usr/bin/env python3
"""Giai nen file .asar cua Electron ma khong can Node.

Dung:  ./unpack-asar.py <app.asar> <thu-muc-dich>

Viet rieng vi `npx asar` doc ca file vao RAM — app.asar cua Zalo ~900MB nen
tien trinh Node bi giet. Ban nay doc theo tung khoi 4MB.

Dinh dang asar:
    [0:4]   uint32 = 4            (kich thuoc truong ke tiep)
    [4:8]   uint32 = headerPickle (kich thuoc pickle chua header)
    [8:12]  uint32                (kich thuoc chuoi JSON + padding)
    [12:16] uint32 = jsonLen
    [16:16+jsonLen] JSON cay thu muc
    du lieu bat dau tai (8 + headerPickle) lam tron len boi 4
"""
import json
import os
import struct
import sys

CHUNK = 4 << 20


def unpack(asar_path, out_dir):
    with open(asar_path, 'rb') as f:
        head = f.read(16)
        if len(head) < 16:
            sys.exit('Loi: file qua ngan, khong phai .asar')
        _, header_pickle, _, json_len = struct.unpack('<IIII', head)
        header = json.loads(f.read(json_len).decode('utf8'))
        base = 8 + header_pickle
        base += (4 - base % 4) % 4  # lam tron len boi 4

        made = [0]
        files = [0]

        def walk(node, rel):
            for name, info in node.get('files', {}).items():
                path = os.path.join(rel, name)
                if 'files' in info:
                    os.makedirs(os.path.join(out_dir, path), exist_ok=True)
                    made[0] += 1
                    walk(info, path)
                    continue
                if info.get('unpacked'):
                    # nam o app.asar.unpacked/ ben canh — chep o buoc khac
                    continue
                dst = os.path.join(out_dir, path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                off = base + int(info['offset'])
                size = int(info['size'])
                f.seek(off)
                with open(dst, 'wb') as o:
                    left = size
                    while left > 0:
                        buf = f.read(min(CHUNK, left))
                        if not buf:
                            sys.exit('Loi: doc thieu du lieu o %s' % path)
                        o.write(buf)
                        left -= len(buf)
                if info.get('executable'):
                    os.chmod(dst, 0o755)
                files[0] += 1
                if files[0] % 500 == 0:
                    print('   ... %d file' % files[0], flush=True)

        os.makedirs(out_dir, exist_ok=True)
        walk(header, '')
        print('   giai nen xong: %d file, %d thu muc' % (files[0], made[0]))

    # chep phan .unpacked neu co (native module thuong nam o day)
    unpacked = asar_path + '.unpacked'
    if os.path.isdir(unpacked):
        import shutil
        for root, _dirs, names in os.walk(unpacked):
            for n in names:
                src = os.path.join(root, n)
                rel = os.path.relpath(src, unpacked)
                dst = os.path.join(out_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        print('   da chep them app.asar.unpacked/')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit('Dung: ./unpack-asar.py <app.asar> <thu-muc-dich>')
    unpack(sys.argv[1], os.path.abspath(os.path.expanduser(sys.argv[2])))
