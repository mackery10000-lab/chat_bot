"""Recompress PNGs without changing pixels, PNG filters, or metadata.

No third-party dependencies are required. Only the IDAT zlib stream changes;
the decompressed stream and every other PNG chunk must remain byte-identical.
Files are replaced only after verification and only when the result is smaller.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import zlib


BASE = Path(__file__).resolve().parents[1]
SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_chunks(data):
    if not data.startswith(SIGNATURE):
        raise ValueError("Invalid PNG signature")
    chunks = []
    offset = len(SIGNATURE)
    while offset < len(data):
        start = offset
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + length + 12
        if end > len(data):
            raise ValueError("Truncated PNG chunk")
        payload = data[offset + 8:offset + 8 + length]
        checksum = struct.unpack_from(">I", data, offset + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != checksum:
            raise ValueError("Invalid PNG chunk CRC: " + repr(kind))
        chunks.append((kind, payload, data[start:end]))
        offset = end
        if kind == b"IEND":
            break
    if offset != len(data) or not chunks or chunks[-1][0] != b"IEND":
        raise ValueError("Invalid PNG ending")
    if any(kind in (b"acTL", b"fcTL", b"fdAT") for kind, _, _ in chunks):
        raise ValueError("Animated PNG is not supported")
    return chunks


def idat_stream(chunks):
    return zlib.decompress(b"".join(data for kind, data, _ in chunks if kind == b"IDAT"))


def chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def optimize(path_string, dry_run):
    path = Path(path_string).resolve()
    before = path.read_bytes()
    if not before.startswith(SIGNATURE):
        # Some legacy assets have a .png name but contain JPEG data. Keep their
        # actual format and existing links intact; this tool only handles PNGs.
        return {
            "path": path.relative_to(BASE).as_posix(),
            "before_bytes": len(before),
            "after_bytes": len(before),
            "changed": False,
            "skipped": "File has a .png name but is not PNG; bytes preserved",
            "file_sha256": hashlib.sha256(before).hexdigest(),
        }
    original = read_chunks(before)
    raw = idat_stream(original)
    compressed = zlib.compress(raw, level=9)
    pieces = [SIGNATURE]
    inserted = False
    for kind, _, encoded in original:
        if kind == b"IDAT":
            if not inserted:
                pieces.append(chunk(b"IDAT", compressed))
                inserted = True
        else:
            pieces.append(encoded)
    if not inserted:
        raise ValueError("PNG has no image data: " + str(path))
    candidate = b"".join(pieces)
    optimized = read_chunks(candidate)
    if idat_stream(optimized) != raw:
        raise ValueError("PNG scanline data changed: " + str(path))
    if ([encoded for kind, _, encoded in original if kind != b"IDAT"]
            != [encoded for kind, _, encoded in optimized if kind != b"IDAT"]):
        raise ValueError("PNG metadata changed: " + str(path))
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", original[0][1])
    result = {
        "path": path.relative_to(BASE).as_posix(),
        "before_bytes": len(before),
        "after_bytes": min(len(before), len(candidate)),
        "width": width,
        "height": height,
        "bit_depth": depth,
        "color_type": color,
        "interlace": interlace,
        "scanline_sha256": hashlib.sha256(raw).hexdigest(),
        "exact_scanlines_and_metadata": True,
        "changed": len(candidate) < len(before),
    }
    if result["changed"] and not dry_run:
        # The temporary file is on the same volume so replacement is atomic.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".png-recompress-",
                                             suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(candidate)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=BASE / "public")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    paths = sorted(args.root.resolve().rglob("*.png"))
    if args.workers < 1:
        parser.error("--workers must be positive")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        # Record the source sizes before starting so an interrupted run can
        # still be audited, even if some atomic replacements have completed.
        args.report.with_suffix(".before.json").write_text(
            json.dumps({path.relative_to(BASE).as_posix(): path.stat().st_size
                        for path in paths}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(optimize, str(path), args.dry_run): path for path in paths}
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            verification = result.get("skipped", "exact scanlines + metadata")
            print(f"{result['path']}: {result['before_bytes']:,} -> "
                  f"{result['after_bytes']:,} bytes; {verification}", flush=True)
    results.sort(key=lambda result: result["path"])
    before = sum(result["before_bytes"] for result in results)
    after = sum(result["after_bytes"] for result in results)
    report = {
        "method": "zlib level 9; exact PNG scanlines and all non-IDAT chunks preserved",
        "dry_run": args.dry_run,
        "files_checked": len(results),
        "files_skipped": sum("skipped" in result for result in results),
        "files_improved": sum(result["changed"] for result in results),
        "before_bytes": before,
        "after_bytes": after,
        "saved_bytes": before - after,
        "files": results,
    }
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(f"Checked {len(results)} image files: {before:,} -> {after:,} bytes "
          f"({before - after:,} bytes saved).", flush=True)


if __name__ == "__main__":
    main()
