# FM-Modmon-ms

Multi-station FM modulation / RDS monitor for the SDRplay RSP1A (GNU Radio 3.10, PyQt5),
one file: `fm-modmon-ms.py`, plus its web page `fm-modmon-ms-web.html`.

- Python: radioconda's, `C:\ProgramData\radioconda\python.exe` (has GNU Radio, gr-rds, SoapySDR).
- Run: `C:\ProgramData\radioconda\python.exe fm-modmon-ms.py` (`--help` for options).
- All suites in parallel (~2 min, slowest first; name words filter): `tests\run_all.py [words] [-j N]`.
- Test (no SDR needed; synthetic transmitter): `tests\verify_meas.py` and `tests\rules_test.py`;
  both exit non-zero on a wrong reading. Run both after touching measurements or alarms.
  `tests\setup_test.py` covers the setup wizard, password hashing and Credential Manager.
  `tests\radiovis_test.py` covers the RadioDNS slideshow against local fake servers.
  `tests\state_test.py` covers the panel's plain readings, alarm states, History, the detail tabs and LRA.
  `tests\centre_test.py` covers where the SDR centres (off DC, off IQ images, inside the IF filter).
  `tests\rds_feed_test.py` covers the RDS group TCP feed (a stalled client never blocks the decoder).
  `tests\gain_test.py` covers the band scan's and gain calibration's ADC headroom (a simulated, clipping RSP1A,
  and a one-gain-stage SDR).
  `tests\record_test.py` covers the on-demand measurement records (`Recorder`, the REC chip) and
  `prune_files` (old event logs and records deleted after `keep_days`).
  `tests\notify_test.py` covers `Notifier` (email to a fake SMTP server, each webhook format, batching,
  retries) — `_deliver`'s retries default binds `NOTIFY_RETRY_S` at class definition: patch `__defaults__`.
  `tests\web_test.py` covers the web server (GETs, POST checks, sign-in, sessions, the command queue).
  `tests\recovery_test.py` covers SDR loss: the watchdog, reopening in place, and the B210's restart.
  `tests\sdr_test.py` covers the SDR profiles (`SDRS`: RSP1A, RSP1B, RTL-SDR, B210) and a station at each one's rate.
  `tests\antenna_test.py` covers antenna tuning (`window_snrs`, `AntennaTuner`, `AntennaLoop` on a
  synthetic flowgraph, the window and web controls).
- `tests\alarm_ack_test.py` covers alarm priorities and acknowledgement. The alarm log (`AlarmTable.episodes`)
  is the one record of what waits to be acknowledged; `MainWindow._sync_unacked` copies it to each
  receiver's `alarms.unacked` for its lamps, status cell and row tint. Run it after touching alarms.
- `tests\theme_test.py` holds the visual system: every colour in the GUI code and the web page must be a
  `THEME` value (add a token, don't add a hex), type sizes from `TYPE`, corners from `RADIUS`, no emoji,
  and the text colours' contrast. The stylesheet is `APP_QSS` with `%token%` placeholders (`app_qss()`).
- `tests\inventory_test.py` covers the SDR inventory and profiler (a simulated radio; no SDR needed).
  On hardware: `fm-modmon-ms.py --scan-sdrs` and `--profile-sdr SERIAL --config <a copy>` (a built-in kind
  is printed beside its built-in profile, not saved).
- New SDRs: `scan_sdrs` classifies every radio by driver + serial (`FoundSdr`: known / learned / new /
  failed / unusable). `profile_sdr` measures a new one (each step in an `_in_child` helper) into an
  `SdrProfile` saved in the settings file's `sdrs` section; `load_learned` adds those to `SDRS` under
  their own key (`BUILTIN_SDRS` are never overridden). Bump `PROFILER_VERSION` when the profiler's
  results change, so learned profiles are made again.
- SDRs: one `SdrProfile` each in `SDRS`; `use_sdr()` sets `SAMP_RATE`, `CHAN_DECIM`, `MAX_SPAN` and the
  other rate-derived globals from it. Every station is decimated to the same `QUAD_RATE` (384 kS/s).
  At start-up `detect_sdr()` finds what is plugged in (`find_sdrs`, `choose_sdr`) and switches to it.
  Switching SDR while running (the header's SDR chip) restarts the process (`switch_sdr`, `restart_argv`,
  `--after-pid`): the sample rate changes every filter, and UHD can crash closing a B210 in-process.
  So an SDR with `closes_cleanly=False` (the B210) is never closed in-process: scan and calibration run
  in a helper (`_in_child`, `--child-call`), exit is `os._exit`, and SDR lost restarts (`--recovering`).
  Known, left as is: unplugging a streaming B210 aborts the process (UHD 4.8 throws again while unwinding
  its USB buffers → `std::terminate`; the same through gr-soapy and gr-uhd), so SDR lost never runs for
  that case. Surviving it would need the B210 in its own capture process, as fm-band-monitor does.
- CPU: `tools\profile_cpu.py` profiles the monitor on the RSP1A (~70 s; needs the SDR free).
  Pass `--config` with a copy that has notifications off when testing here.
- Install: `install.ps1` (run from GitHub with `irm .../install.ps1 | iex`). It pins
  third-party download URLs + SHA-256; the SoapySDRPlay3 module and nrsc5 come from the
  `deps-2026.11` release. Rebuilt either? Publish a new release and update the URLs and hashes.
  Two exceptions, by design: the app itself is this repo's `main` (no hash), and the SDRplay
  API, which only SDRplay's site offers, is checked by its Authenticode signer.
- Public repo, GPL-3.0-or-later: no secrets, personal data, local paths or captured audio/IQ
  in commits. Config and logs are git-ignored.
