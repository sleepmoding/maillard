import argparse
import platform
from io import BytesIO
from pathlib import Path
from pathlib import PureWindowsPath
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

from cache import (
    loads_bytes,
    decode_header,
    decode_entries,
    read_texture_cache,
    read_texture_body,
)


if __name__ == "__main__":
    exts = Image.registered_extensions()
    supported_extensions = {ext for ext, fmt in exts.items() if fmt in Image.OPEN}

    parser = argparse.ArgumentParser(
        prog="maillard",
        description="rips texture cache from second life viewers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    paths = [Path.home()/".firestorm_x64/cache/texturecache/", Path('%LocaleAppData%\\Firestorm_x64\\'), Path.home()/"/Library/Caches/Firestorm_x64/texturecache"]
    validpaths = []

    pathflag = False
    for cpath in paths:
        if cpath.exists():
            pathflag = True
            validpaths.append(cpath)


    parser.add_argument(
        "--cache_dir", "--c", type=Path, help="path to cache directory"
    )

    parser.add_argument(
       "--out-dir", "-o", type=Path, help="path to output directory", default="./out")

    parser.add_argument(
        "--output-extension",
        "-e",
        choices=supported_extensions,
        help="output format for images. for decode only, use '.j2c'",
        default=".png",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="overwrite existing files",
        default=False,
    )
    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="don't write files", default=False
    )

    args = parser.parse_args()
    if not(args.cache_dir is None):
        if args.cache_dir.exists():
            validpaths.append(args.cache_dir)
        
    # for checkpath in paths:
    #     print(checkpath)
    #     if checkpath.exists():
    #         validpaths.append(checkpath)
    #         pathflag = True

    if not pathflag:
        # Error: No Valid cache directory
        pass
    elif pathflag and len(validpaths) > 1:
        # Prompt user for choice:
        print("Multiple valid cache paths detected - please select")
        i = 0
        for vpath in validpaths:
            print(f"[{i+1}] : {validpaths[i]}\n")
            i = i + 1
        userselect = int(input("selection: "))
        usepath = validpaths[userselect-1]
    elif pathflag:
        usepath = validpaths[0]    

    texture_entries = loads_bytes(usepath / "texture.entries")
    texture_cache = loads_bytes(usepath / "texture.cache")

    header = decode_header(texture_entries)
    # print(header)

    entries = decode_entries(texture_entries, entry_count=header["entry_count"])

    good_reads = 0
    bad_reads = 0
    skipped_reads = 0

    args.out_dir.mkdir(exist_ok=True)

    for i, entry in tqdm(
        enumerate(entries), total=header["entry_count"], unit="texture"
    ):
        uuid = entry["uuid"]
        save_path = args.out_dir / (uuid + args.output_extension)

        if save_path.exists() and not args.force:
            skipped_reads += 1
            continue

        head = read_texture_cache(texture_cache, i)
        
        body = read_texture_body(uuid, cache_dir=usepath)

        if head is None:
            bad_reads += 1
            continue

        if body is None:
            j2c_bytes = head
        else:
            j2c_bytes = head + body

        if args.output_extension == ".j2c":
            with open(save_path, "wb") as f:
                f.write(j2c_bytes)

            good_reads += 1
        else:
            try:
                with Image.open(BytesIO(j2c_bytes), formats=["jpeg2000"]) as im:
                    im.save(save_path)
            except (UnidentifiedImageError, OSError):
                bad_reads += 1

            good_reads += 1

    print(f"wrote {good_reads} cache entries")
    print(f"skipped {skipped_reads} duplicates") if skipped_reads else None
    print(f"failed to read {bad_reads} entries") if bad_reads else None
