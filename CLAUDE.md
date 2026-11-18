# FM-Modmon-ms

Multi-station FM modulation / RDS monitor for the SDRplay RSP1A (GNU Radio 3.10, PyQt5),
one file: `fm-modmon-ms.py`, plus its web page `fm-modmon-ms-web.html`.

- Python: radioconda's, `C:\ProgramData\radioconda\python.exe` (has GNU Radio, gr-rds, SoapySDR).
- Run: `C:\ProgramData\radioconda\python.exe fm-modmon-ms.py` (`--help` for options).
- Test (no SDR needed; synthetic transmitter): `tests\verify_meas.py` and `tests\rules_test.py`;
  both exit non-zero on a wrong reading. Run both after touching measurements or alarms.
  `tests\setup_test.py` covers the setup wizard, password hashing and Credential Manager.
  `tests\radiovis_test.py` covers the RadioDNS slideshow against local fake servers.
  `tests\state_test.py` covers the panel's plain readings, alarm states and History.
  `tests\centre_test.py` covers where the SDR centres (off DC, off IQ images, inside the IF filter).
  `tests\rds_feed_test.py` covers the RDS group TCP feed (a stalled client never blocks the decoder).
- CPU: `tools\profile_cpu.py` profiles the monitor on the RSP1A (~70 s; needs the SDR free).
  Pass `--config` with a copy that has notifications off when testing here.
- Install: `install.ps1` (run from GitHub with `irm .../install.ps1 | iex`). It pins
  download URLs + SHA-256; the SoapySDRPlay3 module and nrsc5 come from the `deps-2026.11`
  release. Rebuilt either? Publish a new release and update the URLs and hashes.
- Public repo, GPL-3.0-or-later: no secrets, personal data, local paths or captured audio/IQ
  in commits. Config and logs are git-ignored.
