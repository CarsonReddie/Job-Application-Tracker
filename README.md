# Job Tracker

A local job application tracker that runs in your browser. Data is stored locally in `applications.json`.

## Quick Start

```bash
chmod +x run.sh
./run.sh
```

The app opens automatically at **http://127.0.0.1:5757**. Press `Ctrl+C` in the terminal to stop it.

Or run directly:

```bash
pip3 install flask
python3 app.py
```

## Requirements

- Python 3.8+
- Flask (`pip3 install flask`)

## Features

- Add, edit, delete applications
- Track status: Applied → Interview → Offer / Rejected / Ghosted / Withdrawn
- Filter by status, search by company or role
- Click any row to see full details (notes, URL, salary)
- Kanban board drag-and-drop view
- Dashboard analytics (funnel, weekly trends, tag/source breakdown)
- Follow-up email templates with auto-fill
- Custom tags with filtering
- CSV import/export
- URL auto-fill from job postings
- Keyboard shortcuts: `Ctrl+N` to add, `Esc` to close panels
- Dark/light theme toggle
- Data stored locally — no accounts, no cloud

---

## Windows

### Option 1: Download the installer (recommended)

1. Download the latest `JobTracker-Setup-*.exe` from [Releases](https://github.com/CarsonReddie/Job-Application-Tracker/releases)
2. Run the installer
3. Launch JobTracker from the Start Menu or desktop shortcut

### Option 2: Build from source

1. Install [Python 3.8+](https://www.python.org/downloads/) (check "Add to PATH" during install)
2. Open Command Prompt in the project folder
3. Run:

   ```bat
   build.bat
   ```

   This creates `dist\JobTracker.exe`.

### Option 3: Run directly

```bat
pip install flask
python app.py
```

### Building the installer (from source)

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php)
2. Open Command Prompt in the project folder
3. Run:

   ```bat
   build.bat
   ```

   Output: `JobTracker-Setup-1.0.0.exe` — a standard Windows installer with Start Menu entry, optional desktop shortcut, and proper uninstall support.

### Adding to PATH (optional)

Add a batch file to your PATH so you can type `jobtracker` anywhere:

```bat
echo @echo off ^&^& python "%CD%\app.py" > jobtracker.bat
copy jobtracker.bat "%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\jobtracker.bat"
```

---

## Linux / macOS

### Run from source

```bash
pip3 install flask
python3 app.py
```

### Run with the helper script

```bash
chmod +x run.sh
./run.sh
```

### Adding to PATH (optional)

```bash
echo "alias jobtracker='bash /path/to/jobtracker/run.sh'" >> ~/.bashrc
source ~/.bashrc
jobtracker
```

---

## Data Location

| Platform | Location |
|----------|----------|
| Windows | `%APPDATA%\JobTracker\applications.json` |
| Linux/macOS | `~/.jobtracker/applications.json` |

When running from source (not compiled), data stays in the project folder as `applications.json`.
