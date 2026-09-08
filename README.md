# Wizard101 Client Patcher

A small patcher for the **Wizard101** client. It can:

* **Raise the maximum camera zoom distance.** Wizard101 caps how far the camera
  can pull back; this raises the limit to a value of your choice.
* **Change the mouse-wheel zoom speed**, to taste.
* **Unlock the hidden languages. (only text for now)** Greek, Italian and Polish ship with the
  client but are never listed in the settings screen. (!IMPORTANT: this function was made
  and tested on the North American game version. I have not tried it on the EU version,
  but it probably will NOT work.)

Every change is optional and fully reversible from the automatic backup.

## Features

* Increase or decrease the maximum camera distance
* Customize mouse-wheel zoom speed
* Unlock the hidden languages in the settings screen (Greek, Italian, Polish, only text)
* Automatically find the Wizard101 installation directory
* Supports multiple common installation locations
* A simple GUI
* Command-line support
* Automatically creates a backup of the original game executable
* Restore the original game values at any time

## Usage

### GUI

Run `W101ClientPatcher.exe` without any arguments.

The tool will automatically look for the Wizard101 installation in several common locations.

You can then choose:

* **Maximum camera distance**
* **Zoom speed**
* **Unlock hidden languages** (checkbox, off by default)

The default values are:

| Setting                 |  Original | Default patch |
| ----------------------- | --------: | ------------: |
| Maximum camera distance |       425 |           800 |
| Zoom divisor            |       3.5 |           3.5 |

For the zoom divisor, a **lower value makes the mouse-wheel zoom faster**, while a **higher value makes it slower**.

The language unlock is **off by default**: it only happens if you tick the checkbox.

### Running on Linux

The only file published on the Releases page is a Windows `.exe`, but that is
not a problem on Linux. Wizard101 already runs inside a Wine prefix there, and
the patcher runs in exactly the same place: from **Lutris**, use the option that
runs an executable inside the game's Wine prefix and point it at
`W101ClientPatcher.exe`. This is tested and works.

Running it inside the prefix is also the easier route, because the Windows
install paths the patcher looks for — `C:\ProgramData\KingsIsle Entertainment\...`
and friends — resolve to the prefix's `drive_c`, so the game is detected
automatically just like on Windows.

Make sure you use the **same prefix** the game is installed in, otherwise the
patcher will not find it and you will have to browse to
`WizardGraphicalClient.exe` yourself.

#### Without Lutris: run it natively

Wine is only needed to run the prebuilt `.exe`, not to patch the game. The
patcher just reads and writes a file, so you can skip the prefix entirely and
run it natively on Linux — either the Python script, or a Linux build of the
patcher if one is published with the release.

Automatic detection works here too: when there is no `C:` drive to probe, the
patcher looks inside the usual Wine and Proton prefixes instead — `~/Games`,
`~/.wine`, the Lutris prefix directory (including the Flatpak one) and Steam's
`compatdata` — for the same layout Windows would have under `drive_c`.

If your prefix lives somewhere unusual, pass the path yourself:

```bash
python w101_patch.py ~/Games/Wizard101NA/prefix/drive_c/"ProgramData/KingsIsle Entertainment/Wizard101/Bin/WizardGraphicalClient.exe" --languages
```

Note where the quotes go: the `~` has to stay outside them or the shell will
not expand it, while the spaces inside the path do need quoting.

One thing still differs from running the `.exe` in the prefix: Python 3 alone is
enough for the command line, with no extra dependencies, but the GUI also needs
tkinter — `python3-tkinter` on Fedora, `python3-tk` on Debian and Ubuntu.
Without it the script says so and you can still use every option from the
command line.

See [Command Line](#command-line) below for the full list of options.

### Selecting the game executable manually

If you choose the game executable manually, make sure to select:

```text
WizardGraphicalClient.exe
```

**Do not select `Wizard101.exe`.**

The patcher modifies `WizardGraphicalClient.exe`, and selecting `Wizard101.exe` will not work.

### Command Line

Patch the game using the default settings:

```bash
python w101_patch.py WizardGraphicalClient.exe
```

Set a custom maximum camera distance:

```bash
python w101_patch.py WizardGraphicalClient.exe --max 1000
```

Also unlock the hidden languages:

```bash
python w101_patch.py WizardGraphicalClient.exe --languages
```

Perform a dry run without modifying the game:

```bash
python w101_patch.py WizardGraphicalClient.exe --dry-run
```

Change the mouse-wheel zoom speed (lower is faster):

```bash
python w101_patch.py WizardGraphicalClient.exe --speed 2.5
```

Restore the original executable from the backup:

```bash
python w101_patch.py WizardGraphicalClient.exe --restore
```

The same options are available when using the standalone `.exe`.

#### All options

| Option        | Effect                                                                 |
| ------------- | ---------------------------------------------------------------------- |
| `--max N`     | New maximum camera distance (default 800, stock 425)                    |
| `--speed N`   | Zoom speed divisor; lower is faster (stock 3.5, left alone if omitted)  |
| `--languages` | Also unlock the hidden languages (Greek, Italian, Polish)               |
| `--dry-run`   | Show what would change without writing anything                         |
| `--force`     | Proceed even if the constants do not hold their stock value             |
| `--restore`   | Restore the executable from its `.bak` backup and exit                  |
| `--gui`       | Open the graphical interface                                            |

Options combine freely — `--max 1000 --speed 2.5 --languages` applies all three
in a single pass. Running the patcher again is safe: anything already at the
requested value is reported and skipped.

To unlock only the languages and leave the camera at its stock value, pass the
stock maximum explicitly:

```bash
python w101_patch.py WizardGraphicalClient.exe --max 425 --languages
```

## Hidden Languages

Wizard101 shipped with seven languages, but now the 
settings tab only lists four of them. Greek, Italian and
Polish are present in the client and never shown.

With the language option enabled, all seven show up in that dropdown and the
arrow buttons cycle through them as usual. Pick the one you want like any other
setting; the choice is remembered between sessions.

This only enables text translations, as the dubs for the three missing languages
are not present in the game files. I'm still not sure if it's possible to 
somehow add dubs as well.

This is off by default: pass `--languages` on the command line, or tick
**Unlock hidden languages** in the GUI.

## Backup

Before modifying the game, the patcher automatically creates a backup of the
original `WizardGraphicalClient.exe` next to it, as `WizardGraphicalClient.exe.bak`.

There is a single backup for the whole executable, so `--restore` puts back the
untouched file and reverts **every** patch at once — camera, zoom speed and
languages together. There is no way to undo just one of them; to change your
mind about a single setting, restore and re-run the patcher with the options you
want.

> **After a game update, delete the old `.bak` first.**
> An existing backup is never overwritten. If the game updates the executable
> and you patch the new one, the `.bak` still holds the *previous* version, and
> restoring it would put back an outdated client that the server will refuse.
> Deleting the stale `.bak` before patching makes the next backup match the
> version you are actually running.

## Game Updates

Wizard101 enforces mandatory updates — the server refuses a client that is out
of sync — and updates replace `WizardGraphicalClient.exe` with a new version.

When that happens the patches are overwritten and the game returns to its
original settings. Simply run the patcher again after the game has finished
updating. The patcher is built to keep working across game versions, so an
update does not normally require a new release of this tool.

The launcher also restores the original files, so once the game is patched,
start it from a shortcut that points **directly at
`WizardGraphicalClient.exe`** instead of going through the launcher. Run the
launcher when you actually need to update, then re-apply the patches.

## Download

Download the latest version from the **[Releases](../../releases)** page.

The standalone executable does not require Python or any additional
dependencies. Only the Windows `.exe` is published; on Linux, run that same file
inside the game's Wine prefix — see [Running on Linux](#running-on-linux).

## Building from source

The release executable is produced with [PyInstaller](https://pyinstaller.org)
from the included spec file:

```bash
pyinstaller W101ClientPatcher.spec
```

Two things to know before building:

* **PyInstaller does not cross-compile.** It bundles the interpreter of the
  machine it runs on: the same spec file produces a Windows `.exe` when run on
  Windows and a native Linux binary when run on Linux, so each platform's build
  has to be made on that platform.
* **tkinter must be present at build time**, otherwise the GUI is silently left
  out and the result only works from the command line. The official Windows
  Python includes it; on Linux it is usually a separate package, such as
  `python3-tkinter` on Fedora or `python3-tk` on Debian and Ubuntu.

The script itself has no dependencies beyond the standard library, so running it
with `python w101_patch.py` needs no installation at all.

## Antivirus Warnings

Some antivirus programs may flag small utilities like this as suspicious, especially when distributed as a standalone executable.

The patcher modifies the Wizard101 game executable, so security software may also react to its behavior.

If you are unsure about a downloaded release, you can verify its SHA-256 hash against the hash published with the release.

## Compatibility

The patcher is intended for both the Steam and standalone versions of the game.

It targets the Windows build of `WizardGraphicalClient.exe` and reads and writes
that file directly, so the Python script runs anywhere Python does — including
Linux, where it patches a Wizard101 installed under Wine or Proton just as well.
The prebuilt release is a Windows executable.

Automatic detection probes the usual Windows install paths. Those resolve
normally when the patcher itself runs inside the Wine prefix, so detection works
there; running the Python script natively on Linux means selecting
`WizardGraphicalClient.exe` yourself.

Game updates may require an updated version of the patcher. If the game
executable has changed significantly, the patcher refuses to modify it rather
than applying an incorrect patch.

## Disclaimer

This is an unofficial third-party tool for Wizard101.

It is not affiliated with, endorsed by, or sponsored by KingsIsle Entertainment.

Use it at your own risk. Always keep a backup of your original game files.

## License

This project is licensed under the MIT License.
