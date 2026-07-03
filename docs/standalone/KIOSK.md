# Kiosk mode: the in-app lock and a true OS kiosk

**Phase 7 · issue 44**

Labs run the Instrument on machines a participant is left alone with. This page
explains the built-in **in-app lock** — what it stops and, just as importantly,
what it honestly cannot stop — and walks an IT administrator through pairing the
Instrument with **Windows Assigned Access / Shell Launcher** when a study needs a
real OS-level kiosk.

---

## The in-app lock (built in)

Add an **exit passcode** to your Study Preset (Study Setup → *Exit passcode*, or
the `exit_passcode` key in `study.json`). While a session runs with a passcode
set:

- the window is held **fullscreen and always-on-top**;
- every in-app exit path — the ← back button and the Escape/F11 keys — opens a
  **passcode prompt** instead of leaving. A wrong entry returns to the session
  unharmed; the entry is never shown on screen.
- the lock **disengages by itself at the debrief screen** (researcher
  hand-back). Normal completion never asks for the passcode; only mid-session
  escape is gated.

Leaving the field empty keeps the previous behavior: exits are ungated.

### Honest limits — read this before relying on it

- **The passcode is deterrence, not security.** It is stored in plain text in
  `study.json` (and in each session's config snapshot). It stops a curious
  participant from clicking out of the task; it does not stop anyone who can
  open the preset file.
- **The lock is in-app only.** The Instrument installs **no global keyboard
  hooks** and suppresses **no OS shortcuts** — doing so triggers antivirus
  flags and macOS accessibility prompts while still not catching everything.
  That means `Ctrl+Alt+Del`, `Win`, `Win+L`, `Alt+Tab` (Windows) and
  `Cmd+Tab`, `Cmd+Q` (macOS) still work. "Completely locking the OS" is not
  achievable from a normal application — it is an operating-system feature,
  configured by the OS administrator (below).
- For **attended sessions** (a researcher in the room), the in-app lock plus
  the fullscreen/always-on-top window is typically all a lab needs.

## A true OS kiosk on Windows (Assigned Access)

For unattended or high-stakes settings, Windows 10/11 **Pro, Enterprise, and
Education** editions can lock a whole user account to a single app. This is an
OS feature — it survives `Alt+Tab` and the `Win` key because Windows itself
refuses to switch away.

The Instrument is a normal desktop (Win32) application, so use one of the two
Win32-capable mechanisms:

### Option A — kiosk configuration with a Win32 app (Windows 11)

Windows 11 (22H2 and later) allows desktop apps in an Assigned Access
configuration:

1. Create a dedicated **standard** (non-administrator) local account, e.g.
   `bart-kiosk`, and log into it once so its profile exists.
2. Install the Instrument for that account (see the
   [SmartScreen page](SMARTSCREEN.md) for the unsigned-installer prompt).
3. As an administrator, apply an Assigned Access configuration whose
   `<AllowedApps>` names the Instrument's installed `.exe`, and assign it to
   the kiosk account — via your MDM (Intune: *Kiosk* configuration profile) or
   the `MDM_AssignedAccess` PowerShell/WMI bridge. Microsoft's reference:
   search **"Assigned Access configuration file"** on Microsoft Learn.
4. Log the lab machine into `bart-kiosk` for sessions. Windows confines the
   account to the Instrument; `Ctrl+Alt+Del` still works but only offers
   sign-out — which is exactly the researcher hand-back you want.

### Option B — Shell Launcher (Enterprise/Education)

**Shell Launcher v2** replaces the Windows shell (Explorer) with the
Instrument for a chosen account: the machine boots that account straight into
the task, and closing the app can be configured to restart it or sign out.
Enable the *Shell Launcher* feature, then set the Instrument's `.exe` as the
custom shell for the kiosk account (PowerShell/WMI or MDM). Reference: search
**"Shell Launcher"** on Microsoft Learn.

### Practical notes

- Pair either option with the in-app exit passcode: the OS kiosk stops
  app-switching, the passcode stops in-app exits, and the debrief hand-back
  stays passcode-free.
- Test the full path — boot, SmartScreen (first run only), a complete session,
  debrief, sign-out — **before** the first participant.
- Windows **Home** edition has neither feature; use the in-app lock and an
  attended session, or upgrade the lab machine.

## macOS

macOS has no supported way to confine an arbitrary desktop app to a
single-app kiosk without device management: single-app mode requires an MDM
profile (e.g. Jamf's Single App Mode) on a supervised machine. Labs on
managed Macs should ask their IT for a single-app profile pointing at the
Instrument; unmanaged Macs should rely on the in-app lock and attended
sessions.
