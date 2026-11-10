# Verification — 10 November 2026

Chrome browser test page: http://127.0.0.1:8787/test.html

Observed browser result: **ALL 10 CHECKS PASSED**.

The test iframe uses the separate `meddesk-benchmark-test` IndexedDB database. Normal projects continue to use `meddesk-benchmark`. Synthetic test audio is one second of silence; it does not represent a real participant or microphone quality test.

1. Application initializes in isolated IndexedDB.
2. New participant saves without code changes.
3. New script and editable role persist.
4. Upload assigns the correct participant, role and script snapshot.
5. Chrome decodes the uploaded WAV with the correct duration.
6. Review notes and acceptance persist.
7. Actual export produces valid JSON with embedded audio.
8. Actual browser import restores every audio byte (SHA-256 comparison) and project counts.
9. Invalid project is rejected without overwriting saved data.
10. Reload retains participants, scripts, audio and review status.

Additional checks:

- All three reference files loaded metadata in Chrome: approximately 31 seconds for Shawon, 27 seconds for Mahamudul and 36 seconds for Khairul.
- The user's exported project with four recordings passed validation after the MIME fix. Restore logic preserved the SHA-256 hash of all four audio payloads in a simulated storage test.
- Fixed import validation rejecting recorded `audio/webm;codecs=opus` data URLs.
- JavaScript syntax check passed after the import fix.
- User previously confirmed real microphone recording, audible playback and persistence after refresh.

Limits: automated checks do not verify real microphone sound quality, speaker identity, exact spoken transcript, biometric features or every browser/device. Browser tests intercept the export download click to inspect the generated JSON; the user separately confirmed an actual export download.

To repeat, run START-MEDDESK.cmd and open the test URL in Chrome. Each run adds synthetic records only to the test database. Use http://localhost:8787/ for normal work.
