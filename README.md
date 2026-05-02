# Job Tracker

A local job application tracker that runs in your browser. Data is stored in `applications.json` in the same folder.

## Requirements

- Python 3.8+
- Flask (`pip3 install flask`)

## Quick start

```bash
chmod +x run.sh
./run.sh
```

The app opens automatically at **http://127.0.0.1:5757**. Press `Ctrl+C` in the terminal to stop it.

Or run directly:

```bash
python3 app.py
```

## Features

- Add, edit, delete applications
- Track status: Applied → Interview → Offer / Rejected / Ghosted / Withdrawn
- Filter by status, search by company or role
- Click any row to see full details (notes, URL, salary)
- Keyboard shortcuts: `Ctrl+N` to add, `Esc` to close panels
- Dark mode support (follows system preference)
- Data stored locally in `applications.json`

## Adding to your PATH (optional)

```bash
echo "alias jobtracker='bash /path/to/jobtracker/run.sh'" >> ~/.bashrc
source ~/.bashrc
jobtracker
```
