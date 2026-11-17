# FM-Modmon-ms

Multi-station FM modulation / RDS monitor for the SDRplay RSP1A (GNU Radio 3.10, PyQt5),
one file: `fm-modmon-ms.py`, plus its web page `fm-modmon-ms-web.html`.

- Python: radioconda's, `C:\ProgramData\radioconda\python.exe` (has GNU Radio, gr-rds, SoapySDR).
- Run: `C:\ProgramData\radioconda\python.exe fm-modmon-ms.py` (`--help` for options).
- Test (no SDR needed; synthetic transmitter): `tests\verify_meas.py` and `tests\rules_test.py`;
  both exit non-zero on a wrong reading. Run both after touching measurements or alarms.
  `tests\setup_test.py` covers the setup wizard, password hashing and Credential Manager.
- Public repo, GPL-3.0-or-later: no secrets, personal data, local paths or captured audio/IQ
  in commits. Config and logs are git-ignored.
