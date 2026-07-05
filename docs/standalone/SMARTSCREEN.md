# Running the unsigned Instrument on Windows (SmartScreen & antivirus)

**Phase 4 · issue 20 · SPEC §14, §20**

The BART Instrument is currently shipped **unsigned** (no code-signing certificate — see
the technical specifications). On Windows that
means the **first launch shows a warning**. This page explains why, how a researcher gets
past it in two clicks, and how an IT administrator can pre-approve it on managed lab
machines. Nothing here indicates the software is harmful.

---

## What is SmartScreen?

Microsoft Defender **SmartScreen** is a safety feature built into Windows 10/11. When you
run a program it has not seen often before — and that is not signed by a recognized
publisher — it pauses with a blue **"Windows protected your PC"** dialog. It is a
reputation check, not a virus scan: brand-new or low-volume apps simply have no reputation
yet, so they get flagged regardless of whether they are safe.

## Why the warning appears here

The Instrument is **unsigned** research software distributed to a small number of labs, so
it has neither a code-signing certificate nor download-reputation history. SmartScreen
therefore flags it on first run. **This is normal and expected** for unsigned in-house
tools — the warning is about *unknown reputation*, not detected malware. The application
runs fully offline and never contacts the network (SPEC §4).

## How to bypass it (researchers)

When you double-click the installer (or the app) and see **"Windows protected your PC":**

1. Click the small **"More info"** link in the dialog.
2. The dialog expands to show the file name and an **"Run anyway"** button — click
   **"Run anyway."**

That's it — this is a **one-time** prompt per file. Subsequent launches do not ask again.
If you do not see "More info", the window may be too small; resize it or scroll.

## IT administrator notes (managed lab machines)

On locked-down or fleet-managed machines, pre-approve the Instrument so researchers never
see the prompt. Because the build is **unsigned, publisher-based allow rules do not apply**
(there is no signature to match) — use **file-hash** rules instead, which is also the most
precise option.

**AppLocker / Windows Defender Application Control (WDAC):**

- Create a **file-hash** allow rule for both executables: the main app
  (`BART Instrument.exe`) and the bundled Sidecar **`bart-sidecar.exe`**. A new hash is
  generated on every release, so update the rule when you deploy a new version.
- Avoid broad *path* rules (e.g. allowing all of `%LOCALAPPDATA%`) — they are far weaker
  than a hash rule.

**Group Policy:**

- AppLocker rules are authored under *Computer Configuration → Windows Settings → Security
  Settings → Application Control Policies*. Deploy the hash allow-list there for domain
  machines.

**Microsoft Intune:**

- Push the same WDAC/app-control hash allow rules via an Intune **app-control** policy.
- The Defender SmartScreen CSP exposes **`AllowSmartScreen`**; setting it to disable
  SmartScreen org-wide is a blunt instrument and **not recommended** — prefer a targeted
  hash allow rule so SmartScreen stays on for everything else.

## Antivirus false positives

The Sidecar **`bart-sidecar.exe`** is a **PyInstaller** one-file binary: the Python runtime
plus the scoring engine are packed into a single self-extracting executable. Some antivirus
engines flag that *packing pattern* as a generic **heuristic / "packer" false positive**,
even though the contents are benign. If an AV quarantines it, the app will fail to start
its Sidecar.

**Windows Defender** — add an **exclusion** for the install folder or the
`bart-sidecar.exe` file: *Windows Security → Virus & threat protection → Manage settings →
Exclusions → Add an exclusion → File/Folder*. On managed machines, push the same exclusion
via Group Policy / Intune (Defender ASR & exclusion policies).

**Third-party AV** (e.g. Sophos, CrowdStrike, McAfee, ESET) — add a file or folder
exclusion (sometimes called an "allow-list" or "trusted application") for the install
directory through that product's console. If your AV submits "unknown" binaries for cloud
analysis, you can also submit the file as a false positive to speed up clearance.

## Future: code signing

Purchasing an **OV** (Organization Validation) or **EV** (Extended Validation) **code-signing
certificate** and signing the installer + executables would remove the SmartScreen warning
(EV grants reputation immediately; OV builds it over time) and sharply reduce AV false
positives. That is a procurement decision, deliberately deferred for now — the rationale and
ownership are recorded in the technical specifications.
