> **Note:** This project was created with the help of **AI** using [**Cursor**](https://cursor.com/). Human judgment still applies; the disclosure is here for anyone who wants to know how the code came together.

> *Third-party:* This is an independent tool and is not officially affiliated with the [Open WebUI](https://github.com/open-webui/open-webui) project.

# Open WebUI Systray

![Screenshot of Open WebUI Systray](screenshot.png)

Small **Windows** tray application that opens an **[Open WebUI](https://github.com/open-webui/open-webui)** (or any **HTTPS**) instance inside an embedded **WebView2** browser. Run it, park it in the system tray, and show or hide the window from the icon.

## Requirements

- **Windows** (WinForms + WebView2)
- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)

## Build

From the repository root:

```powershell
.\build-release.ps1
```

Or manually:

```powershell
dotnet build .\open-webui-systray.csproj -c Release
```

The executable is produced under `bin\Release\net8.0-windows\` (e.g. `open-webui-systray.exe`).

## Run

After a Release build:

```powershell
.\run-release.ps1
```

That starts the newest `.exe` in the Release output folder with the correct working directory (so config and WebView2 data resolve next to the binary).

## Configuration

On first run (or if no valid config exists), a dialog asks for the **HTTPS URL** of your server (for example your Open WebUI URL).

Settings are stored next to the executable in **`open-webui-systray.cfg`**: one non-comment line with the HTTPS URL. Lines starting with `#` are ignored.

Only **https://** URLs with a host are accepted.

## Behavior

- **Single instance** - starting a second copy exits immediately.
- **Tray icon** - left-click shows or focuses the browser window; **Quit** is in the tray context menu.
- **Global shortcut** - **Ctrl+Alt+O** toggles show or hide (same as tray left-click). If that hotkey is already registered by another program, this app does not register it for the session.
- **Close button** - hides the window to the tray (does not exit the app).
- **WebView2 user data** - stored under `WebView2Data\` beside the executable (cookies, cache, etc.).

## Project layout

- `open-webui-systray.csproj` - .NET 8 WinExe project
- `Program.cs`, `Startup.cs`, `AppConfig.cs` - entry, URL resolution, config
- `GlobalHotkeyWindow.cs` - global Ctrl+Alt+O hotkey (message-only window)
- `TrayApplicationContext.cs` - tray icon and menu
- `MainForm.cs` - WebView2 host window

## License

This project is released under the [MIT License](LICENSE). You may use, copy, modify, and distribute it subject to that license. The embedded [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) runtime is subject to Microsoft’s terms.
