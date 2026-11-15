# name_editor.py
# Full script: decode -> replace "Shaab ji" -> re-encode
# DOES NOT EXECUTE the payload.

import base64
import marshal
import re
import sys
import zlib
from pathlib import Path

SRC = Path("old1_.py")
OUT = Path("old1_updated.py")

OLD_NAME = "Shaab ji"
NEW_NAME = "YOUR_NEW_NAME_HERE"   # <-- yahan naya naam daalo


# ------------------------------------------------------------------
# 1. Recursively replace string/bytes constants inside code object
# ------------------------------------------------------------------
def replace_in_code(code, old, new, log):
    changed = False
    new_consts = []

    for c in code.co_consts:
        # string match
        if isinstance(c, str) and c == old:
            log.append(f"  [str ] {old!r} -> {new!r}")
            c = new
            changed = True

        # bytes match
        elif isinstance(c, bytes) and c == old.encode():
            log.append(f"  [byte] {old!r} -> {new!r}")
            c = new.encode()
            changed = True

        # nested code object -> recurse
        elif hasattr(c, "co_consts"):
            c2, ch = replace_in_code(c, old, new, log)
            if ch:
                c = c2
                changed = True

        new_consts.append(c)

    if changed:
        return code.replace(co_consts=tuple(new_consts)), True
    return code, False


# ------------------------------------------------------------------
# 2. Extract the encoded payload from the source text
# ------------------------------------------------------------------
PAYLOAD_RE = re.compile(r"exec\(\(_\)\(b'([0-9A-Fa-f]+)'\)\)")


def extract_payload(text):
    m = PAYLOAD_RE.search(text)
    if not m:
        raise SystemExit("Could not find payload in source.")
    return m


# ------------------------------------------------------------------
# 3. Decode / encode helpers (matches the loader exactly)
# ------------------------------------------------------------------
def decode_payload(hex_str):
    # loader does: zlib.decompress(base64.b16decode(hex[::-1]))
    return zlib.decompress(base64.b16decode(hex_str[::-1]))


def encode_payload(raw):
    # reverse of above
    return base64.b16encode(zlib.compress(raw))[::-1].decode()


# ------------------------------------------------------------------
# 4. Main
# ------------------------------------------------------------------
def main():
    if not SRC.exists():
        raise SystemExit(f"File not found: {SRC}")

    if NEW_NAME == "YOUR_NEW_NAME_HERE":
        raise SystemExit("Please set NEW_NAME to the name you want.")

    print(f"[*] Reading {SRC} ...")
    text = SRC.read_text(encoding="utf-8")

    m = extract_payload(text)
    hex_str = m.group(1)
    print(f"[*] Payload length: {len(hex_str)} hex chars")

    print("[*] Decoding ...")
    try:
        raw = decode_payload(hex_str)
    except Exception as e:
        raise SystemExit(
            f"Decode failed: {e}\n"
            f"Try running with the same Python version used to build the file "
            f"(current = {sys.version.split()[0]})."
        )

    print("[*] Unmarshalling ...")
    try:
        code = marshal.loads(raw)
    except Exception as e:
        raise SystemExit(
            f"marshal.loads failed: {e}\n"
            f"marshal is Python-version specific. "
            f"Use the same Python version as the original file."
        )

    print(f"[*] Searching for {OLD_NAME!r} in code constants ...")
    log = []
    new_code, changed = replace_in_code(code, OLD_NAME, NEW_NAME, log)

    if not changed:
        print("[!] Exact name not found. Showing all short strings "
              "to help you find the real spelling:\n")
        dump_strings(code, maxlen=40)
        raise SystemExit("Nothing replaced.")

    for line in log:
        print(line)

    print("[*] Re-encoding ...")
    new_raw = marshal.dumps(new_code)
    new_hex = encode_payload(new_raw)

    new_text = text[:m.start(1)] + new_hex + text[m.end(1):]
    OUT.write_text(new_text, encoding="utf-8")

    print(f"[+] Done. Saved: {OUT}")
    print(f"    Old size: {len(text)} bytes")
    print(f"    New size: {len(new_text)} bytes")


# ------------------------------------------------------------------
# Debug helper: print every string constant (for when name isn't found)
# ------------------------------------------------------------------
def dump_strings(code, maxlen=40, depth=0):
    for c in code.co_consts:
        if isinstance(c, str) and 0 < len(c) <= maxlen:
            print("  " * depth + repr(c))
        elif hasattr(c, "co_consts"):
            print("  " * depth + f"<code {c.co_name}>")
            dump_strings(c, maxlen, depth + 1)


if __name__ == "__main__":
    main()
