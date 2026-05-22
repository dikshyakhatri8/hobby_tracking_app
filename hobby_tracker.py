import json            # For reading and writing hobby data to and from the JSON file
import os              # For checking whether the data file exists before opening it
from datetime import datetime, timedelta  # For all date calculations, comparisons, and timestamps
from functools import reduce              # For functional aggregation inside the analytics layer

# ─────────────────────────────────────────────────────────────────────────────
# Module-level streak-engine helpers (pure functions, no class membership)
# ─────────────────────────────────────────────────────────────────────────────

def _cycle_open(date, cycle):
    """Return the first calendar day of the cycle window that contains 'date'."""
    if cycle == "daily":
        return date                                    # A daily window opens on the date itself
    elif cycle == "weekly":
        return date - timedelta(days=date.weekday())   # Step back to the Monday of this week
    elif cycle == "monthly":
        return date.replace(day=1)                     # Every month opens on its first day
    elif cycle == "yearly":
        return date.replace(month=1, day=1)            # Every year opens on January the 1st


def _cycle_close(opening, cycle):
    """Return the last calendar day of the cycle window that begins on 'opening'."""
    if cycle == "daily":
        return opening                                 # A daily window also closes on the same day
    elif cycle == "weekly":
        return opening + timedelta(days=6)             # Six days after Monday lands on Sunday
    elif cycle == "monthly":
        if opening.month == 12:                        # December cannot have a 'next' month
            return opening.replace(day=31)             # December always ends on the 31st
        next_open = opening.replace(month=opening.month + 1, day=1)  # First day of next month
        return next_open - timedelta(days=1)           # One day before that is the last of this month
    elif cycle == "yearly":
        return opening.replace(month=12, day=31)       # Every year closes on December the 31st


def _window_sequence(earliest, cycle):
    """
    Generator that yields successive (open, close) window pairs, starting from
    the cycle window containing 'earliest' and advancing one window at a time
    until the current window has passed today's date.
    """
    cursor = _cycle_open(earliest, cycle)              # Snap cursor to the first window boundary
    today = datetime.now().date()                      # Capture today once; reused each iteration
    while cursor <= today:                             # Keep yielding until we pass today
        closing = _cycle_close(cursor, cycle)          # Compute the closing date of this window
        yield cursor, closing                          # Deliver this (open, close) pair to the caller
        cursor = closing + timedelta(days=1)           # Jump to the day that opens the next window


def _entries_in_window(log_dates, win_open, win_close):
    """
    Count log entries whose date falls within [win_open, win_close] (both inclusive).
    Uses a generator expression inside sum() to stay in the functional style.
    """
    return sum(                                        # Sum booleans: True == 1, False == 0
        1 for d in log_dates                           # Iterate over every stored log-date string
        if win_open <= datetime.strptime(d, "%Y-%m-%d").date() <= win_close  # Inclusive range check
    )


def _rebuild_streak(hobby):
    """
    Walk every cycle window from the earliest log entry to today and return
    (current_streak, best_streak).  A closed past window that fails to meet
    the frequency target resets the streak; a still-open window does not.
    """
    if not hobby.log_dates:                            # Guard: empty history means no streak at all
        return 0, hobby.best_streak                    # Preserve stored best; current resets to zero

    sorted_dates = sorted(hobby.log_dates)             # Sort ascending so the earliest is always first
    earliest = datetime.strptime(sorted_dates[0], "%Y-%m-%d").date()  # Parse the earliest entry
    today = datetime.now().date()                      # Need today for the open-window guard below

    current = 0                                        # Accumulates consecutive completed windows
    best = hobby.best_streak                           # Carry the stored best forward as a floor

    for win_open, win_close in _window_sequence(earliest, hobby.cycle):  # Walk every window
        count = _entries_in_window(hobby.log_dates, win_open, win_close)  # Entries in this window

        if count >= hobby.frequency:                   # Window target was met
            current += 1                               # Extend the streak by one window
            if current > best:                         # Did we set a new personal record?
                best = current                         # Update the best if so
        elif win_close < today:                        # Window is fully in the past and was missed
            current = 0                                # A past miss resets the streak to zero
        # If the window is still open (win_close >= today) and count < frequency,
        # the day is not over — do NOT break the streak prematurely

    return current, best                               # Return both final computed values


def _progress_bar(streak, best, width=20):
    """
    Build an ASCII progress bar that shows the current streak as a proportion
    of the best streak ever achieved.  Filled blocks use █, empty blocks use ░.
    """
    if best == 0:                                      # Guard: avoid division by zero when no best
        filled = 0                                     # Empty bar when no best exists yet
    else:
        filled = round((streak / best) * width)        # Scale the streak to the bar width
    filled = min(filled, width)                        # Clamp to the maximum bar width
    empty = width - filled                             # Remaining blocks are shown as empty
    return "█" * filled + "░" * empty                  # Concatenate filled and empty blocks


"""
Hobby Tracker — A recurring-goal management system.

This single-file application lets users define personal hobbies with a
recurrence cycle (daily, weekly, monthly, or yearly) and monitor their
streak — the number of consecutive cycles in which they met the required
frequency. All data is persisted in a JSON file between sessions.

Classes:
    Hobby          : Stores every attribute that belongs to a single hobby.
    HobbyStore     : Handles all file I/O (load and save) for hobby data.
    HobbyAnalytics : Provides analytics using the functional programming paradigm.
    HobbyTracker   : Drives the CLI: 4 main options, sub-menus, table display,
                     ASCII progress bars, and a confirmation preview for new hobbies.
"""


# =============================================================================
# Class: Hobby
# Responsibility: Encapsulate all data that belongs to one personal hobby
# =============================================================================
class Hobby:
    """
    Represents a single recurring personal hobby with a cycle and a frequency target.

    Attributes:
        title       (str)  : Short name that uniquely identifies the hobby.
        cycle       (str)  : Recurrence cadence — 'daily', 'weekly', 'monthly', 'yearly'.
        frequency   (int)  : Minimum sessions per cycle required to keep the streak alive.
        description (str)  : Free-text note describing what the hobby involves.
        created_on  (str)  : Timestamp (YYYY-MM-DD HH:MM) recording when the hobby was added.
        log_dates   (list) : ISO-date strings (YYYY-MM-DD) of every logged session.
        streak      (int)  : Count of consecutive cycles that have all met the target.
        best_streak (int)  : Highest streak value ever recorded for this hobby.
    """

    # Human-readable labels for each supported cycle type
    CYCLE_LABELS = {
        "daily": "Daily",
        "weekly": "Weekly",
        "monthly": "Monthly",
        "yearly": "Yearly"
    }

    def __init__(self, title, cycle, frequency, description):
        """Initialise a new Hobby with empty history and an automatic creation timestamp."""
        self.title = title                              # Store the user-provided hobby name
        self.cycle = cycle                              # Store the recurrence pattern key
        self.frequency = frequency                      # Store the per-cycle session target
        self.description = description                  # Store the descriptive note
        self.created_on = datetime.now().strftime("%Y-%m-%d %H:%M")  # Stamp the creation moment
        self.log_dates = []                             # No sessions have been recorded yet
        self.streak = 0                                 # No consecutive cycles completed yet
        self.best_streak = 0                            # No personal best established yet

    def cycle_label(self):
        """Return the display-friendly label for this hobby's cycle type."""
        return self.CYCLE_LABELS.get(self.cycle, self.cycle)  # Fall back to the raw key if unknown

    def target_label(self):
        """Return a compact string describing the per-cycle frequency target."""
        if self.cycle == "daily":
            return "1x / day"                          # Daily hobbies always require one per day
        return f"{self.frequency}x / {self.cycle[:2]}"  # e.g. '2x / we' for weekly

    def to_dict(self):
        """Serialise this Hobby to a plain dictionary ready for JSON output."""
        return {
            "title": self.title,                        # Hobby identifier
            "cycle": self.cycle,                        # Recurrence pattern key
            "frequency": self.frequency,                # Per-cycle session target
            "description": self.description,            # Free-text note
            "created_on": self.created_on,              # Creation timestamp string
            "log_dates": self.log_dates,                # Sorted list of logged date strings
            "streak": self.streak,                      # Current consecutive-cycle count
            "best_streak": self.best_streak             # All-time best consecutive-cycle count
        }

    @classmethod
    def from_dict(cls, data):
        """Reconstruct a fully populated Hobby object from a stored dictionary."""
        obj = cls(                                      # Allocate a fresh instance with core fields
            title=data["title"],                        # Restore the hobby name
            cycle=data["cycle"],                        # Restore the recurrence cycle key
            frequency=data["frequency"],                # Restore the per-cycle frequency target
            description=data["description"]             # Restore the descriptive note
        )
        obj.created_on = data["created_on"]             # Restore the original creation timestamp
        obj.log_dates = data["log_dates"]               # Restore the full log-date history
        obj.streak = data["streak"]                     # Restore the last-computed streak count
        obj.best_streak = data["best_streak"]           # Restore the all-time best streak
        return obj                                      # Return the fully reconstructed object


# =============================================================================
# Class: HobbyStore
# Responsibility: Load and save hobby records to and from the JSON data file
# =============================================================================
class HobbyStore:
    """
    Manages all file-system persistence for hobby data.

    Records are stored under a top-level "hobbies" key in the JSON file,
    allowing future metadata to coexist without breaking the existing format.
    """

    DATA_FILE = "hobbies.json"  # Default name of the JSON persistence file

    @classmethod
    def load(cls):
        """
        Read the data file and deserialise it into a list of Hobby objects.
        Returns an empty list if the file is missing, empty, or unreadable.
        """
        if not os.path.exists(cls.DATA_FILE):           # Abort cleanly if the file is absent
            return []                                   # Nothing saved yet means an empty list

        try:
            with open(cls.DATA_FILE, "r") as fh:        # Open the file for reading
                payload = json.load(fh)                 # Parse the entire JSON document at once
            return [Hobby.from_dict(r) for r in payload.get("hobbies", [])]  # Reconstruct objects
        except (json.JSONDecodeError, KeyError):
            print("  Data file is unreadable. Starting with an empty list.")  # Warn the user
            return []                                   # Recover gracefully with an empty list

    @classmethod
    def save(cls, hobbies):
        """
        Serialise a list of Hobby objects and write them to the data file.

        Args:
            hobbies (list) : Every Hobby object that should be persisted.
        """
        payload = {"hobbies": [h.to_dict() for h in hobbies]}  # Wrap records under the top-level key
        with open(cls.DATA_FILE, "w") as fh:            # Open for writing (replaces any old content)
            json.dump(payload, fh, indent=4)            # Write human-readable, indented JSON


# =============================================================================
# Class: HobbyAnalytics
# Responsibility: Provide all analytics using the functional programming paradigm
# =============================================================================
class HobbyAnalytics:
    """
    Stateless analytics class implemented entirely with functional-programming tools.

    Every method uses higher-order functions (map, filter, sorted, max, reduce)
    and lambda expressions rather than imperative loops, satisfying the assignment
    requirement that the analytics layer follow the functional paradigm.
    """

    @staticmethod
    def list_all(hobbies):
        """
        Return a list of all currently tracked hobbies.
        Uses map() to project the collection, preserving every element.
        """
        return list(map(lambda h: h, hobbies))          # map over every hobby and collect results

    @staticmethod
    def list_by_cycle(hobbies, cycle):
        """
        Return all hobbies whose cycle matches the given cycle type.
        Uses filter() with a lambda predicate to select matching hobbies.
        """
        return list(filter(lambda h: h.cycle == cycle, hobbies))  # Keep only cycle-matching entries

    @staticmethod
    def longest_streak_overall(hobbies):
        """
        Return the hobby with the longest run streak across all tracked hobbies.
        Uses max() with a key lambda to find the highest best_streak value.
        Returns None when the list is empty.
        """
        return max(hobbies, key=lambda h: h.best_streak) if hobbies else None  # Max by best_streak

    @staticmethod
    def longest_streak_for(hobby):
        """
        Return the longest run streak recorded for a single specific hobby.
        A simple attribute access, presented as a named analytics function.
        """
        return hobby.best_streak                        # The stored all-time best for this hobby

    @staticmethod
    def sorted_by_streak(hobbies):
        """
        Return hobbies sorted from highest to lowest best_streak.
        Uses sorted() with a key lambda and reverse=True for descending order.
        """
        return sorted(hobbies, key=lambda h: h.best_streak, reverse=True)  # Descending order

    @staticmethod
    def average_streak(hobbies):
        """
        Compute the mean current streak across all hobbies.
        Uses map() to extract streaks, then reduce() to sum them functionally.
        """
        if not hobbies:                                 # Guard against division by zero
            return 0.0
        streak_values = list(map(lambda h: h.streak, hobbies))  # Extract each streak via map
        total = reduce(lambda acc, x: acc + x, streak_values)   # Sum using reduce (functional fold)
        return total / len(streak_values)               # Return the arithmetic mean

    @staticmethod
    def total_sessions(hobbies):
        """
        Count the total number of logged sessions across all hobbies.
        Uses map() to get per-hobby counts and reduce() to fold them into a sum.
        """
        if not hobbies:                                 # Return zero for an empty collection
            return 0
        counts = list(map(lambda h: len(h.log_dates), hobbies))  # Per-hobby session counts via map
        return reduce(lambda acc, n: acc + n, counts)   # Fold counts into a grand total via reduce


# =============================================================================
# Class: HobbyTracker
# Responsibility: Drive the CLI — 4 main options, sub-menus, table view, ASCII bars
# =============================================================================
class HobbyTracker:
    """
    Main application controller that presents a 4-option main menu and delegates
    work to Hobby, HobbyStore, and HobbyAnalytics.

    Main menu:
        [1] Hobby Management  →  sub-menu: add / edit / remove
        [2] Log a Session     →  pick hobby from table, log today
        [3] Progress & Stats  →  ASCII bars + functional analytics summary
        [4] Exit
    """

    VALID_CYCLES = ("daily", "weekly", "monthly", "yearly")  # All accepted cycle type strings

    def __init__(self):
        """Load persisted hobbies from disk and prepare the application state."""
        self.hobbies = HobbyStore.load()                # Restore any previously saved hobbies

    # ─────────────────────────────────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────────────────────────────────

    def run(self):
        """Print the welcome banner and start the main 4-option menu loop."""
        print("\n" + "=" * 46)
        print("    HOBBY TRACKER  |  Build Good Routines")   # Application title banner
        print("=" * 46)
        self._main_menu()                               # Hand control to the main menu loop

    # ─────────────────────────────────────────────────────────────────────────
    # Main menu (4 options)
    # ─────────────────────────────────────────────────────────────────────────

    def _main_menu(self):
        """Display the 4-option main menu and route the user's selection."""
        while True:
            print("\n  ┌─────────────────────────────┐")
            print("  │         MAIN MENU           │")       # Section header for the main menu
            print("  ├─────────────────────────────┤")
            print("  │  [1]  Hobby Management      │")       # Opens the management sub-menu
            print("  │  [2]  Log a Session         │")       # Log one session for today
            print("  │  [3]  Progress & Stats      │")       # Show ASCII bars and analytics
            print("  │  [4]  Exit                  │")       # End the application
            print("  └─────────────────────────────┘")

            choice = input("\n  Select an option (1-4): ").strip()  # Read the user's choice

            if choice == "1":
                self._management_menu()                 # Route to the hobby management sub-menu
            elif choice == "2":
                self._log_session()                     # Route to the session-logging flow
            elif choice == "3":
                self._stats_screen()                    # Route to the analytics display
            elif choice == "4":
                print("\n  Goodbye! Stay consistent.\n") # Friendly farewell message
                break                                   # Exit the loop and end the program
            else:
                print("  Please enter 1, 2, 3, or 4.")  # Reject any unrecognised input

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-menu: Hobby Management  [1] Add  [2] Edit  [3] Remove  [4] Back
    # ─────────────────────────────────────────────────────────────────────────

    def _management_menu(self):
        """Display the hobby-management sub-menu and route the user's selection."""
        while True:
            print("\n  -- Hobby Management --")
            print("  [1]  Add a new hobby")              # Create a brand-new hobby record
            print("  [2]  Edit an existing hobby")       # Change details of a saved hobby
            print("  [3]  Remove a hobby")               # Permanently delete a hobby
            print("  [4]  Back to main menu")            # Return to the 4-option main menu

            sub = input("\n  Select (1-4): ").strip()    # Read the sub-menu selection

            if sub == "1":
                self._add_hobby()                        # Route to the add-hobby wizard
            elif sub == "2":
                self._edit_hobby()                       # Route to the edit-hobby flow
            elif sub == "3":
                self._remove_hobby()                     # Route to the remove-hobby flow
            elif sub == "4":
                break                                    # Return to the main menu loop
            else:
                print("  Please enter 1, 2, 3, or 4.")  # Reject any unrecognised sub-menu input

    # ─────────────────────────────────────────────────────────────────────────
    # Management action: Add a new hobby (wizard with confirmation preview)
    # ─────────────────────────────────────────────────────────────────────────

    def _add_hobby(self):
        """
        Walk the user through a step-by-step wizard for creating a new hobby,
        then display a confirmation preview before committing the record to disk.
        """
        print("\n  -- Add New Hobby --")

        # Step 1: collect the title
        title = input("  Hobby name         : ").strip()
        if not title:                                   # Blank title is not acceptable
            print("  Name cannot be empty. Returning to menu.")
            return
        if any(h.title.lower() == title.lower() for h in self.hobbies):  # No duplicates
            print(f"  '{title}' already exists. Returning to menu.")
            return

        # Step 2: choose the recurrence cycle
        print("  Recurrence cycle   : [1] Daily  [2] Weekly  [3] Monthly  [4] Yearly")
        cycle_input = input("  Your choice        : ").strip()
        cycle_map = {"1": "daily", "2": "weekly", "3": "monthly", "4": "yearly"}
        if cycle_input not in cycle_map:                # Reject anything outside 1–4
            print("  Invalid cycle. Returning to menu.")
            return
        cycle = cycle_map[cycle_input]                  # Resolve the digit to a cycle key

        # Step 3: determine the per-cycle frequency
        if cycle == "daily":
            frequency = 1                               # Daily always requires exactly one session
            freq_display = "1 session per day"          # Human-readable summary for the preview
        else:
            limits = {"weekly": 7, "monthly": 31, "yearly": 365}  # Upper cap per cycle type
            top = limits[cycle]                         # Look up the ceiling for the chosen cycle
            frequency = self._read_int(
                f"  Sessions per {cycle} (1-{top}): ", 1, top
            )
            if frequency is None:                       # None signals a validation failure
                return
            freq_display = f"{frequency} session(s) per {cycle}"  # Human-readable for the preview

        # Step 4: collect a description
        description = input("  Description        : ").strip()
        if not description:                             # Substitute a placeholder if left blank
            description = "No description provided."

        # Step 5: show a confirmation preview box before writing anything to disk
        print("\n  +-----------------------------------------+")
        print("  |           CONFIRM NEW HOBBY             |")    # Preview box header
        print("  +-----------------------------------------+")
        print(f"  |  Name   : {title:<30}|")                      # Title line in the preview
        print(f"  |  Cycle  : {freq_display:<30}|")               # Frequency summary line
        print(f"  |  Desc   : {description[:30]:<30}|")           # Truncated description line
        print("  +-----------------------------------------+")

        confirm = input("  Save this hobby? (yes / no): ").strip().lower()  # Ask for confirmation
        if confirm != "yes":                            # Only proceed on an explicit 'yes'
            print("  Hobby not saved.")
            return

        # Build the Hobby object, append it, and write the updated list to disk
        new_hobby = Hobby(title, cycle, frequency, description)  # Creation timestamp auto-set
        self.hobbies.append(new_hobby)                  # Insert at the end of the in-memory list
        HobbyStore.save(self.hobbies)                   # Persist immediately after confirmation
        print(f"  '{title}' saved! (Created: {new_hobby.created_on})")  # Confirm with timestamp

    # ─────────────────────────────────────────────────────────────────────────
    # Management action: Edit an existing hobby
    # ─────────────────────────────────────────────────────────────────────────

    def _edit_hobby(self):
        """Display the hobby table, let the user pick one, then offer edit options."""
        print("\n  -- Edit Hobby --")
        if not self._render_table():                    # Show the table; abort if list is empty
            return

        idx = self._read_int("  Hobby number to edit (0 to cancel): ", 0, len(self.hobbies))
        if idx is None or idx == 0:                     # 0 means the user wants to go back
            return

        target = self.hobbies[idx - 1]                  # Retrieve the selected Hobby object
        print(f"\n  Editing: {target.title}")
        print("  [1]  Rename")                          # Change the hobby's title
        print("  [2]  Edit description")                # Change the description text
        print("  [3]  Reset streak & clear log")        # Wipe all history and set streak to 0
        print("  [4]  Cancel")                          # Go back without making any change

        action = input("  Choice: ").strip()            # Read the edit-action selection

        if action == "1":                               # Rename the hobby
            new_name = input("  New name: ").strip()
            if new_name:                                # Only apply a non-blank replacement
                target.title = new_name
                HobbyStore.save(self.hobbies)           # Persist the change immediately
                print("  Name updated.")
            else:
                print("  No change made.")              # Blank input means do nothing

        elif action == "2":                             # Edit the description
            new_desc = input("  New description: ").strip()
            if new_desc:
                target.description = new_desc
                HobbyStore.save(self.hobbies)           # Persist the change immediately
                print("  Description updated.")
            else:
                print("  No change made.")              # Blank input means do nothing

        elif action == "3":                             # Reset streak and log history
            confirm = input("  Clear all log dates and reset streak? (yes/no): ").strip().lower()
            if confirm == "yes":
                target.log_dates = []                   # Wipe the entire log history
                target.streak = 0                       # Reset the rolling streak to zero
                HobbyStore.save(self.hobbies)           # Persist the cleared state
                print("  Log and streak cleared.")
            else:
                print("  Reset cancelled.")

        elif action == "4":                             # Explicit cancel
            print("  No changes made.")
        else:
            print("  Invalid selection.")               # Reject unrecognised input

    # ─────────────────────────────────────────────────────────────────────────
    # Management action: Remove a hobby
    # ─────────────────────────────────────────────────────────────────────────

    def _remove_hobby(self):
        """Display the hobby table and permanently delete the user's chosen entry."""
        print("\n  -- Remove Hobby --")
        if not self._render_table():                    # Show the table; abort if list is empty
            return

        idx = self._read_int("  Hobby number to remove (0 to cancel): ", 0, len(self.hobbies))
        if idx is None or idx == 0:                     # 0 means the user wants to go back
            return

        target = self.hobbies[idx - 1]                  # Retrieve the selected Hobby object
        confirm = input(f"  Delete '{target.title}' permanently? (yes/no): ").strip().lower()
        if confirm == "yes":
            self.hobbies.pop(idx - 1)                   # Remove from the in-memory list by index
            HobbyStore.save(self.hobbies)               # Persist the shortened list immediately
            print("  Hobby deleted.")
        else:
            print("  Deletion cancelled.")              # Do nothing if the user backs out

    # ─────────────────────────────────────────────────────────────────────────
    # Main option [2]: Log a session for today
    # ─────────────────────────────────────────────────────────────────────────

    def _log_session(self):
        """Show the hobby table, pick one, and append today's date to its log."""
        print("\n  -- Log a Session --")
        if not self._render_table():                    # Show the table; abort if list is empty
            return

        idx = self._read_int("  Hobby number to log (0 to cancel): ", 0, len(self.hobbies))
        if idx is None or idx == 0:                     # 0 means the user wants to cancel
            return

        hobby = self.hobbies[idx - 1]                   # Retrieve the target Hobby by position
        today = datetime.now().strftime("%Y-%m-%d")     # Capture today's date as an ISO string

        already = hobby.log_dates.count(today)          # Count how many times logged today already

        if hobby.cycle == "daily" and already >= 1:     # Daily: strictly one session per day
            print(f"  '{hobby.title}' is already logged for today.")
            return
        if already >= hobby.frequency:                  # All cycles: cap at the frequency target
            print(f"  Today's target for '{hobby.title}' is already met.")
            return

        hobby.log_dates.append(today)                   # Append today's ISO date to the log
        hobby.log_dates.sort()                          # Keep the log in chronological order

        hobby.streak, hobby.best_streak = _rebuild_streak(hobby)  # Recompute streak from full log

        HobbyStore.save(self.hobbies)                   # Persist the updated state to disk

        bar = _progress_bar(hobby.streak, hobby.best_streak)  # Build the ASCII progress bar
        print(f"\n  Logged '{hobby.title}' for {today}.")
        print(f"  {bar}  streak {hobby.streak} / best {hobby.best_streak}")  # Show bar + numbers

    # ─────────────────────────────────────────────────────────────────────────
    # Main option [3]: Progress & Stats screen
    # ─────────────────────────────────────────────────────────────────────────

    def _stats_screen(self):
        """
        Display the full analytics screen:
          1. ASCII progress-bar table (streak vs best for every hobby)
          2. Aggregate stats computed using functional-programming methods
          3. Hobby groups by cycle type (via filter)
          4. Ranked leaderboard (via sorted)
        """
        print("\n  -- Progress & Stats --")
        if not self.hobbies:                            # Nothing to show on an empty list
            print("  No hobbies to display.")
            return

        # ── Section 1: ASCII progress bars ───────────────────────────────────
        print("\n  Progress (current streak vs personal best)")
        print("  " + "-" * 44)
        for h in self.hobbies:                          # Iterate through every registered hobby
            bar = _progress_bar(h.streak, h.best_streak)    # Generate the bar for this hobby
            label = f"{h.title[:20]:<20}"                   # Truncate and pad the title to 20 chars
            print(f"  {label}  {bar}  {h.streak:>3} / {h.best_streak:<3}")  # Print bar row
        print("  " + "-" * 44)

        # ── Section 2: aggregate figures (functional methods) ─────────────────
        all_h = HobbyAnalytics.list_all(self.hobbies)           # All hobbies via map()
        total = HobbyAnalytics.total_sessions(self.hobbies)     # Grand total via reduce()
        avg = HobbyAnalytics.average_streak(self.hobbies)       # Mean streak via reduce()
        top = HobbyAnalytics.longest_streak_overall(self.hobbies)  # Best hobby via max()

        print(f"\n  Total hobbies  : {len(all_h)}")
        print(f"  Total sessions : {total}")
        print(f"  Avg streak     : {avg:.1f}")
        if top:                                                  # Only print if a top hobby exists
            print(f"  Top streak     : {top.title} — best of {top.best_streak}")

        # ── Section 3: grouping by cycle type (filter) ────────────────────────
        print("\n  Hobbies by cycle")
        for cycle_key in ("daily", "weekly", "monthly", "yearly"):   # Check all four cycle types
            group = HobbyAnalytics.list_by_cycle(self.hobbies, cycle_key)  # filter() for this cycle
            if group:                                                  # Only print non-empty groups
                names = ", ".join(map(lambda h: h.title, group))       # Join names via map()
                print(f"  {cycle_key.capitalize():<10}: {names}")

        # ── Section 4: streak leaderboard (sorted, longest_streak_for) ────────
        print("\n  Streak leaderboard")
        ranked = HobbyAnalytics.sorted_by_streak(self.hobbies)  # sorted() descending by best_streak
        for rank, h in enumerate(ranked, start=1):               # Number rankings from 1
            best = HobbyAnalytics.longest_streak_for(h)          # Named accessor for the best streak
            sessions = len(h.log_dates)                          # Total session count for this hobby
            print(f"  #{rank:<2} {h.title:<24}  best: {best:<4}  sessions: {sessions}")

        print()                                                   # Blank line to close the section

    # ─────────────────────────────────────────────────────────────────────────
    # Shared display: hobby table
    # ─────────────────────────────────────────────────────────────────────────

    def _render_table(self):
        """
        Print a formatted table of all registered hobbies.
        Returns True if at least one hobby exists, False otherwise.
        """
        if not self.hobbies:                            # Nothing to render on an empty list
            print("  No hobbies registered yet.")
            return False                                # Signal to the caller that the list is empty

        # Print the table header row with fixed-width columns
        print(f"\n  {'#':<4}{'Name':<24}{'Cycle':<10}{'Target':<12}{'Streak':>7}{'Best':>6}")
        print("  " + "─" * 63)                         # Horizontal rule below the header

        for i, h in enumerate(self.hobbies, start=1):  # Number rows starting from 1
            print(                                      # Print one data row per hobby
                f"  {i:<4}"                             # Left-aligned index number
                f"{h.title:<24}"                        # Left-aligned hobby title (24 chars wide)
                f"{h.cycle_label():<10}"                # Left-aligned cycle label (10 chars wide)
                f"{h.target_label():<12}"               # Left-aligned target label (12 chars wide)
                f"{h.streak:>7}"                        # Right-aligned current streak
                f"{h.best_streak:>6}"                   # Right-aligned best streak
            )

        print("  " + "─" * 63)                         # Horizontal rule below the data rows
        return True                                     # Signal to the caller that rows were printed

    # ─────────────────────────────────────────────────────────────────────────
    # Shared utility: validated integer input
    # ─────────────────────────────────────────────────────────────────────────

    def _read_int(self, prompt, lo, hi):
        """
        Prompt for a whole number within [lo, hi] and return it, or None on failure.
        Consolidates all numeric input validation in one reusable place.
        """
        raw = input(prompt).strip()                     # Read the raw input and strip whitespace
        if not raw.lstrip("-").isdigit():               # Reject strings that are not pure integers
            print("  Please enter a whole number.")
            return None
        value = int(raw)                                # Convert the validated string to an integer
        if not (lo <= value <= hi):                     # Enforce the allowed inclusive range
            print(f"  Please enter a number between {lo} and {hi}.")
            return None
        return value                                    # Return the verified integer to the caller


# =============================================================================
# Entry point — launch the application when this file is executed directly
# =============================================================================
if __name__ == "__main__":
    tracker = HobbyTracker()    # Instantiate the main controller (loads saved hobbies from disk)
    tracker.run()               # Begin the interactive CLI session
