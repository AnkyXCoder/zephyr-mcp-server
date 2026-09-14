---
name: mcuboot-image-inspector
description: Use when the user asks about a signed MCUboot image binary -- "is this image signed", "what version is this firmware", "check the mcuboot header", "why won't the bootloader accept my image", "inspect zephyr.signed.bin", "what's the image size in the header". Reads and decodes the 32-byte MCUboot image header (magic, header size, image size, flags, version) and reports each field, explicitly flagging an unsigned or unrecognized image instead of guessing.
---

# mcuboot-image-inspector

Decodes the MCUboot `image_header` at the start of a firmware binary and reports its fields: magic, load address, header size, protected TLV size, image size, flags, and version. An image whose magic does not match is reported as *not an MCUboot image*, never coerced into a plausible-looking answer.

Replaces the `zephyr_mcp` MCP tool: `analyze_image`.

## When to use

- User wants to confirm a binary was actually signed by `imgtool` / the MCUboot signing step.
- User wants the firmware version encoded in the header (for OTA/DFU bookkeeping).
- User is debugging a bootloader that rejects an image and wants the header fields checked first.
- User wants to confirm which of `zephyr.bin` / `zephyr.signed.bin` / `zephyr.signed.confirmed.bin` is the signed artifact.

## When NOT to use

- The user wants to *sign* an image (that is `imgtool sign` / the build's signing step -- say so and point at `west sign`).
- The user wants flash partition layout rather than image contents (read the devicetree `partitions` node -- use `devicetree-inspector`).
- The user wants to verify a cryptographic signature. This skill reads the header only; it does **not** verify signatures. Refuse and say plainly that signature verification requires the public key and `imgtool verify`.
- The user wants ELF/symbol/size analysis (use the toolchain's `size`/`nm`, not this skill).

## Required inputs

| Input | Type | Default |
|-------|------|---------|
| `image_path` | path to the binary to inspect | auto-detect (see below) |
| `offset` | byte offset where the header starts (non-zero for images placed in a slot dump) | `0` |
| `expect_magic` | whether to fail when the magic does not match | `false` (report, do not fail) |

## Image path resolution

Try in order, take the first that resolves:

1. Explicit `image_path`.
2. `<build_dir>/zephyr/zephyr.signed.bin` if a build directory is known or discoverable.
3. `<build_dir>/zephyr/zephyr.bin` -- but state clearly that an unsigned `zephyr.bin` normally has **no** MCUboot header, so a magic mismatch there is expected, not a defect.
4. Ask the user.

## MCUboot header layout (little-endian, 32 bytes)

From MCUboot's `bootutil/image.h` `struct image_header`. Decode exactly these fields and offsets:

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| 0x00 | 4 | `ih_magic` | expected `0x96f3b83d` |
| 0x04 | 4 | `ih_load_addr` | |
| 0x08 | 2 | `ih_hdr_size` | commonly `0x200` (512) |
| 0x0A | 2 | `ih_protect_tlv_size` | |
| 0x0C | 4 | `ih_img_size` | payload size excluding header and TLVs |
| 0x10 | 4 | `ih_flags` | see below |
| 0x14 | 1 | `iv_major` | version |
| 0x15 | 1 | `iv_minor` | |
| 0x16 | 2 | `iv_revision` | |
| 0x18 | 4 | `iv_build_num` | |
| 0x1C | 4 | `_pad1` | |

Known flag bits (report only bits you can name; list unknown bits as raw hex): `0x00000001` PIC, `0x00000004` ENCRYPTED_AES128, `0x00000008` ENCRYPTED_AES256, `0x00000010` NON_BOOTABLE, `0x00000020` RAM_LOAD.

The TLV info magic that follows the payload is `0x6907` (unprotected) / `0x6908` (protected). Only report TLV presence if you actually read those bytes at `offset + ih_hdr_size + ih_img_size`; otherwise omit the TLV line entirely.

## Procedure

1. **Verify the file.** `test -f <image_path>`; halt if absent. `stat` its size; if size < `offset + 32`, halt -- the file is too small to contain a header, and reporting fields from a short read would be fabrication.
2. **Read 32 bytes** at `offset` and unpack the fields per the layout table, little-endian (e.g. `python3 -c` with `struct.unpack("<IIHHII BBHI I", ...)`, or `xxd -s <offset> -l 32`).
3. **Check the magic.** If `ih_magic != 0x96f3b83d`, report `MCUboot header: NOT PRESENT (magic 0x<actual>)` and stop decoding the remaining fields -- their values are meaningless without a valid magic. If the path was an unsigned `zephyr.bin`, add the note that this is the expected result and point at `zephyr.signed.bin`.
4. **Sanity-check the decoded fields** against the file: `ih_hdr_size` should be >= 32 and less than the file size; `offset + ih_hdr_size + ih_img_size` should be <= file size. Report any field that fails these checks as **implausible** alongside its raw value; do not silently normalize it.
5. **Decode flags** bit by bit, naming only known bits and printing the remainder as raw hex.
6. **Optionally check TLVs**: if `offset + ih_hdr_size + ih_img_size + 2 <= file size`, read the 2-byte TLV magic there and report whether it is `0x6907`, `0x6908`, or neither.
7. **Report** with the output format below.

## Self-Validation Protocol

Every check binary; report all six.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | File exists | `test -f <image_path>` |
| 2 | File is large enough for a header | `stat` size >= `offset + 32` |
| 3 | Magic compared against the literal constant | decoded `ih_magic` compared to `0x96f3b83d`; the actual value is always printed |
| 4 | Fields decoded from real bytes | the 32 header bytes are shown as hex alongside the decoded values |
| 5 | Size arithmetic is consistent | `offset + ih_hdr_size + ih_img_size <= file size`, or the discrepancy is reported |
| 6 | No field is reported without a valid magic | when magic mismatches, only the magic and file size are reported |

If check 2 fails: halt. If check 3 fails: this is a legitimate result (unsigned image), not an error -- report it as such and stop at check 6.

## Retry policy

At most 1 retry, and only when the magic mismatches at `offset = 0` **and** the user pointed at a slot dump or full-flash image: retry once at the next plausible offset (a header-size-aligned boundary the user names, or a known slot offset from the devicetree partitions). Never scan the whole file for the magic and present the first hit as "the" header -- say what you looked at and why.

## Output format

```
mcuboot-image-inspector report:

File:    build/hello_world_nrf52840dk/zephyr/zephyr.signed.bin   (66,048 bytes)
Offset:  0x0
Header bytes: 3db8f396 00000000 0002 0000 0000fe00 00000000 01 00 0000 00000001 00000000

MCUboot header: PRESENT  (magic 0x96f3b83d)
  load_addr          0x00000000
  hdr_size           512  (0x200)
  protect_tlv_size   0
  img_size           65,024  (0xfe00)
  flags              0x00000000  (none set)
  version            1.0.0+1
  TLV magic @ 0x10000: 0x6907  (unprotected TLV area present)

Validation:
  [x] file exists:            zephyr.signed.bin
  [x] size >= header:         66048 >= 32
  [x] magic matched:          0x96f3b83d
  [x] decoded from raw bytes: shown above
  [x] size arithmetic:        0 + 512 + 65024 = 65536 <= 66048
  [x] no fields without magic: n/a (magic valid)
```

Unsigned case:

```
mcuboot-image-inspector report:

File:   build/hello_world_nrf52840dk/zephyr/zephyr.bin   (65,024 bytes)
Offset: 0x0
First 4 bytes: 0x20003000

MCUboot header: NOT PRESENT  (magic 0x20003000, expected 0x96f3b83d)
This is the expected result for an unsigned zephyr.bin -- the first word is the
initial stack pointer of the vector table. The signed artifact is normally
zephyr.signed.bin, produced by the build's signing step / `west sign`.

Remaining header fields not decoded (meaningless without a valid magic).

Validation:
  [x] file exists
  [x] size >= header
  [x] magic compared:          0x20003000 != 0x96f3b83d
  [x] decoded from raw bytes:  first word shown
  [ ] size arithmetic:         n/a (no valid header)
  [x] no fields without magic: enforced
```

## Examples

### Example 1: confirm an image is signed

User: "is zephyr.signed.bin actually signed?"

Agent reads 32 bytes at offset 0, matches magic `0x96f3b83d`, reports `hdr_size = 512`, `img_size`, flags, and version `1.0.0+1`, then checks that `hdr_size + img_size` fits inside the file and reports the TLV magic found at that boundary.

### Example 2: bootloader rejects the image

User: "MCUboot won't boot my image"

Agent inspects the header and finds `NON_BOOTABLE (0x10)` set in `ih_flags`, reporting it as a named flag bit. It does not speculate further about the bootloader's decision -- flags are what the header says; anything beyond that needs the bootloader's own log.

### Example 3: refusal on signature verification

User: "verify this image's signature is valid"

Agent refuses: reading the header proves nothing about the signature. It explains that verification needs the public key and `imgtool verify -k <key> <image>`, and offers to report the header fields instead.

## Elevator pitch (for slides)

mcuboot-image-inspector decodes the 32-byte MCUboot image header from real bytes and prints them alongside the decode, so every field is auditable. A bad magic is reported as "not an MCUboot image" -- with the actual value -- instead of being decoded into a confident-looking answer, and signature verification is explicitly out of scope rather than implied.
