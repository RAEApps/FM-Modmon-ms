# FM-Modmon-ms

**Multi-station FM modulation monitor** for the SDRplay RSP1A, built on GNU Radio 3.10.

One RSP1A at 9.6 MS/s watches up to **four FM stations at once**: each gets its own
channel filter, stereo demodulator, RDS decoder, measurement chain, alarms and panel,
in a PyQt5 window and an identical web page with live audio.

## What it measures

Per station, refreshed 10× a second:

- **Modulation** – peak +/−, peak deviation, over-100% / over-110% counts, L, R, L+R, L−R,
  ITU-R BS.412 MPX power, and an MPX spectrum to 100 kHz
- **Signal** – RF level, MPX S/N, carrier offset, AM / multipath, pilot level and frequency,
  RDS injection, SCA 67 / 92 kHz injection (and whether an SCA carries audio, data, a tone or nothing)
- **Loudness** – ITU-R BS.1770 / EBU R128 momentary, short-term, integrated and true peak
- **Stereo image** – levels, balance, correlation, width and a goniometer
- **RDS** – PI, PS, RT, RT+, PTY / PTYN, flags, AF, ECC, ODA, CT, group rate and loss, group types
- **IBOC** – via [nrsc5](https://github.com/theori-io/nrsc5): status, MER/BER, PSD, SIS,
  station logo and album art, emergency alerts
- **RadioDNS** – service information and RadioVIS slides (ETSI TS 103 270 / TS 101 499)

## Alarms

Carrier low/lost, audio silence, over-modulation, pilot lost, RDS lost, wrong PI, IBOC
emergency alert, and the FM technical rules of a preset, each limit adjustable per receiver:

| Check | FCC (47 CFR 73) | ISED (BETS-6, BPR-3) |
|---|---|---|
| Modulation | 100% + 0.5% per 1% subcarrier injection, max 110% | same |
| Pilot | 8–10%, 19 kHz ± 2 Hz | same |
| Subcarriers | ≤ 20% total, ≤ 10% above 75 kHz | same |
| Carrier frequency | ± 2000 Hz | ± 1000 Hz |

Alarms go to the event log and optionally to email (SMTP) and webhooks (JSON, Slack,
Microsoft Teams, Discord). A watchdog reopens the SDR after a USB dropout.

> The monitor is a measurement aid, not a type-approved modulation monitor. Carrier
> offset includes the SDR's own tuning error, and levels depend on gain calibration.

## Requirements

- **Windows 10/11** (developed and tested there; some parts – DNS SRV lookups for
  RadioDNS, sign-in autostart – use Windows APIs)
- **SDRplay RSP1A** and the [SDRplay API](https://www.sdrplay.com/api/) 3.x
- **[radioconda](https://github.com/ryanvolz/radioconda)** (GNU Radio 3.10 with gr-rds,
  SoapySDR, NumPy, SciPy, PyQt5)
- **[SoapySDRPlay3](https://github.com/pothosware/SoapySDRPlay3)** built against radioconda's
  SoapySDR (radioconda can't ship it: the SDRplay API is closed source). Put the module in
  `../soapysdrplay3-build/modules` beside this folder, or set `SOAPY_SDR_PLUGIN_PATH`.
- Optional: **ffmpeg** on the PATH for web audio (MP3, AAC, Opus, FLAC)
- Optional: **nrsc5** on the PATH (or in a sibling `../nrsc5*/build/src/` folder) for IBOC

## Running

```bash
C:\ProgramData\radioconda\python.exe fm-modmon-ms.py
```

On start it scans 88–108 MHz, calibrates the RSP1A's gain for the stations found and opens a
receiver on the strongest. *Add receiver* opens more (any that fit in the 7.2 MHz window).
Useful options:

```bash
C:\ProgramData\radioconda\python.exe fm-modmon-ms.py --freqs 94.5 101.7 --country US
```

| Option | |
|---|---|
| `--freqs MHZ …` | start on these stations instead of the saved ones |
| `--country CC` | ISO country (ISED rules for `CA`, FCC otherwise; RadioDNS) |
| `--lna N --ifgr DB` | fixed gain instead of start-up calibration |
| `--web-port N` | web version port (default 8765, `0` = off) |
| `--web-bind ADDR` | `127.0.0.1` keeps the web version on this PC |
| `--web-password PW` | allow the web controls from other computers |
| `--rds-port N` | first raw RDS group feed port (default 7711; `0` = off) |

Run with `--help` for the full list. Receivers and their settings are saved to
`fm-modmon-ms_config.json`; events are logged to `logs/`.

### Environment variables

| Variable | Use |
|---|---|
| `FM_MODMON_WEB_PASSWORD` | web controls password (instead of `--web-password`) |
| `FM_MODMON_SMTP_PASSWORD` | SMTP password for email notifications (never stored in the config) |
| `RADIODNS_CLIENT_ID` | RadioDNS client identifier, for providers that need one |
| `SOAPY_SDR_PLUGIN_PATH` | where the SoapySDRPlay3 module is |

## Web version

`http://<this-pc>:8765/` shows the same panels, updated 10× a second, with each receiver's
audio in the browser. Anyone who can reach the port can watch and listen; the controls
need `--web-password`, or, without one, a browser on the monitor PC itself.

**Security:** the web version is plain HTTP, so the password crosses the network
unencrypted. Use it on a trusted network, bind it to `127.0.0.1` behind a TLS reverse
proxy, or reach it over a VPN. Don't expose it directly to the internet.

## RDS group feed

Each receiver serves its error-free RDS groups over TCP (ports 7711–7714) as hex text, one
group per line – the format of an Inovonics INOmini 633 or RDS Spy – for other RDS software.

## Tests

The tests drive the real receiver chain with a synthetic FM transmitter (`tests/fmtx.py`:
stereo, pilot, RDS per IEC 62106, SCA, AM, noise, carrier offset) and check the readouts
and alarms against known values. No SDR is needed.

```bash
C:\ProgramData\radioconda\python.exe tests\verify_meas.py
```

```bash
C:\ProgramData\radioconda\python.exe tests\rules_test.py
```

## Examples

`examples/` has the simple single-station GNU Radio Companion flowgraphs this started from
(RSP1A and simulated).

## License

GPL-3.0-or-later – see [LICENSE](LICENSE). GNU Radio, gr-rds and PyQt5 are GPL-licensed too.
