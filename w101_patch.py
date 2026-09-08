#!/usr/bin/env python3
"""
w101_patch.py

Raises the maximum camera distance in Wizard101 (WizardGraphicalClient.exe).

The code looks for the camera zoom clamp searching by pattern
which should make this fix compatible with different versions
of the game.
Once found, it simply overrides the MAX zoom constant with the value
chosen by the user. Default value is 425, default NEW value is 800.
It's also possible to modify the mouse wheel speed divisor to make
zoom faster/slower, default value is 3.5. Higher number makes zoom slower.

Optionally it can also unlock the languages that the settings screen
hides (Greek, Italian and Polish) -- see LANGUAGE UNLOCK below.

Run with no arguments for a small GUI, or from the command line:

    python w101_patch.py WizardGraphicalClient.exe
    python w101_patch.py WizardGraphicalClient.exe --max 1000
    python w101_patch.py WizardGraphicalClient.exe --languages
    python w101_patch.py WizardGraphicalClient.exe --dry-run
    python w101_patch.py WizardGraphicalClient.exe --restore

NOTE ON GAME UPDATES
--------------------
Wizard101 forces clients to update -- the server refuses a client that
is out of sync -- and the launcher restores the original files, so every
patch here has to be re-applied after an update and the client has to be
started from a shortcut that goes straight to the executable instead of
through the launcher. That is also why every constant is located by
pattern matching rather than by a hardcoded offset.
"""

import argparse
import os
import shutil
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Known game values
# ---------------------------------------------------------------------------

VANILLA_MAX = 425.0      # stock maximum camera distance
VANILLA_MIN = 175.0      # stock minimum camera distance (left untouched)
DEFAULT_NEW_MAX = 800.0
FLOAT_TOL = 0.01

# Zoom clamp pattern.
#
#   F3 0F 10 05 ........   MOVSS  XMM0, [rip+X]      X = max threshold (425.0)
#   0F 2F C1               COMISS XMM0, XMM1
#   76 ..                  JBE    -> clamp-to-max branch
#   48 8D 05 ........      LEA    RAX, [rip+Y]       Y = min value (175.0)
#   0F 2F 0D ........      COMISS XMM1, [rip+Z]      Z = min threshold (175.0)
#   48 0F 47 C1            CMOVA  RAX, RCX
#   EB ..                  JMP    -> join point
#
CLAMP_PATTERN = (
    "F3 0F 10 05 ?? ?? ?? ?? 0F 2F C1 76 ?? "
    "48 8D 05 ?? ?? ?? ?? 0F 2F 0D ?? ?? ?? ?? "
    "48 0F 47 C1 EB ??"
)
CLAMP_ANCHOR = bytes.fromhex("480F47C1")   # CMOVA RAX,RCX -- rare, good anchor
CLAMP_ANCHOR_IDX = 27                      # anchor position inside the pattern

# Branch taken by the JBE: loads the max value and stores it.
#
#   48 8D 05 ........      LEA    RAX, [rip+W]       W = max value (425.0)
#   F3 0F 10 10            MOVSS  XMM2, [RAX]
#   F3 0F 11 11            MOVSS  [RCX], XMM2
#
MAXBRANCH_PATTERN = "48 8D 05 ?? ?? ?? ?? F3 0F 10 10 F3 0F 11 11"

# Optional: zoom speed.
#
#   0F 5B C0               CVTDQ2PS XMM0, XMM0       wheel delta int -> float
#   F3 0F 5E 05 ........   DIVSS    XMM0, [rip+S]    S = divisor (3.5)
#
SPEED_PATTERN = "0F 5B C0 F3 0F 5E 05 ?? ?? ?? ??"
VANILLA_SPEED_DIV = 3.5

# ---------------------------------------------------------------------------
# LANGUAGE UNLOCK
# ---------------------------------------------------------------------------
#
# SettingsWindow builds the language dropdown on the advanced-gameplay tab by
# appending a fixed number of entries from the global locale array:
#
#     array index:  0 INVALID  1 en-US  2 fr  3 de  4 es  5 el  6 it  7 pl
#
# The array holds eight elements, INVALID sits at index 0 and the loop starts
# at 1, but it only adds four entries -- which is exactly why Greek, Italian
# and Polish never show up. MSVC compiled the counter as an offset from the
# array stride:
#
#     bb 20 00 00 00    MOV  EBX, 0x20         ; stride, and start index 1
#     44 8d 6b e4       LEA  R13D, [RBX-0x1c]  ; 0x20 - 0x1c = 4 entries
#
# Changing the displacement from -0x1c (E4) to -0x19 (E7) gives 0x20 - 0x19 =
# 7, so all seven real languages are listed. Index 0 (INVALID) is still never
# reached because the loop keeps starting at 1, and the arrow buttons cycle
# over however many entries were added, so nothing else needs touching.
#
# That is the whole patch: one byte.
#
# Known limitation: the chosen language is not written to preferences.xml,
# state.dat or the Wine registry, yet the choice does survive -- where it is
# persisted has not been tracked down.
#
LANG_PATTERN = bytes.fromhex("bb20000000448d6be4")
LANG_DISP_INDEX = 8        # position of the displacement byte within the pattern
LANG_OLD_DISP = 0xE4       # -0x1c -> 4 entries
LANG_NEW_DISP = 0xE7       # -0x19 -> 7 entries
LANG_STRIDE = 0x20         # sizeof(std::string), also the starting offset
LANGUAGES = ["INVALID", "en-US", "fr", "de", "es", "el", "it", "pl"]
LANG_UNLOCKED = "Greek, Italian and Polish"

# Where the game usually sits, relative to the root of a Windows drive.
GAME_SUBPATHS = [
    ("ProgramData", "KingsIsle Entertainment", "Wizard101", "Bin",
     "WizardGraphicalClient.exe"),
    ("Program Files (x86)", "Steam", "steamapps", "common", "Wizard101", "Bin",
     "WizardGraphicalClient.exe"),
    ("Program Files", "KingsIsle Entertainment", "Wizard101", "Bin",
     "WizardGraphicalClient.exe"),
]

# Running natively on Linux there is no C: drive to probe, so look inside the
# usual Wine and Proton prefixes instead -- the layout under drive_c is the
# same one Windows would have.
PREFIX_GLOBS = [
    "Games/*/drive_c",
    "Games/*/prefix/drive_c",
    "Games/*/*/drive_c",
    ".wine/drive_c",
    ".local/share/lutris/prefixes/*/drive_c",
    ".var/app/net.lutris.Lutris/data/lutris/prefixes/*/drive_c",
    ".local/share/Steam/steamapps/compatdata/*/pfx/drive_c",
    ".steam/steam/steamapps/compatdata/*/pfx/drive_c",
    ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c",
]


def drive_roots():
    """Yield the directories that stand in for a Windows drive root."""
    if os.name == "nt":
        yield Path("C:/")
        return
    home = Path.home()
    for pattern in PREFIX_GLOBS:
        yield from sorted(home.glob(pattern))


def find_game_paths():
    """Every game executable found in a usual install location."""
    hits = []
    for root in drive_roots():
        for parts in GAME_SUBPATHS:
            candidate = root.joinpath(*parts)
            if candidate.is_file() and candidate not in hits:
                hits.append(candidate)
    return hits


# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------

def parse_pattern(text):
    """'F3 0F ?? 05' -> [0xF3, 0x0F, None, 0x05]"""
    return [None if tok == "??" else int(tok, 16) for tok in text.split()]


def match_at(data, off, pattern):
    if off < 0 or off + len(pattern) > len(data):
        return False
    for i, b in enumerate(pattern):
        if b is not None and data[off + i] != b:
            return False
    return True


def find_all(data, pattern, anchor, anchor_idx):
    """Find every occurrence of the pattern, using the anchor as a fast filter."""
    hits = []
    pos = 0
    while True:
        pos = data.find(anchor, pos)
        if pos == -1:
            return hits
        start = pos - anchor_idx
        if match_at(data, start, pattern):
            hits.append(start)
        pos += 1


def find_backwards(data, pattern, end_off, window):
    """Search for the pattern within the `window` bytes preceding end_off."""
    start = max(0, end_off - window)
    for off in range(end_off, start - 1, -1):
        if match_at(data, off, pattern):
            return off
    return None


# ---------------------------------------------------------------------------
# Minimal PE parsing (only needed for VA <-> file offset conversion)
# ---------------------------------------------------------------------------

class PEFile:
    def __init__(self, data):
        if data[:2] != b"MZ":
            raise ValueError("Not a Windows executable (missing MZ signature).")
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise ValueError("Invalid PE header.")

        coff = e_lfanew + 4
        num_sections = struct.unpack_from("<H", data, coff + 2)[0]
        size_opt = struct.unpack_from("<H", data, coff + 16)[0]

        opt = coff + 20
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic == 0x20B:          # PE32+
            self.image_base = struct.unpack_from("<Q", data, opt + 24)[0]
        elif magic == 0x10B:        # PE32
            self.image_base = struct.unpack_from("<I", data, opt + 28)[0]
        else:
            raise ValueError(f"Unknown optional header magic: {magic:#x}")

        sec_table = opt + size_opt
        self.sections = []
        for i in range(num_sections):
            o = sec_table + i * 40
            name = data[o:o + 8].rstrip(b"\0").decode("latin-1")
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
            self.sections.append({
                "name": name, "vaddr": vaddr, "vsize": vsize,
                "rawptr": rawptr, "rawsize": rawsize,
            })

    def va_to_off(self, va):
        rva = va - self.image_base
        for s in self.sections:
            size = max(s["vsize"], s["rawsize"])
            if s["vaddr"] <= rva < s["vaddr"] + size:
                delta = rva - s["vaddr"]
                if delta >= s["rawsize"]:
                    raise ValueError(f"VA {va:#x} falls in a region not present in the file.")
                return s["rawptr"] + delta
        raise ValueError(f"VA {va:#x} is outside every section.")

    def off_to_va(self, off):
        for s in self.sections:
            if s["rawsize"] and s["rawptr"] <= off < s["rawptr"] + s["rawsize"]:
                return self.image_base + s["vaddr"] + (off - s["rawptr"])
        raise ValueError(f"File offset {off:#x} is outside every section.")


def rip_target(pe, data, disp_off, insn_end_off):
    """Resolve a RIP-relative operand to a virtual address."""
    disp = struct.unpack_from("<i", data, disp_off)[0]
    return pe.off_to_va(insn_end_off) + disp


def read_f32(data, off):
    return struct.unpack_from("<f", data, off)[0]


# ---------------------------------------------------------------------------
# Constant location
# ---------------------------------------------------------------------------

def locate(pe, data):
    """Return a dict of {role: (virtual_address, file_offset)}."""
    hits = find_all(data, parse_pattern(CLAMP_PATTERN), CLAMP_ANCHOR, CLAMP_ANCHOR_IDX)

    if not hits:
        raise RuntimeError(
            "Zoom clamp pattern not found. The executable may be from a very "
            "different version, already modified, or not the game client at all."
        )
    if len(hits) > 1:
        raise RuntimeError(
            f"Found {len(hits)} matches for the pattern -- ambiguous, aborting.\n"
            "Offsets: " + ", ".join(f"{h:#x}" for h in hits)
        )

    m = hits[0]
    found = {"clamp_va": pe.off_to_va(m)}

    # max threshold: MOVSS XMM0,[rip+X]   (instruction spans m .. m+8)
    va = rip_target(pe, data, m + 4, m + 8)
    found["max_threshold"] = (va, pe.va_to_off(va))

    # min value: LEA RAX,[rip+Y]          (instruction spans m+13 .. m+20)
    va = rip_target(pe, data, m + 16, m + 20)
    found["min_value"] = (va, pe.va_to_off(va))

    # min threshold: COMISS XMM1,[rip+Z]  (instruction spans m+20 .. m+27)
    va = rip_target(pe, data, m + 23, m + 27)
    found["min_threshold"] = (va, pe.va_to_off(va))

    # clamp-to-max branch, reached by the JBE at m+11 (2 bytes, signed disp8)
    jbe_disp = struct.unpack_from("<b", data, m + 12)[0]
    branch_off = m + 13 + jbe_disp
    if not match_at(data, branch_off, parse_pattern(MAXBRANCH_PATTERN)):
        raise RuntimeError(
            f"The clamp-to-max branch at {pe.off_to_va(branch_off):#x} "
            "does not have the expected shape."
        )
    va = rip_target(pe, data, branch_off + 3, branch_off + 7)
    found["max_value"] = (va, pe.va_to_off(va))

    # optional: zoom speed divisor, shortly before the clamp
    speed_off = find_backwards(data, parse_pattern(SPEED_PATTERN), m, 128)
    if speed_off is not None:
        va = rip_target(pe, data, speed_off + 7, speed_off + 11)
        found["speed_div"] = (va, pe.va_to_off(va))

    return found


def lang_entries_for(disp):
    """Decode a signed disp8 into the resulting entry count."""
    signed = disp - 256 if disp > 127 else disp
    return LANG_STRIDE + signed


def find_lang_sites(data, disp):
    """Offsets of the displacement byte for every match with that value."""
    needle = LANG_PATTERN[:LANG_DISP_INDEX] + bytes([disp])
    sites, pos = [], 0
    while True:
        pos = data.find(needle, pos)
        if pos == -1:
            return sites
        sites.append(pos + LANG_DISP_INDEX)
        pos += 1


def locate_language(data):
    """Return (file_offset, current_disp) for the language entry counter."""
    for disp in (LANG_OLD_DISP, LANG_NEW_DISP):
        sites = find_lang_sites(data, disp)
        if len(sites) > 1:
            raise RuntimeError(
                f"Found {len(sites)} matches for the language counter -- "
                "ambiguous, aborting.\nOffsets: "
                + ", ".join(f"{h:#x}" for h in sites)
            )
        if sites:
            return sites[0], disp
    raise RuntimeError(
        "Language counter pattern not found. The executable may be from a "
        "very different version, already modified, or not the game client "
        "at all."
    )


# ---------------------------------------------------------------------------
# Core operations (shared by CLI and GUI)
# ---------------------------------------------------------------------------

REPORT_ORDER = ["max_threshold", "max_value", "min_threshold", "min_value", "speed_div"]


def run_patch(exe, new_max=DEFAULT_NEW_MAX, speed=None, languages=False,
              dry_run=False, force=False, log=print, summary=None):
    """Analyze and optionally patch the executable. Returns True on success.

    If `summary` is a dict, it is filled in with what actually happened
    (as opposed to what was requested), so a caller can report the real
    outcome instead of echoing back its own arguments:

        camera_changed, old_max     -- max distance did / would change
        speed_changed, old_speed    -- speed divisor did / would change
        languages_changed           -- language count did / would change
        languages_already_unlocked  -- languages were requested but already unlocked
        backup_created               -- a new .bak was written this run
    """
    if summary is not None:
        summary.clear()
        summary.update(camera_changed=False, old_max=None,
                        speed_changed=False, old_speed=None,
                        languages_changed=False, languages_already_unlocked=False,
                        backup_created=False)

    exe = Path(exe)
    if not exe.is_file():
        log(f"[!] File not found: {exe}")
        return False

    data = bytearray(exe.read_bytes())
    log(f"[*] File      : {exe}  ({len(data):,} bytes)")

    try:
        pe = PEFile(data)
        found = locate(pe, data)
    except (ValueError, RuntimeError) as e:
        log(f"[!] {e}")
        return False

    lang = None
    if languages:
        try:
            lang = locate_language(data)
        except RuntimeError as e:
            log(f"[!] {e}")
            log("    Nothing was written. Re-run without the language option "
                "to patch the camera only.")
            return False

    log(f"[*] ImageBase : {pe.image_base:#x}")
    log(f"[*] Clamp found at VA {found['clamp_va']:#x}")
    log("")
    log("    constant           VA            file offset    value")
    log("    " + "-" * 58)
    for key in REPORT_ORDER:
        if key in found:
            va, off = found[key]
            log(f"    {key:<17} {va:#012x}  {off:#010x}     {read_f32(data, off):g}")
    if lang is not None:
        off, disp = lang
        log(f"    {'language_count':<17} {pe.off_to_va(off):#012x}  {off:#010x}"
            f"     {lang_entries_for(disp)} entries")
    log("")

    # --- validate ---
    targets = []
    for key in ("max_threshold", "max_value"):
        va, off = found[key]
        cur = read_f32(data, off)
        if abs(cur - new_max) <= FLOAT_TOL:
            log(f"[*] {key} is already {cur:g}: nothing to do.")
            continue
        if abs(cur - VANILLA_MAX) > FLOAT_TOL and not force:
            log(f"[!] {key} is {cur:g}, expected {VANILLA_MAX:g}. "
                f"It may already be modified. Use force to proceed anyway.")
            return False
        targets.append((key, off, cur, new_max))

    for key in ("min_threshold", "min_value"):
        if key in found:
            cur = read_f32(data, found[key][1])
            if abs(cur - VANILLA_MIN) > FLOAT_TOL:
                log(f"[!] Warning: {key} is {cur:g} instead of {VANILLA_MIN:g}.")

    byte_targets = []
    if lang is not None:
        off, disp = lang
        if disp == LANG_NEW_DISP:
            log(f"[*] The language list already shows "
                f"{lang_entries_for(disp)} entries: nothing to do.")
            if summary is not None:
                summary["languages_already_unlocked"] = True
        else:
            byte_targets.append(("language_count", off, disp, LANG_NEW_DISP))

    if speed is not None:
        if "speed_div" not in found:
            log("[!] Zoom speed divisor not located: speed setting ignored.")
        elif speed <= 0:
            log("[!] Zoom speed divisor must be greater than zero.")
            return False
        else:
            off = found["speed_div"][1]
            cur = read_f32(data, off)
            if abs(cur - speed) <= FLOAT_TOL:
                log(f"[*] speed_div is already {cur:g}: nothing to do.")
            else:
                targets.append(("speed_div", off, cur, speed))

    if not targets and not byte_targets:
        log("[=] No changes needed.")
        return True

    log("[*] Pending changes:")
    for key, off, old, new in targets:
        old_b = struct.pack("<f", old).hex(" ").upper()
        new_b = struct.pack("<f", new).hex(" ").upper()
        log(f"      {key:<17} @ {off:#010x}   {old:g} -> {new:g}   [{old_b}] -> [{new_b}]")
    for key, off, old, new in byte_targets:
        log(f"      {key:<17} @ {off:#010x}   "
            f"{lang_entries_for(old)} -> {lang_entries_for(new)} entries   "
            f"[{old:02X}] -> [{new:02X}]")
    log("")

    # These changes are real whether or not they get written -- a dry run
    # reports the same "would happen" facts a real run would apply.
    was = {key: old for key, _off, old, _new in targets}
    if summary is not None:
        if was.keys() & {"max_threshold", "max_value"}:
            summary["camera_changed"] = True
            summary["old_max"] = was.get("max_threshold", was.get("max_value"))
        if "speed_div" in was:
            summary["speed_changed"] = True
            summary["old_speed"] = was["speed_div"]
        if byte_targets:
            summary["languages_changed"] = True

    if dry_run:
        log("[=] Dry run: nothing was written.")
        return True

    # --- backup ---
    backup = exe.with_suffix(exe.suffix + ".bak")
    if not backup.exists():
        try:
            shutil.copy2(exe, backup)
        except OSError as e:
            log(f"[!] Could not create backup: {e}")
            return False
        log(f"[+] Backup created: {backup.name}")
        if summary is not None:
            summary["backup_created"] = True
    else:
        log(f"[*] Backup already present: {backup.name} (not overwritten)")

    # --- write ---
    for _key, off, _old, new in targets:
        struct.pack_into("<f", data, off, new)
    for _key, off, _old, new in byte_targets:
        data[off] = new

    try:
        exe.write_bytes(bytes(data))
    except PermissionError:
        log("[!] Permission denied. Close the game and its launcher, then retry "
            "(on Windows you may need to run this as administrator).")
        return False
    except OSError as e:
        log(f"[!] Write failed: {e}")
        return False

    if was.keys() & {"max_threshold", "max_value"}:
        old_max = was.get("max_threshold", was.get("max_value"))
        log(f"[+] Done. Maximum camera distance: {old_max:g} -> {new_max:g}")
    if "speed_div" in was:
        log(f"[+] Done. Zoom speed divisor: {was['speed_div']:g} -> {speed:g}")
    if byte_targets:
        log(f"[+] Done. The settings screen now lists all "
            f"{lang_entries_for(LANG_NEW_DISP)} languages: "
            f"{', '.join(LANGUAGES[1:])}.")
    return True


def run_restore(exe, log=print):
    """Restore the executable from its .bak backup. Returns True on success."""
    exe = Path(exe)
    backup = exe.with_suffix(exe.suffix + ".bak")
    if not backup.exists():
        log(f"[!] No backup found at {backup}")
        return False
    try:
        shutil.copy2(backup, exe)
    except OSError as e:
        log(f"[!] Restore failed: {e}")
        return False
    log(f"[+] Restored {exe.name} from backup.")
    return True


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def launch_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext
    except ImportError:
        print("tkinter is not available. Use the command line instead:")
        print(f"  python {Path(sys.argv[0]).name} <path-to-exe> --max 800")
        return 1

    root = tk.Tk()
    root.title("Wizard101 Client Patcher")
    root.geometry("760x230")
    root.minsize(700, 230)

    path_var = tk.StringVar()
    max_var = tk.StringVar(value=str(int(DEFAULT_NEW_MAX)))
    speed_var = tk.StringVar()
    lang_var = tk.BooleanVar(value=False)
    force_var = tk.BooleanVar(value=False)

    found_games = find_game_paths()
    if found_games:
        path_var.set(str(found_games[0]))

    # --- file row ---
    frm_file = tk.Frame(root, padx=10, pady=8)
    frm_file.pack(fill="x")
    tk.Label(frm_file, text="Game executable:").pack(side="left")
    tk.Entry(frm_file, textvariable=path_var).pack(side="left", fill="x", expand=True, padx=6)

    def browse():
        chosen = filedialog.askopenfilename(
            title="Select WizardGraphicalClient.exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if chosen:
            path_var.set(chosen)

    tk.Button(frm_file, text="Browse...", command=browse).pack(side="left")

    # --- options row ---
    frm_opt = tk.Frame(root, padx=10)
    frm_opt.pack(fill="x")
    tk.Label(frm_opt, text=f"Max distance (stock {VANILLA_MAX:g}):").pack(side="left")
    tk.Entry(frm_opt, textvariable=max_var, width=8).pack(side="left", padx=(4, 16))
    tk.Label(frm_opt, text=f"Zoom speed divisor (stock {VANILLA_SPEED_DIV:g}, blank = leave):").pack(side="left")
    tk.Entry(frm_opt, textvariable=speed_var, width=8).pack(side="left", padx=4)

    frm_opt2 = tk.Frame(root, padx=10)
    frm_opt2.pack(fill="x", pady=(4, 0))
    tk.Checkbutton(frm_opt2,
                   text=f"Unlock hidden languages ({LANG_UNLOCKED})",
                   variable=lang_var).pack(side="left")
    tk.Checkbutton(frm_opt2, text="Force", variable=force_var).pack(side="left", padx=12)

    # --- status line (always visible) ---
    status_var = tk.StringVar(value="Select the game executable, then click Analyze or Apply patch.")
    status_lbl = tk.Label(root, textvariable=status_var, anchor="w",
                          padx=10, pady=6, fg="#333333")
    status_lbl.pack(fill="x")

    def set_status(text, ok=None):
        status_var.set(text)
        status_lbl.config(fg={True: "#1a7f37", False: "#b3261e", None: "#333333"}[ok])

    # --- buttons ---
    frm_btn = tk.Frame(root, padx=10)
    frm_btn.pack(fill="x", pady=(0, 8))

    # --- collapsible log ---
    log_frame = tk.Frame(root, padx=10)
    log_box = scrolledtext.ScrolledText(log_frame, height=18, font=("Courier New", 9))
    log_box.pack(fill="both", expand=True)
    log_visible = tk.BooleanVar(value=False)

    def set_log_visible(show):
        if show == log_visible.get():
            return
        log_visible.set(show)
        if show:
            log_frame.pack(fill="both", expand=True, pady=(0, 10))
            btn_log.config(text="Hide details")
            root.geometry("760x590")
        else:
            log_frame.pack_forget()
            btn_log.config(text="Show details")
            root.geometry("760x230")

    def log(msg=""):
        log_box.insert("end", str(msg) + "\n")
        log_box.see("end")
        root.update_idletasks()

    def read_inputs():
        """Validate the form. Returns (path, max, speed) or None."""
        path = path_var.get().strip()
        if not path:
            messagebox.showwarning("Missing file", "Select the game executable first.")
            return None
        try:
            new_max = float(max_var.get())
        except ValueError:
            messagebox.showwarning("Invalid value", "Max distance must be a number.")
            return None
        if new_max < VANILLA_MIN:
            messagebox.showwarning(
                "Invalid value",
                f"Max distance must be at least the stock minimum ({VANILLA_MIN:g}).")
            return None
        speed_text = speed_var.get().strip()
        speed = None
        if speed_text:
            try:
                speed = float(speed_text)
            except ValueError:
                messagebox.showwarning("Invalid value", "Zoom speed divisor must be a number.")
                return None
            if speed <= 0:
                messagebox.showwarning("Invalid value", "Zoom speed divisor must be positive.")
                return None
        return path, new_max, speed

    def do(dry_run):
        args = read_inputs()
        if args is None:
            return
        path, new_max, speed = args
        languages = lang_var.get()
        log_box.delete("1.0", "end")
        set_status("Working...", None)
        summary = {}
        ok = run_patch(path, new_max=new_max, speed=speed, languages=languages,
                       dry_run=dry_run, force=force_var.get(), log=log,
                       summary=summary)
        if not ok:
            set_status("Something went wrong -- see details below.", False)
            set_log_visible(True)
            return

        # Build the status line from what actually happened, not from what
        # was merely requested -- an unticked option, an already-applied
        # patch, or a no-op run must not be reported as a change.
        changes, notes = [], []
        if summary["camera_changed"]:
            verb = "would become" if dry_run else "is now"
            changes.append(f"Max distance {verb} {new_max:g} "
                           f"(was {summary['old_max']:g}).")
        if summary["speed_changed"]:
            verb = "would become" if dry_run else "is now"
            changes.append(f"Zoom speed divisor {verb} {speed:g} "
                           f"(was {summary['old_speed']:g}).")
        if summary["languages_changed"]:
            changes.append("Hidden languages would be unlocked." if dry_run
                           else "Hidden languages unlocked.")
        elif languages and summary["languages_already_unlocked"]:
            notes.append("Hidden languages were already unlocked.")

        if not changes:
            tail = (" " + " ".join(notes)) if notes else ""
            set_status("Nothing to do: the executable already matches "
                       "everything you asked for." + tail, True)
        elif dry_run:
            set_status("Looks good. Nothing was written. "
                       + " ".join(changes + notes), True)
        else:
            if summary["backup_created"]:
                notes.append("A .bak backup was saved.")
            set_status("Patched. " + " ".join(changes + notes), True)

    def do_restore():
        path = path_var.get().strip()
        if not path:
            messagebox.showwarning("Missing file", "Select the game executable first.")
            return
        if not messagebox.askyesno("Restore", "Restore the original executable from backup?"):
            return
        log_box.delete("1.0", "end")
        ok = run_restore(path, log=log)
        if ok:
            set_status("Original executable restored from backup.", True)
        else:
            set_status("Restore failed -- see details below.", False)
            set_log_visible(True)

    tk.Button(frm_btn, text="Analyze (no changes)", width=20,
              command=lambda: do(True)).pack(side="left")
    tk.Button(frm_btn, text="Apply patch", width=16,
              command=lambda: do(False)).pack(side="left", padx=8)
    tk.Button(frm_btn, text="Restore backup", width=16,
              command=do_restore).pack(side="left")
    btn_log = tk.Button(frm_btn, text="Show details", width=13,
                        command=lambda: set_log_visible(not log_visible.get()))
    btn_log.pack(side="left", padx=8)
    tk.Button(frm_btn, text="Quit", width=8, command=root.destroy).pack(side="right")

    log("Select the game executable, then run Analyze to preview the changes.")
    log("Close the game before applying the patch.")
    root.mainloop()
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) == 1:
        return launch_gui()

    ap = argparse.ArgumentParser(
        description="Raise the maximum camera distance in Wizard101."
    )
    ap.add_argument("exe", nargs="?", type=Path,
                    help="path to WizardGraphicalClient.exe")
    ap.add_argument("--gui", action="store_true", help="open the graphical interface")
    ap.add_argument("--max", type=float, default=DEFAULT_NEW_MAX,
                    help=f"new maximum distance (default {DEFAULT_NEW_MAX:g}, "
                         f"stock {VANILLA_MAX:g})")
    ap.add_argument("--speed", type=float, default=None,
                    help=f"zoom speed divisor; lower is faster (stock {VANILLA_SPEED_DIV:g})")
    ap.add_argument("--languages", action="store_true",
                    help="also unlock the languages hidden in the settings "
                         f"screen ({LANG_UNLOCKED})")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would change without writing anything")
    ap.add_argument("--force", action="store_true",
                    help="proceed even if the constants do not hold their stock value")
    ap.add_argument("--restore", action="store_true",
                    help="restore the executable from its .bak backup and exit")
    args = ap.parse_args()

    if args.gui:
        return launch_gui()
    if args.exe is None:
        ap.error("the 'exe' argument is required unless --gui is used")

    if args.restore:
        return 0 if run_restore(args.exe) else 1

    ok = run_patch(args.exe, new_max=args.max, speed=args.speed,
                   languages=args.languages,
                   dry_run=args.dry_run, force=args.force)
    if ok and not args.dry_run:
        print(f'    To undo: python {Path(sys.argv[0]).name} "{args.exe}" --restore')
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
