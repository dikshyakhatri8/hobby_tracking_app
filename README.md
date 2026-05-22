# Hobby Tracker

A command-line habit tracking application built with Python, combining object-oriented and functional programming paradigms. Users can define recurring habits, log completed sessions, monitor streaks, and analyse their progress through a clean interactive menu.


## Features

- Create habits with a daily, weekly, monthly, or yearly recurrence cycle
- Log sessions and automatically track streaks across consecutive cycles
- ASCII progress bar visualising current streak versus personal best
- Analytics module built entirely with functional programming tools (`map`, `filter`, `sorted`, `max`, `reduce`, `lambda`)
- Persistent JSON storage — data survives between sessions
- Five predefined habits with four weeks of sample tracking data included
- 46 unit tests covering every class, method, and edge case


## Requirements

- Python 3.7 or later
- No third-party packages required — uses only the Python standard library (`json`, `os`, `datetime`, `functools`)

To verify your Python version:

```bash
python --version
```


## Running the Application

```bash
python hobby_tracker.py
```

The application loads the predefined habits from `hobbies.json` and opens the main menu.


## How to Use

### Main Menu

```
  ┌─────────────────────────────┐
  │         MAIN MENU           │
  ├─────────────────────────────┤
  │  [1]  Hobby Management      │
  │  [2]  Log a Session         │
  │  [3]  Progress & Stats      │
  │  [4]  Exit                  │
  └─────────────────────────────┘
```

### [1] Hobby Management

Opens a sub-menu with three options:

| Option | Action |
|--------|--------|
| Add a new hobby | Step-by-step wizard: enter a name, choose a cycle (daily/weekly/monthly/yearly), set the per-cycle frequency, add a description, and confirm before saving |
| Edit an existing hobby | Rename a hobby, update its description, or reset its streak and log history |
| Remove a hobby | Permanently delete a habit record after confirmation |

### [2] Log a Session

Displays the full hobby table, asks you to pick a number, and records today's date against that hobby. The streak is recomputed immediately and an ASCII progress bar is shown.

```
  Logged 'Morning Journaling' for 2026-05-22.
  ████████████████░░░░  streak 16 / best 28
```

### [3] Progress & Stats

Displays:
- ASCII progress bars for every habit (current streak vs personal best)
- Aggregate figures: total hobbies, total sessions logged, average streak, top streak holder
- Habits grouped by cycle type (daily / weekly / monthly / yearly)
- A ranked streak leaderboard

### [4] Exit

Saves all data and closes the application.


## Running the Tests

The test suite uses Python's built-in `unittest` framework and can also be run with `pytest`.

**With pytest (recommended):**

```bash
python -m pytest test_hobby_tracker.py -v
```

**With unittest:**

```bash
python -m unittest test_hobby_tracker.py -v
```

All 46 tests should pass. The suite covers:

| Test class | What is tested |
|---|---|
| `TestHobby` | Constructor, serialisation (`to_dict`), and round-trip restoration (`from_dict`) |
| `TestHobbyAnalytics` | All six functional analytics methods with exact numeric assertions |
| `TestHobbyStore` | Save-then-reload round-trips; missing-file edge case |
| `TestHobbyTracker` | Streak engine (daily and weekly cycles), progress bar, controller state, table display |


## Predefined Habits and Sample Data

The file `hobbies.json` ships with five ready-to-use habits and approximately four weeks of tracking data so the analytics screen has real figures to display from the first run.

| # | Habit | Cycle | Target | Sample data covers |
|---|-------|-------|--------|--------------------|
| 1 | Morning Journaling | Daily | 1 session/day | 12 Apr – 11 May 2026 (28 entries, best streak 28) |
| 2 | Screenless Morning | Daily | 1 session/day | 20 Apr – 9 May 2026 (20 entries, streak 20) |
| 3 | Chess Puzzles | Weekly | 2 sessions/week | 5 complete weeks (Apr – May 2026, streak 5) |
| 4 | Weekly Reflection | Weekly | 1 session/week | 5 consecutive Mondays (Apr – May 2026, streak 5) |
| 5 | Apartment Deep Clean | Monthly | 1 session/month | Jan – Apr 2026 (4 months, streak 4) |

To reset to the original sample data, restore `hobbies.json` from the repository.


## Project Structure

```
.
├── hobby_tracker.py          # Main application — all classes and CLI
├── test_hobby_tracker.py     # 46-test unit suite
├── hobbies.json              # Persistent data file (predefined habits + sample logs)
├── Hobby_tracker_diagram.jpeg  # UML class diagram
└── README.md                 # This file
```

### Architecture overview

| Component | Class | Paradigm |
|-----------|-------|----------|
| Data model | `Hobby` | Object-oriented |
| Persistence | `HobbyStore` | Object-oriented |
| Analytics | `HobbyAnalytics` | Functional (`map`, `filter`, `sorted`, `max`, `reduce`) |
| CLI controller | `HobbyTracker` | Object-oriented |
| Streak engine | Module-level helpers (`_rebuild_streak`, `_cycle_open`, `_cycle_close`, `_window_sequence`, `_entries_in_window`, `_progress_bar`) | Pure functions |


## How Streaks Work

A streak counts the number of consecutive cycles in which the required frequency was met.

- A **closed** past cycle window that falls short of the target **resets** the streak to zero.
- The **current open** cycle window (still in progress today) does **not** break the streak even if the target has not yet been reached.
- The **best streak** is the highest value ever recorded and is preserved across resets.

Example (daily habit, target 1/day):

```
Mon ✓  Tue ✓  Wed ✗  Thu ✓  Fri (today)
                ↑ past missed window resets streak
streak = 1 (only Thu counts), best = 2 (Mon–Tue run)
```


## License

This project was developed as a portfolio submission for the course *Object-Oriented and Functional Programming with Python* (DLBDSOOFPP01) at IU International University of Applied Sciences.
