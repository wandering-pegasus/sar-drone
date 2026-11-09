"""Extract one STORED/DEFLATED member from a remote zip via HTTP range requests.
usage: remotezip_get.py URL MEMBER OUTFILE"""
import sys, struct, urllib.request, zlib, shutil
url, member, outp = sys.argv[1:4]
def rng(a, b):
    req = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (a, b)})
    return urllib.request.urlopen(req, timeout=120)
size = int(urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60).headers["Content-Length"])
tail = rng(size - 65536 - 22, size - 1).read()
j = tail.rfind(b"PK\x06\x06")
if j >= 0: cd_size, cd_off = struct.unpack("<QQ", tail[j+40:j+56])
else:
    i = tail.rfind(b"PK\x05\x06"); cd_size, cd_off = struct.unpack("<II", tail[i+12:i+20])
cd = rng(cd_off, cd_off + cd_size - 1).read()
p = 0
while cd[p:p+4] == b"PK\x01\x02":
    method, = struct.unpack("<H", cd[p+10:p+12])
    crc, csize, usize = struct.unpack("<III", cd[p+16:p+28])
    nl, el, cl = struct.unpack("<HHH", cd[p+28:p+34])
    off, = struct.unpack("<I", cd[p+42:p+46])
    name = cd[p+46:p+46+nl].decode(); extra = cd[p+46+nl:p+46+nl+el]
    if name == member:
        # parse zip64 extra
        q = 0
        while q < len(extra):
            hid, hl = struct.unpack("<HH", extra[q:q+4]); body = extra[q+4:q+4+hl]
            if hid == 1:
                vals = list(struct.unpack("<%dQ" % (hl // 8), body)); k = 0
                if usize == 0xFFFFFFFF: usize = vals[k]; k += 1
                if csize == 0xFFFFFFFF: csize = vals[k]; k += 1
                if off == 0xFFFFFFFF: off = vals[k]; k += 1
            q += 4 + hl
        break
    p += 46 + nl + el + cl
else:
    sys.exit("member not found")
lh = rng(off, off + 29).read()
lnl, lel = struct.unpack("<HH", lh[26:30])
start = off + 30 + lnl + lel
print("method", method, "csize", csize, "usize", usize, "crc", hex(crc), flush=True)
r = rng(start, start + csize - 1)
d = zlib.decompressobj(-15) if method == 8 else None
c = 0; n = 0
with open(outp, "wb") as f:
    while True:
        b = r.read(1 << 22)
        if not b: break
        if d: b = d.decompress(b)
        c = zlib.crc32(b, c); n += len(b); f.write(b)
    if d: b = d.flush(); c = zlib.crc32(b, c); n += len(b); f.write(b)
print("wrote", n, "bytes; crc", "OK" if (c & 0xFFFFFFFF) == crc and n == usize else "MISMATCH")
