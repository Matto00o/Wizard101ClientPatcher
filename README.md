# Wizard101 Camera Zoom Patcher

A simple tool to increase the maximum camera distance in **Wizard101**.

Wizard101 has a relatively low default maximum camera distance. This tool allows you to increase it to a value of your choice, making it possible to zoom the camera further away from the player.

It can also adjust the **mouse-wheel zoom speed**.

## Features

* Increase or decrease the maximum camera distance
* Customize mouse-wheel zoom speed
* Automatically find the Wizard101 installation directory
* Supports multiple common installation locations
* Simple GUI
* Command-line support
* Automatically creates a backup of the original game executable
* Restore the original game values at any time
* Standalone Windows executable — Python is not required

## Usage

### GUI

Run `W101CameraZoomPatcher.exe` without any arguments.

The tool will automatically look for the Wizard101 installation in several common locations.

You can then choose:

* **Maximum camera distance**
* **Zoom speed**

The default values are:

| Setting                 | Original | Default patch |
| ----------------------- | -------: | ------------: |
| Maximum camera distance |      425 |           800 |
| Zoom divisor            |      3.5 |           3.5 |

For the zoom divisor, a **lower value makes the mouse-wheel zoom faster**, while a **higher value makes it slower**.

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
python w101_camzoom_patch.py WizardGraphicalClient.exe
```

Set a custom maximum camera distance:

```bash
python w101_camzoom_patch.py WizardGraphicalClient.exe --max 1000
```

Perform a dry run without modifying the game:

```bash
python w101_camzoom_patch.py WizardGraphicalClient.exe --dry-run
```

Restore the original Wizard101 values:

```bash
python w101_camzoom_patch.py WizardGraphicalClient.exe --restore
```

The same options are available when using the standalone `.exe`.

## Backup

Before modifying the game, the patcher automatically creates a backup of the original `WizardGraphicalClient.exe`.

This backup can be used to restore the original executable if needed.

## Game Updates

Wizard101 updates may replace `WizardGraphicalClient.exe` with a new version.

If this happens, the camera zoom modification may be overwritten and the game will return to its original zoom settings.

Simply run the patcher again after the game has finished updating.

## Download

Download the latest version from the **[Releases](../../releases)** page.

The standalone executable does not require Python or any additional dependencies.

## Antivirus Warnings

Some antivirus programs may flag small utilities like this as suspicious, especially when distributed as a standalone executable.

The patcher modifies the Wizard101 game executable, so security software may also react to its behavior.

If you are unsure about a downloaded release, you can verify its SHA-256 hash against the hash published with the release.

## Compatibility

The patcher is intended for the Windows version of Wizard101.

Game updates may require an updated version of the patcher. If the game executable has changed significantly, the patcher may refuse to modify it rather than applying an incorrect patch.

## Disclaimer

This is an unofficial third-party tool for Wizard101.

It is not affiliated with, endorsed by, or sponsored by KingsIsle Entertainment.

Use it at your own risk. Always keep a backup of your original game files.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
