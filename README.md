# Recruiter networking for Passpoli users

Derived from GodsScion/Auto_job_applier_linkedIn
(https://github.com/GodsScion/Auto_job_applier_linkedIn). Original MIT license included.
Choose between connection requests, LinkedIn Easy Apply applications, and the career workspace. Each task uses separate records and task-specific setup.

## Local control panel

Open `start.command` on macOS, `start.bat` on Windows, or run
`sh start.sh` on Linux. A browser opens a local-only control panel.
Choose **Connection requests**, **Easy Apply jobs**, or **Career workspace** first.
Fields change with the task. Save settings, then Start. Résumé uploads are copied
into this app's private folder; no website is hosted publicly.

A separate terminal opens for the running task. Use it for SSH authentication
and LinkedIn login confirmation, then return to the panel and Refresh results.
The panel stores no SSH passwords. Keep the panel's server terminal open while
using the page. On Linux, a graphical terminal such as gnome-terminal, konsole or
xterm is required to start tasks from the panel. Otherwise use the terminal launcher.

Normal startup opens the local control panel directly. There is no initial numbered
terminal menu. Use `--network`, `--jobs`, or `--career` only for direct terminal tasks.

## Before starting

1. Extract the entire ZIP into its own folder.
2. Install Python 3.11 or newer, Google Chrome, and the OpenSSH client.
   Windows users can enable OpenSSH Client in Windows Optional Features.
3. Connect to IITB Wi-Fi or your working IITB VPN.
4. If a previous networking batch is still running, use its terminal. After it
   finishes, type `close` to exit. Do not launch two copies.
5. Close any leftover Chrome window opened by THIS app. Normal personal Chrome
   windows can stay open: the app uses a separate browser profile.

## Start

- Windows: double-click `start.bat`.
- macOS: double-click `start.command`. If the extracted file lost executable
  permission, open Terminal in the extracted folder and run `sh start.sh`.
- Linux: open a terminal in the extracted folder and run `sh start.sh`.

**The default is SEND mode, up to 5 invitation attempts per batch.** The launcher
prints this before setup and again before opening the networking workflow.
No extra execute command is needed. The limit is a local budget, not LinkedIn's
allowance. For a different budget use `sh start.sh --limit 10`, or on Windows
`start.bat --limit 10`. An optional `--preview` searches without sending.

## First run

1. Enter target roles, one at a time; press Enter on an empty line to finish.
2. Enter preferred locations the same way.
3. Answer `Would you like to add your personal information now? [y/n]`.
   Enter `n` to start networking without education, experience, name, or profile URL.
   The launcher offers personal setup again on the next launch until completed.
4. Enter the number of invitation attempts for this batch, from 1 to 100.
   Press Enter to use 5. This is your batch budget, not a LinkedIn allowance.
5. Use your own Passpoli account when asked. Your username is saved once; the
   host and OpenJev endpoint are automatic. SSH may ask for a password (typing
   is hidden) unless your SSH key/agent already handles authentication. Passwords
   are not stored. Verify any first-time host fingerprint normally.
6. Close any old app Chrome window when prompted and press Enter. Normal Chrome
   windows can stay open. Sign in to LinkedIn if needed and confirm the signed-in
   account is yours. In Chrome choose Me > View Profile, copy its URL, then return
   to the terminal and paste it. This one-time account detail is saved even if
   you skipped the optional personal profile. Each run asks you to confirm it.

Recruiters and IIT Bombay IEOR alumni are selected by default. The control panel
lets you also select managers/team leads, IIT Bombay alumni from any department,
IIT Bombay faculty, and professionals in your target roles. Searches use your saved roles and locations. OpenJev is configured
at `http://127.0.0.1:11436`; Passpoli defaults to `10.119.2.11`.

If you answer `y` to personal setup, separate questions collect name, profile URL
(with an example), education, experience, availability, and work authorization.
These improve matching and career answers, but are not needed for networking.
Missing facts remain unknown; selecting alumni does not assert that you personally
attended IIT Bombay. Existing complete profiles are reused without re-entering them.

## Later runs

Double-click the launcher again. Dependencies install only when requirements
change. Roles, locations and the Passpoli username are reused. Incomplete personal profiles are offered again. The batch limit is asked on each launch unless you supplied `--limit`. A healthy existing
model endpoint/tunnel is reused. Otherwise the launcher opens a new tunnel with
your saved SSH details. When you exit, it closes only the tunnel it started.

After a batch, Chrome stays open. Type `run` in the same terminal for another
batch, or `close` to exit. On uncertainty or a platform restriction, the batch
stops; an uncertain contact is never automatically retried. Do not bypass checks.

## Files and privacy

- `profile.json`: your background, preferences and model settings.
- `passpoli.json`: your SSH username and host; no password.
- `private/browser/`: your LinkedIn browser session.
- `private/career.sqlite3`: contact decisions and durable invitation history.
- `private/last-run.json`: latest completed batch, which may be stale after a crash.

Never redistribute these personal files or your `.venv`. Share only the original
clean ZIP. Keep your history to prevent duplicate or uncertain invitation retries.
Previously rejected contacts are reconsidered after targeting changes. Contacts with an outreach record, including uncertain invitations, are never retried automatically.

The shared OpenJev server receives candidate descriptions plus education,
experience, target roles/locations, availability and authorization facts. It does
not receive your SSH password. All users on Passpoli can reach the loopback model
port; it has no individual API keys or quotas. GPU capacity is shared. No model
weights or SSH credentials are included. Model licensing is separate from the
included MIT software license.

If SSH fails, check campus/VPN access and your own normal SSH login. If the tunnel
works but health fails, ask the model owner to check the running service. It is
not guaranteed to restart after a server reboot. If local port 11436 is occupied,
close your obsolete tunnel or edit the endpoint port in `profile.json`; the
launcher forwards that local port to Passpoli port 11436.

The app opens each new candidate’s profile and verifies the URL and owner heading before asking the model to decide. It checks for populated sections and visible loading indicators. On a partial read the model receives the matching result card and populated sections after the reader verifies the owner. A partial read without an explicit match goes to review. Relevance does not establish a vacancy, visa sponsorship, or compatible
start date. Pending is required before counting a send. No scheduler is installed.
Windows launcher execution has not been verified on a Windows host.

## Contact categories

Choose any combination of contact categories in the panel. Recruiters and IEOR
alumni are the defaults; managers, broader IIT Bombay alumni, IIT Bombay faculty,
and professionals in your target roles are optional. Searches alternate between
the selected categories.
Alumni do not have to be recruiters, but visible descriptions must establish
IIT Bombay, IEOR, and completed study. Ambiguous evidence goes to review.

## Local career workspace (new)

The repo also includes a terminal career workspace adapted from
https://github.com/ai-job-search-dev/ai-job-search at commit
`d554e797f9aecfa46185cc54fdbb6457f5d7e681`. Attribution, source notes and its MIT
license are in `modules/vendor/ai_job_search/`. No hosted website is involved.

Start with `sh start.sh --career` on macOS/Linux, or `start.bat --career` on Windows.
Career mode does NOT run networking or submit applications. It offers:

1. Import a saved `.txt`/`.html` posting with company, title and original URL.
   Tracking parameters are removed for duplicate detection; hidden HTML is cleaned.
2. List tracked jobs ranked by model fit score, with coverage and review decisions.
3. Evaluate technical, experience, behavioral and career fit, with exact source
   quotes and separate authorization, availability, location, language and funding
   checks. Unknown facts stay unknown. Scores describe model judgment, not odds of
   an offer. Scores with partial coverage must be read with that limitation.
4. Generate a cover-letter draft, suggested résumé bullets, interview questions,
   STAR prompts and company questions. A second model pass reviews unsupported
   claims. Drafts and evidence are saved as Markdown in `private/packets/`;
   originals are not overwritten. This does not generate or upload final PDFs.
5. Answer form questions: the text model drafts with profile evidence; OpenJev
   selects among supplied options. Unanswered facts become clarification questions.
   This terminal feature does not automatically fill a website form.
6. Record outcomes with a factual note. These are user-reported outcomes, not
   invented submission confirmations. An append-only event history preserves notes.
7. Import postings from an existing `career.sqlite3` opportunity queue read-only.

`career-settings.json` defaults to text model `qwen3.8:27b` on local port 11434
and OpenJev on 11436. The launcher tunnels missing local services through your
saved Passpoli account (remote Ollama port 11435, remote OpenJev port 11436).
Edit the settings file for a different installed text model or endpoint. Services
must already be running; the launcher does not install weights or restart GPU jobs.
SSH forwarding is isolated from unrelated rules in your SSH config. Standard key
paths/ssh-agent work; config-only identity/proxy settings are not inherited.

Add factual résumé/project/achievement details in `private/evidence.txt` for richer
answers. Optional profile fields include skills, languages, projects, achievements
and behavioral_preferences. These facts go to the configured model server. Do not
include passwords or unverified claims. Sparse profiles intentionally produce
review flags instead of invented qualifications.

A draft's automated review is not a guarantee of correctness. Read the evidence
and text before using it. No paid Claude subscription, Bun, LaTeX, website hosting,
or public server is required by this integrated workflow. The upstream's other
portal-specific search CLIs and PDF layout tools have not been imported.


## Where to act during startup

- Installing dependencies: wait in the terminal for setup to finish.
- SSH prompt: type your own password in the terminal; characters are invisible.
  Press Enter once. If a key signs you in, there may be no password prompt.
- Model connection: wait for “Model connection is ready”; do not start another copy.
- LinkedIn opens: sign in in Chrome, choose Me > View Profile, and copy the URL.
  Return to the terminal, paste the URL, and press Enter to confirm the account.
- Batch running: keep Chrome and the terminal open. Avoid navigating the app's
  Chrome window while it is working.
- Batch stopped: read the result. `uncertain` means no confirmed send and no retry
  for that contact. Type `run` for another batch or `close` to exit.
- Career draft ready: open the printed Markdown path in a text editor to review;
  return to the terminal menu afterward. Draft generation never submits a job.


## LinkedIn Easy Apply

Choose Easy Apply in the panel, or run `sh start.sh --jobs` / `start.bat --jobs`.
Applications require a complete personal profile, your application email and phone,
current city, and an existing PDF résumé. The application limit counts jobs
assessed/attempted; verified submissions can be fewer. `--preview` stops before
Submit; in the panel use the Preview checkbox. The normal jobs task enables Submit
for supported, eligible applications.

The runner uses the original project's LinkedIn search/account verification helpers
and adapts its modal-scoped Easy Apply workflow without importing personal defaults.
It searches your roles and locations with the Easy Apply filter, checks fit and
eligibility, opens the application modal, uploads the chosen PDF, and fills supported
text, numeric, select and radio fields. Text answers use the configured text model;
explicit choices use OpenJev. A literal source quote is required for known answers.
The chosen résumé filename must appear in the form before submission can proceed.

Only a shortlist with no unknown eligibility gates advances automatically. Sparse
profiles or unstated sponsorship/start requirements can therefore defer many jobs.
Unknown form answers pause in the task terminal: enter the answer and choose its
reuse scope to continue, or type skip to leave the application blocked. Unsupported
autocomplete controls, consent checkboxes, validation errors, restrictions, and
uncertain submissions still stop for inspection.
External employer applications are recorded as unavailable/handoffs, never submitted.
A visible application-sent/submitted receipt is required to count success. A click
alone is not success. The durable `easy_apply_jobs` table prevents automatic retries,
including interrupted or uncertain attempts. Existing reviewed/blocked entries are
also not automatically retried in this version.

This is a conservative English-UI implementation. It does not promise support for
every LinkedIn form layout. Browser validation used local fixtures, not a live job
submission. Inspect the first live run and its blockers before raising the batch
limit. Application details are saved in `private/career.sqlite3` and the latest
completed report in `private/applications-last-run.json`. If a task crashes, the
previous report may remain; use durable records and terminal output.


## Learning answers during applications

When the model cannot establish a form answer, return to the task terminal. It
shows the exact question and job URL. For choices, enter the displayed option
number; for written fields, enter the exact value. Use `skip` to leave the
application blocked instead of guessing.

After answering, select how it should be remembered:

1. Reusable personal fact — usable on other applications.
2. This job only (default) — for employer/country-specific answers.
3. Today only (UTC) — for temporary facts such as current offer deadlines.

The answer is appended to `profile.json` under `confirmed_answers`, with the
question, options, job URL, scope and timestamp. It is available immediately to
continue the current form. Exact matching questions reuse it directly; related
questions can use relevant saved answers as evidence for the model. Job-specific
answers stay with that job. Changing personal profile facts invalidates old
remembered answers so stale information is not silently carried forward.

No passwords are requested through this answer-learning feature. These saved
application facts are private profile data and are excluded from the share ZIP.


## Structured personal fields

The local panel separates each qualification into degree, specialization,
institution, study status and graduation month. Add or remove qualification entries
with their buttons. Work experience has separate years, job title, employer and
responsibilities. Authorization has separate authorized countries, sponsorship
status and country-specific restrictions. Existing free-text information remains
unchanged until you edit the replacement fields; prior changed values are retained
in the private profile edit history.


Target roles are free text: add or replace any role, one per line, then save and
start a new batch. Searches and model instructions use those roles. Changes to
roles/categories allow previously skipped profiles to be evaluated again when
rediscovered. Durable outreach records still prevent retries of anyone already
contacted or marked uncertain. Restart an already-running task after changing
settings; it loaded the previous profile at startup.

## Remembering LinkedIn sign-in

Use the same extracted app folder each time: its `private/browser` directory holds
the dedicated Chrome session. A new extraction into another folder has a different
session. Do not delete the private browser folder when updating the app.

The runner now checks the saved session and automatically verifies the expected
LinkedIn profile through LinkedIn's own-profile URL. It no longer asks for a profile
URL every run when the session and expected account are verified. A mismatched
account stops the task. Manual confirmation is still needed for first-time setup
or when the existing session cannot be verified.

Optionally use **LinkedIn sign-in → Save in system keychain** in the local panel.
The login email/phone and password are stored via the OS credential service; the
password is never written to profile.json or included in the ZIP. The private
login metadata file contains only a random keychain entry identifier and username.
When a session has expired, the app makes one normal sign-in attempt with the saved
credential. Complete any two-factor/security check in Chrome yourself. Failed or
unavailable keychain access falls back to manual sign-in; there is no plaintext
password-storage fallback. Standard system keychains supported by the keyring
library are required; see https://keyring.readthedocs.io/en/latest/ .

Removing saved credentials does not sign out an existing browser session. Restart
the launcher after updating so it installs the keyring dependency. Saving actual
credentials is opt-in; no credentials were saved during automated testing.

Profile reading waits for the matching owner heading and then makes a bounded scroll pass to load lower sections. Errors distinguish `profile_read_failed` from `profile_assessment_failed` and include the specific cause. Restart the networking task after installing an update; already-running Python processes retain the old code.
