# MedDesk Voice Benchmark Studio

A local HTML, CSS and JavaScript workspace for collecting structured voice recordings against reading scripts. Participants can read as different doctor roles, record or upload takes, review audio and export a portable dataset.

**Delivery scope:** voice data collection and human review. This version does not generate biometric voice signatures, automatically identify speakers or calculate benchmark accuracy scores.

## Requirements

- Windows with PowerShell and a current Chrome or Edge browser. Chrome was verified; Edge has not been separately tested.
- A microphone and browser microphone permission for live recording.
- The complete extracted project folder, including `audio/`.

No npm installation, database service, API key or paid service is required. Internet access is optional: Google Fonts provides typography, with local font fallbacks when offline.

## Quick start

1. Extract the ZIP to a local folder. Do not run from inside the ZIP.
2. Double-click `START-MEDDESK.cmd`.
3. Keep the server window open while working.
4. Open **http://localhost:8787/** directly in Chrome. The launcher attempts to open the default browser; open the address manually if needed.
5. On first launch, check that the three reference participants and recordings appear.

To stop the server, close its window or press **Ctrl+C** there. Restart it with the same launcher. Use the same browser profile and address to access saved work.

Do not use VS Code's embedded preview for recording or playback: playback failed in that preview during use, while it worked in Chrome. Opening `index.html` as a file is not the supported launch method.

## Included reference material

| Participant | Initial role | Audio file |
| --- | --- | --- |
| Khairul | Dr. Kabir | `audio/khairul.aac` |
| Mahamudul | Doctor 2 | `audio/mahamudul.mp4` |
| Shawon | Doctor 3 | `audio/shawon.ogg` |

The supplied English voice-signature reading script is included. Doctor roles are editable placeholders, not verified identities. Reference files are imported into browser storage on the first launch of a new workspace. All reference takes start unaccepted and require review.

## Collection workflow

### 1. Select the participant and role

Choose a participant, or click **+ Add** and enter a new name. Set **Role / doctor name** separately. The participant identifies the real speaker; the role identifies the character they read. One person reading three roles is still one speaker.

More than three participants can be added without editing code. Roles can be changed in the interface. This version has no participant rename or individual participant removal control.

### 2. Prepare the script

Select a reading script, or click **+ New**. Edit the title and text directly in the page. The word count updates automatically and changes are saved locally.

Each take captures the script text, title and role used at collection time. Later edits do not rewrite earlier takes' snapshots.

### 3. Confirm collection permission

Explain the actual collection and storage process, then tick the permission checkbox before recording or uploading audio. Switching participants clears the checkbox. This is an operator acknowledgement, not a signed consent form or independent proof of consent.

**Reading-script clarification:** the supplied passage describes a separate proposed MedDesk system. Its statements about encrypted server storage, biometric signatures and recordings not being kept do not describe this tool. This tool retains recordings locally until deleted. Explain that distinction before collection.

### 4. Record or upload

For a new recording:

1. Select the correct participant, role and script.
2. Confirm permission and click **Start recording**.
3. Allow microphone access when the browser requests it.
4. Read naturally at a steady microphone distance.
5. Click **Stop & save**. The new take appears in **Review recordings**.

For existing audio:

1. Select the correct participant, role and script, and confirm permission.
2. Click **Upload audio** and select one or more files.
3. All selected files are assigned to the current participant and script. Upload each speaker's files separately to avoid incorrect attribution.

Common accepted extensions include WAV, MP3, AAC, M4A/MP4, OGG, WebM and FLAC. An accepted extension does not guarantee every codec in that container will play in every browser. Microphone recording format is selected according to browser support.

### 5. Review each take

Listen for audibility, completeness, clipping, background noise and whether the intended text was spoken. Add notes and click **Accept take** when suitable; the button can toggle acceptance off again.

Use the participant filter to narrow the list. **Audio** downloads an individual take. **Delete** removes a take after confirmation. Acceptance is a human review label, not an automated score. Export includes accepted and unaccepted takes with their review flags.

For speech-to-text evaluation, the reference transcript must reflect what was actually said. This application does not transcribe recordings or automatically resolve differences between the prompt and spoken words.

## Saving and backups

### Automatic local saving

Scripts, participants, recordings and review changes are stored in the current browser profile's IndexedDB database, named `meddesk-benchmark` for normal work.

Storage belongs to the exact scheme, hostname and port. `localhost:8787` and `127.0.0.1:8787` have separate workspaces; other browsers or profiles also have separate data. Clearing browser data or using private browsing can remove work. Large projects can exceed browser storage or memory limits. Export regularly.

### Export a complete project

1. Click **Export project**.
2. Keep the downloaded `meddesk-benchmark-YYYY-MM-DD.json` file in an appropriate backup location.
3. Export again after important collection or review sessions.

The JSON includes participants, scripts, all takes, script snapshots, roles, take numbers, timestamps, source labels, notes and acceptance flags. Audio is embedded as base64 data URLs, so separate audio files are not needed to restore it. Base64 increases file size and is not encryption.

Export downloads a local copy; it does not upload the project to a remote server. Backups contain people's voices and should be shared only with intended recipients.

### Restore or move to another computer

1. Start the application on the destination computer or browser.
2. Export the destination's current project first if it needs to be preserved.
3. Click **Import project** and select the exported JSON.
4. Confirm replacement of the current local project.
5. Check participant and take counts, then play a recording.

Import **replaces** the project; it does not merge projects. Unsupported or malformed backups are rejected. Previously downloaded backups are independent of browser storage.

## Handoff to another person

ZIP the complete project folder, preserving `audio/`. Include an exported project JSON separately if the recipient needs collected recordings and review progress: browser-saved changes are not included merely by zipping the source folder.

The recipient should extract the ZIP, run `START-MEDDESK.cmd`, open Chrome and import the supplied backup if applicable.

## Deletion behavior

- **Delete** on a recording removes that take from the current browser project.
- **Delete local project** removes local recordings and edits, and restores the default roster and script. It does not automatically reload reference recordings into the reset project.
- Neither action deletes original files in `audio/`, downloaded recordings or exported backups.

There is no in-app undo for deletion. Keep an export if restoration may be needed.

## Verification

On **10 November 2026**, the Chrome test page reported **ALL 10 CHECKS PASSED**. These cover initialization, participants, roles, scripts, uploads and duration, review persistence, export, import with SHA-256 audio comparisons, invalid-import handling and reload persistence.

To repeat:

1. Start the server.
2. Open **http://127.0.0.1:8787/test.html** in Chrome.
3. Wait for the final result above the embedded workspace.

Tests use the separate `meddesk-benchmark-test` database and synthetic audio. Normal project data is untouched. Each run adds test records to the test database. Export content is inspected without triggering a download during the automated checks.

The user separately confirmed real microphone recording, audible playback, refresh persistence and an actual export download. A supplied four-recording backup passed validation after a fix for `audio/webm;codecs=opus` import support.

See [TEST-RESULTS.md](TEST-RESULTS.md) for evidence and limits. Automated tests do not assess microphone sound quality, spoken content, speaker identity or every device/browser.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Page will not open | Run the launcher, keep its window open and use `http://localhost:8787/`. |
| Port 8787 unavailable | Another instance may already be running. Try the address; close an old server window before restarting if needed. |
| Player shows `0:00 / 0:00` | Open directly in Chrome. Read the error below the player, if shown. Download the original file to check external playback. |
| Microphone will not start | Confirm the collection checkbox, use localhost, check browser and Windows microphone permissions, and check the input device. |
| Data appears missing | Use the original browser profile and exact hostname/port. Import a backup if storage was cleared. |
| Reference audio missing | Confirm `audio/` was included. Existing workspaces are not automatically reseeded; upload missing files for the correct participants. |
| Import fails | Use an unmodified JSON exported by this tool. After a code update, press **Ctrl+Shift+R** to load the current version. |
| Local saving fails | Export immediately if possible. Check disk space and browser storage restrictions. |

## Project structure

| File | Purpose |
| --- | --- |
| `index.html` | Page structure and controls |
| `style.css` | Responsive interface styles |
| `app.js` | Recording, uploads, local storage, review and export/import |
| `audio/` | Supplied reference files |
| `START-MEDDESK.cmd` | Windows entry point |
| `serve.ps1` | Loopback HTTP server on port 8787 |
| `test.html`, `test.js` | Isolated browser integration checks |
| `TEST-RESULTS.md` | Verification evidence and limitations |

## Architecture and limits

The client uses browser APIs including `MediaRecorder`, `getUserMedia`, `IndexedDB`, `Blob`, `FileReader` and object URLs. The PowerShell server serves local assets on loopback. It has no audio-upload or remote-storage endpoint.

This is a local collection workspace. Accounts, authentication, encrypted biometric storage, synchronization, transcription, diarization, speaker embeddings, speaker verification and recognition scoring require additional implementation. The three reference speakers provide starter data, not evidence of broad benchmark performance.
