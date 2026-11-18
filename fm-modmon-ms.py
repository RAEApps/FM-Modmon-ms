#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# FM-Modmon-ms: FM broadcast monitor for the SDRplay RSP1A (GNU Radio 3.10).
# Copyright (C) 2026 RAE Apps
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version. It is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License (LICENSE) for more details.
"""
FM-Modmon-ms: FM broadcast monitor for the SDRplay RSP1A (GNU Radio 3.10).

On startup the RSP1A sweeps 88-108 MHz (about 3 s) and opens one receiver
on the strongest station it finds. "Add receiver" opens more, up to four,
each on the strongest station not yet open that still fits; each receiver
has a dropdown of the stations found and a button to remove it. The 9.6 MS/s
SDR window re-centres on the receivers' stations, so a station is only
offered when it fits within 7.2 MHz of the others. Each receiver gets its own
channel filter, stereo WBFM demodulator, RDS decoder and measurement blocks,
and its own "radio" panel. Each panel has a Play button; one station plays
at a time (stereo, 75 us de-emphasis; falls back to mono without a pilot).

Run with radioconda's Python:
    C:\\ProgramData\\radioconda\\python.exe fm-modmon-ms.py
    C:\\ProgramData\\radioconda\\python.exe fm-modmon-ms.py --lna 2 --ifgr 35
    C:\\ProgramData\\radioconda\\python.exe fm-modmon-ms.py --freqs 94.5 101.7
    C:\\ProgramData\\radioconda\\python.exe fm-modmon-ms.py --no-scan --web-port 0

Each panel's audio source can be analog FM, SCA audio from the 67 or 92
kHz subcarrier, or IBOC (MPS, SPS1-SPS3). IBOC is decoded by nrsc5 (--nrsc5;
default: nrsc5 on the PATH, else a build in a sibling folder such as
../nrsc5/build/src/nrsc5.exe), which plays it on the default
sound device; its status, station name, title, artist, bit rate, MER and BER
show on the panel's IBOC line, the station logo and the song's album art
beside it, its programme service data (artist, title,
album, genre, comment) on the PSD line and its station information (name,
slogan, message) on the SIS line. IBOC emergency alerts raise an alarm and
their text goes to the event log.

RadioDNS (ETSI TS 103 270): each station is looked up from its frequency,
PI and GCC (ECC, or derived from --country) and, while IBOC plays, its IBOC
station ID. Where the station's RadioDNS service information (SPI) can be
read, its name and logo show on the panel's RadioDNS line; where it has a
RadioDNS slideshow (RadioVIS, ETSI TS 101 499: Server-sent Events, or the
older Stomp or HTTP transports), its current slide (usually the album art)
shows as the album art (after IBOC's own); clicking it opens the slide's
link, and the slideshow text shows on the RadioDNS line. Slides sent ahead
with a trigger-time show at that time. The RadioDNS line shows only while RadioDNS
works for the station; the logo is used
when no IBOC logo is on air. Some providers need a client identifier: set
RADIODNS_CLIENT_ID (or --radiodns-client-id). Images and service information
are cached for the session only (a %TEMP% folder deleted on exit).

Each receiver has a settings button (name, de-emphasis, stereo/mono, play
volume, PTY names, expected PI, RDS feed, alarms and their thresholds). The
open receivers, their stations and settings are saved to fm-modmon-ms_config.json
whenever they change, and restored at the next start (--freqs overrides).

The web version of the app is served on http://<this-pc>:8765/ (unless
--web-port 0): the same receiver panels, drawn in the browser and updated 10x
per second, with the same controls, and each receiver's audio as a stream
in the listener's choice of MP3, AAC, Opus or FLAC (/audio/1.mp3, .aac,
.opus, .flac ... /audio/4.*; encoded by ffmpeg, --ffmpeg and --web-audio)
for the page's player or any media player. Anyone who can reach the port
can watch and listen; the controls need the web password (set in Setup, or
--web-password / FM_MODMON_WEB_PASSWORD, which take precedence), or, when no
password is set, a browser on this PC (http://localhost:8765/). The password
is kept only as a salted hash (PBKDF2) in the settings file.

Each receiver also serves its raw RDS groups over TCP (receiver 1 on port
7711, 2 on 7712, 3 on 7713, 4 on 7714 by default, or the port set in the
receiver's settings; --rds-port 0 turns them off) as hex text, one
group per line, the format of an Inovonics INOmini 633 or RDS Spy, so RDS
software that reads one of those over TCP (address <this-pc>:7711) can
decode the groups itself. The feed follows whatever station its receiver
is tuned to, and closes when the receiver is removed. Alarms and station changes go to
the event log in the window, the web view and logs/fm-modmon-ms_events_YYYY-MM-DD.log.

First run: the first start (or --setup, or Settings > Run setup again) opens
a short setup: where the monitor is (which technical rules the alarms check:
ISED in Canada, else FCC), the web version (on or off, this PC only or the
network, its port and password), notifications, and starting with Windows.
Cancelling keeps the defaults; it doesn't come back unless asked for.

Notifications: "Settings" (in the window) sends alarms raised and cleared,
SDR lost and recovered, and start / stop by email (SMTP; the password is kept
in Windows Credential Manager, never the settings file;
FM_MODMON_SMTP_PASSWORD, if set, is used instead) and / or a webhook (generic JSON, Slack, Microsoft Teams workflow or
Discord). Events within NOTIFY_BATCH_S of each other go out as one message;
failed sends are retried, and failures go to the event log.

SDR watchdog: when no samples arrive from the RSP1A for SDR_STALL_S (USB
dropout, driver fault), "SDR lost" is logged and notified, alarms pause, and
the RSP1A is reopened until samples flow again; the meters then restart.
Settings can also start FM-Modmon-ms when you sign in to Windows.

Gain: at start-up (unless --lna or --ifgr is given) the RSP1A's LNA state
and IF gain reduction are calibrated for the stations being received: for
each LNA state the IF gain is set to keep the ADC's peaks CAL_PEAK_DBFS below
full scale, and the state that gives the open stations the best average
S/N over the noise floor is kept: the least gain within CAL_TOLERANCE_DB of
the best (once antenna noise dominates, more gain only costs headroom). Gain then stays fixed, so RF
levels are comparable. "Recalibrate gain" repeats it on the running receivers
(for example after the SDR window has moved); their meters restart afterwards.
While running, the wideband samples' peak is watched: when it reaches CAL_CLIP
(the level calibration counts as overload) in ADC_OVERLOAD_N of
ADC_OVERLOAD_WINDOW_S seconds, "SDR overload" is logged and notified and the
gain chip turns red, until ADC_OVERLOAD_CLEAR_S pass without one.

Measurements (refreshed 10x per second):
  RDS
    PI, PS, RT, PTY, flags, AF      from gr-rds' parser
    RT+, PTYN, ECC, ODA list, CT    decoded here from the raw groups (CT as
                                    local time, with its offset from UTC)
    Groups/s, group loss            error-free groups; 11.4/s = no loss
    Group types                     share of each group type received
    Data services                   paging (7A), TMC (8A), EWS (9A), other
                                    ODAs and SCA data: present or lost, with
                                    their share; identified, never decoded
                                    (addressed, often encrypted, and not to be
                                    divulged: Radiocommunication Act s. 9(2)).
                                    Paging shows its 1A fields (paging codes,
                                    operator code, paging ID); no field names
                                    the provider, so each receiver can name its
                                    services (e.g. 7A=Alert FM)
  Signal (each receiver passes +/-150 kHz of the FM signal, as a modulation
  monitor's wide IF does, so subcarriers and L-R aren't cut)
    RF level        channel power, dBFS (uncalibrated, depends on gain)
    MPX S/N         unweighted, no de-emphasis: 100% mod tone vs. receiver
                    noise in 0-15 kHz, estimated from the 16-18.3 kHz guard
                    band (FM noise rises as f^2; the estimate allows for it)
    Carrier offset  DC of demodulated MPX (station + SDR tuning error)
    AM / multipath  envelope ripple of the carrier, RMS, as % of 100% AM
                    (10% sine AM reads 10%; 0% = clean reception). Peaks
                    are judged only while it stays under 5% (ITU-R SM.1268:
                    echoes 26 dB down); the other rules under 15%
    Sync AM         synchronous AM: the envelope ripple that follows the
                    modulation, as the AM depth it reaches at +/-75 kHz, in %
                    and dB. A mistuned transmitter, filter, combiner or
                    antenna match causes it (Orban: <= -35 dB, -40 dB
                    preferred) - but so does any short-delay echo on the
                    path, identically (a 3 us echo 20 dB down reads ~7%).
                    So it is a figure for this receiving site: the
                    transmitter's own share is at most this, and at a fixed,
                    line-of-sight site its changes (before/after a retune)
                    are the transmitter's. Amber above -35 dB only while
                    AM / multipath has stayed under 5%; marked 'multipath'
                    above that. '-' while the modulation is too light
    Pilot           19 kHz injection, % of 75 kHz (>3% = stereo), and its
                    frequency from the stereo PLL (spec 19 kHz +/- 2 Hz)
    RDS injection   57 kHz subcarrier peak deviation, % of 75 kHz (as
                    encoders are set: 2 kHz = 2.7%), noise removed
    RDS phase       the 57 kHz subcarrier against the pilot's third harmonic,
                    over 5 s: 0 = in phase, +/-90 = quadrature (IEC 62106:
                    either, +/-10 deg). 'drifting' = the RDS encoder isn't
                    locked to the pilot (free-running, or its 19 kHz feed is
                    lost or too low): late RadioText, skipped PS
    SCA 67/92 kHz   subcarrier injection, % of 75 kHz, when one stands
                    10 dB above the empty 77-82 kHz gap; else 'none'. What it
                    carries, from its demodulated signal over ~6 s: AUDIO
                    (programme: level and spectrum keep changing), DATA
                    (steady and stationary; with the symbol rate when it is
                    NRZ FSK), TONE, or IDLE (no modulation). SCA data services
                    are proprietary, so data is identified, not decoded
    IBOC signal     IBOC sidebands found by the start-up scan, in dBc
  Modulation (100% = 75 kHz deviation)
    Peak + / -      1 s peak of positive and negative excursions
    Peak deviation  1 s peak of the 99.9th percentile of |MPX|
    Over 100/110%   excursions above 100% / 110% in the last minute
    L, R, L+R, L-R  1 s peak modulation of each, as transmitted
    MPX power       ITU-R BS.412, 60 s, dBr (0 dBr = +/-19 kHz sine)
    MPX spectrum    0-100 kHz, 500 Hz resolution, dB re 100% modulation
  Loudness (ITU-R BS.1770 / EBU R128; 0 dBFS = 75 kHz deviation)
    Momentary 400 ms, short-term 3 s, integrated (gated, since start/reset),
    true peak per channel (4x oversampled, 1 s hold)
  Stereo image (300 ms window)
    L/R RMS level, balance, correlation (+1 mono, 0 wide, <0 out of phase),
    width (side/mid energy ratio), goniometer
  Alarms (raise/clear after holding 3-30 s)
    carrier low/lost, audio silence, over-modulation, pilot lost, RDS
    lost (but "possibly on N+1" when the carrier, pilot and audio stay
    fine: the N+1 backup transmitter has no RDS encoder; switch that alarm
    off and it is plain RDS lost), wrong PI, emergency alert (IBOC while it plays, or an RT+
    Alarm tag), data service lost (a service on air 5+ min unbroken,
    then gone; 60 s hold), and the
    technical rules of the receiver's rule set (ISED for --country CA,
    else FCC), every limit adjustable per receiver (changing one makes
    the receiver's rules custom):
      over-modulation  above 100% + 0.5% per 1% of subcarrier injection
                       (RDS + SCA), never above 110% (FCC 47 CFR
                       73.1570(b)(2); ISED BETS-6 A.2.2.4.4, BPR-3 3.13.2)
      pilot            stereo pilot outside 8-10% or 19 kHz +/-2 Hz
                       (FCC 73.322; ISED BETS-6 A.2.2.2)
      subcarriers      total injection over 20%, or over 10% above 75/76 kHz
                       (FCC 73.319(d)(2); ISED BETS-6 A.2.2.4.3, BPR-3 3.13.2)
      carrier freq.    off by more than 2 kHz (FCC 73.1545(b)) / 1 kHz (ISED
                       BETS-6 7.2.3, the transmitter stability standard);
                       the reading includes the SDR's own tuning error
"""

import argparse
import bisect
import glob
import concurrent.futures
import contextlib
import base64
import ctypes
import gc
import datetime
import hashlib
import hmac
import itertools
import json
import math
import os
import queue
import random
import re
import secrets
import shutil
import smtplib
import ssl
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict, deque
from dataclasses import asdict, dataclass, field, fields
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# radioconda's numpy and scipy use MKL with Intel OpenMP, whose threads spin for
# 200 ms after each parallel FFT or filter. The meters call those all the time, so
# on a 4-thread laptop the spinning took 2 of its 4 cores. The meters already run
# in parallel (a GNU Radio thread each): keep the maths single-threaded. Must be
# set before numpy loads.
for _var in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_var, '1')

import numpy as np
import pmt
from PyQt5 import QtCore, QtGui, QtWidgets
from scipy import fft as spfft
from scipy import signal as sps
from gnuradio import analog, audio, blocks, digital, filter, gr
from gnuradio.filter import firdes

import rds  # gr-rds (radioconda package gnuradio-rds)

DEFAULT_FREQS_MHZ = (94.5, 100.9, 101.7)
SAMP_RATE = 9.6e6          # RSP1A rate; 8 MHz IF filter covers +/-3.7 MHz cleanly
CHAN_DECIM = 25            # 9.6 MS/s -> 384 kS/s per station: room for the
QUAD_RATE = SAMP_RATE / CHAN_DECIM  # +/-150 kHz an FM signal with SCA occupies
AUDIO_DECIM = 8            # 384 kS/s -> 48 kS/s
CHAN_PASS_HZ = 150e3       # channel filter: flat to +/-150 kHz, stop by +/-185 kHz
AUDIO_RATE = int(QUAD_RATE / AUDIO_DECIM)
MAX_DEV = 75e3             # FM broadcast 100% deviation
MAX_SPAN = 7.2e6           # widest station spread that fits the 8 MHz IF filter
EDGE_HZ = MAX_SPAN / 2 + 150e3  # a station at most this far from the SDR centre (room to move off the midpoint)
DC_CLEAR_HZ = 250e3        # SDR centre this far from every carrier: the RSP1A's DC offset stays out of the channel
IMAGE_CLEAR_HZ = 300e3     # each station's IQ image (mirrored about the centre) this far from every other carrier
PLAY_GAIN = 0.7
UPDATE_HZ = 10             # measurement and display rate
TREND_S = 0.5              # sparklines and the histogram are redrawn this often
TREND_SPAN_S = 300         # ...over this long
MAX_RECEIVERS = 4          # receivers the app runs at once
FM_BATCH = 2048            # Python meters get samples in batches (~8.5 ms),
AUDIO_BATCH = 512          # so they are called ~100x/s, not ~900x/s; powers
                           # of two keep GNU Radio buffers aligned
SRC_BUFFER = 1 << 18       # SDR output buffer, samples (~27 ms). GNU Radio's default
                           # (4096) makes every block downstream run on ~100-sample
                           # scraps thousands of times a second: 4x the CPU.
CHAN_CHUNK = 8192          # channel filters wait for this many outputs (~21 ms), so the
                           # whole station runs in chunks of this size whatever the
                           # SDR delivers per read. Each station is ~50 blocks, one
                           # thread each: 512 (~1.3 ms) cost ~25% more CPU in wake-ups.
                           # Needs CHAN_CHUNK * CHAN_DECIM < SRC_BUFFER.
RDS_CREST = 1.443          # IEC 62106 RDS waveform: peak / RMS (random data)
RDS_PHASE_S = 5            # RDS phase vs 3x pilot: averaged over this long; locked when
RDS_LOCKED = 0.9           # ...the phase holds this steady (1 = constant, 0 = drifting)
RDS_PHASE_TOL = 10.0       # IEC 62106: in phase or quadrature with 3x the pilot, +/-10 deg
SYNC_AM_ALPHA = 0.05       # synchronous AM: smoothing per update (~2 s)
SYNC_AM_MIN_MOD = 0.1      # ...judged only while the MPX RMS is at least this (7.5 kHz)
RDS_BW = 2.4e3             # RDS occupies 57 kHz +/- this
RDS_SEARCH_HZ = 15         # RDS carrier offsets looked for (IEC 62106 allows +/-6 Hz unlocked)
RDS_MIN_LINE = 6.0         # RDS shown once its line stands this many times the median of the search band
RDS_AVG_S = 2.0            # RDS injection is integrated coherently over this long
RDS_ZZ_AVG = 16            # RDS: z² samples averaged into one point of the line search (>= 300 points/s)
GUARD_TO_AUDIO = (15e3 ** 3 / 3) / ((18.3e3 ** 3 - 16e3 ** 3) / 3 / 2.3e3)  # f^2 noise: 0-15 kHz power
                           # per (Hz of guard-band noise density)
RTPLUS_LEAD_S = 3.0        # RT+ tags may come this far before or after the RadioText they tag
SDR_STALL_S = 3.0          # no samples from the SDR for this long: it is lost, reopen it
SDR_RETRY_S = (2, 5, 10, 30)  # waits between reopening attempts (the last repeats)
NOTIFY_BATCH_S = 5.0       # notifications this close together go out as one message
NOTIFY_RETRY_S = (10, 60)  # waits before re-sending a failed notification
STARTUP_LNK = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs',
                           'Startup', 'fm-modmon-ms.lnk')  # "start when I sign in to Windows"
CAL_PEAK_DBFS = -10.0      # gain calibration: ADC peaks (99.99th percentile) held here
CAL_TOLERANCE_DB = 1.5     # ...the least gain whose stations' S/N is this close to the best
CAL_CLIP = 0.9            # ...and any sample at this fraction of full scale means overload
CAL_LNA_STATES = range(9, -1, -1)  # tried from least gain to most
CAL_DEFAULT = (4, 40)      # LNA state, IF gain reduction when not calibrated
IQ_TAP_BATCH = 65536       # live calibration reads the SDR in batches this big
ADC_BATCH = 16384          # the wideband peak meter reads the SDR in batches this big
ADC_OVERLOAD_N = 3         # ADC overload: raised once this many of the last...
ADC_OVERLOAD_WINDOW_S = 10  # ...this many seconds had a peak at CAL_CLIP or above,
ADC_OVERLOAD_CLEAR_S = 30  # and cleared after this long without one
SETTLE_UPDATES = 5         # meters ignore over-modulation this long after a (re)start
SCA_CLASSIFY_DB = 15.0     # below this (above the gap) demodulated noise hides what an SCA carries
SCA_BATCH = 4096           # the SCA analyser gets its signal in 85 ms batches
SCA_MIN_DB = 10.0          # SCA must be this far above the 77-82 kHz gap
DYNAMIC_PS_S = 30          # a PS that changes 3+ times in this long is dynamic
PS_NAME_STABLE_S = 10      # a PS names the station once it has held this long
OVERMOD_WINDOW_S = 0.001   # over-modulation is counted per 1 ms window
OVERMOD_MIN_S = 17e-6      # ...and only peaks lasting this long (ignores noise spikes)
MPX_POWER_S = 60           # ITU-R BS.412 MPX power integration time
PEAK_AM_PCT = 5.0          # over-modulation is judged only while AM / multipath has stayed
PEAK_AM_S = 10             # ...under this for this long (ITU-R SM.1268: echoes 26 dB down,
                           # AM averaged over 10 s); echoes or noise above it inflate peaks
CLEAN_AM_PCT = 15.0        # the other technical rules are judged under this
IBOC_MIN_DB = 6.0          # IBOC sidebands must be this far above the floor
WEB_PORT = 8765            # web view; 0 turns it off
WEB_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fm-modmon-ms-web.html')
# Browser audio formats, encoded by ffmpeg from 48 kHz 16-bit stereo; offered when
# ffmpeg has the encoder ('encoder') and the browser can play the type ('canplay').
WEB_FORMATS = {
    'mp3': {'label': 'MP3 128k', 'mime': 'audio/mpeg', 'canplay': 'audio/mpeg', 'encoder': 'libmp3lame',
            'args': ['-c:a', 'libmp3lame', '-b:a', '128k', '-f', 'mp3']},
    'aac': {'label': 'AAC 128k', 'mime': 'audio/aac', 'canplay': 'audio/aac', 'encoder': 'aac',
            'args': ['-c:a', 'aac', '-b:a', '128k', '-f', 'adts']},
    'opus': {'label': 'Opus 96k', 'mime': 'audio/ogg', 'canplay': 'audio/ogg; codecs="opus"', 'encoder': 'libopus',
             'args': ['-c:a', 'libopus', '-b:a', '96k', '-f', 'ogg', '-page_duration', '100000']},
    'flac': {'label': 'FLAC', 'mime': 'audio/flac', 'canplay': 'audio/flac', 'encoder': 'flac',
             'args': ['-c:a', 'flac', '-compression_level', '5', '-f', 'flac']},
}
WEB_MAX_LISTENERS = 8     # browser audio streams at once, all receivers together
WEB_BATCH = 4096           # browser audio reaches Python in 85 ms batches (it is buffered anyway)
WEB_SOURCES = {'analog': 0, 'sca67': 1, 'sca92': 2}  # audio sources the browser can play
RDS_TCP_PORT = 7711        # default RDS feed ports 7711-7714 (receiver 1-4); each is settable
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
APP_NAME = 'FM-Modmon-ms'
APP_ID = 'fm-modmon-ms.monitor'   # Windows taskbar identity, so it shows our icon, not Python's
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fm-modmon-ms.ico')
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fm-modmon-ms_config.json')

# Audio sources a receiver can play.
AUDIO_SOURCES = (('analog', 'Analog FM'), ('sca67', 'SCA 67 kHz'), ('sca92', 'SCA 92 kHz'),
                 ('iboc0', 'IBOC MPS'), ('iboc1', 'IBOC SPS1'), ('iboc2', 'IBOC SPS2'),
                 ('iboc3', 'IBOC SPS3'))
SCA_DEV = 6e3              # SCA subcarrier deviation taken as full scale
SCA_DEEMPH_S = 150e-6      # SCA audio de-emphasis
SCA_LEVEL = 0.5            # SCA play level relative to analog
# IBOC is decoded by nrsc5 (https://github.com/theori-io/nrsc5), fed cs16 IQ on stdin.
NRSC5_PATH = (shutil.which('nrsc5') or next(iter(sorted(glob.glob(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'nrsc5*', 'build', 'src',
    'nrsc5.exe' if os.name == 'nt' else 'nrsc5')))), 'nrsc5'))
IBOC_RATE = 744187.5       # nrsc5's cs16 input rate (NRSC5_SAMPLE_RATE_NATIVE_FM)
IBOC_DECIM = 8             # 9.6 MS/s -> 1.2 MS/s before the fractional resampler
IBOC_BATCH = 16384         # shorts per write to nrsc5 (~11 ms)
MIME_PRIMARY_IMAGE = 0xBE4B7536   # nrsc5: LOT component carrying album art
MIME_STATION_LOGO = 0xD9C72536    # nrsc5: LOT component carrying the station logo
IMAGE_KEEP_S = 1800        # cached IBOC images not in use are pruned after this
CACHE_PREFIX = 'fm-modmon-ms_cache_'  # session cache folder in %TEMP%, deleted on exit
RADIODNS_RETRY_S = 300     # retry a failed RadioDNS lookup after this
RADIODNS_IMAGE_MAX = 2 << 20  # a RadioDNS logo or slide bigger than this (bytes) isn't downloaded
# RadioDNS slideshow transports (TS 101 499 table 5), in the order they're tried:
# Server-sent Events (current), then the deprecated Stomp and HTTP long polling
VIS_TRANSPORTS = (('push', '_radiopush._tcp'), ('stomp', '_radiovis._tcp'), ('http', '_radiovis-http._tcp'))
VIS_TRANSPORT_NAMES = {'push': 'Server-sent Events', 'stomp': 'Stomp', 'http': 'HTTP'}

# PTY names: RBDS (North America, NRSC-4-B) and RDS (IEC 62106 / EN 50067).
PTY_RBDS = ('None', 'News', 'Information', 'Sports', 'Talk', 'Rock', 'Classic Rock', 'Adult Hits',
            'Soft Rock', 'Top 40', 'Country', 'Oldies', 'Soft', 'Nostalgia', 'Jazz', 'Classical',
            'Rhythm and Blues', 'Soft Rhythm and Blues', 'Language', 'Religious Music',
            'Religious Talk', 'Personality', 'Public', 'College', 'Spanish Talk', 'Spanish Music',
            'Hip Hop', 'Unassigned', 'Unassigned', 'Weather', 'Emergency Test', 'Emergency')
PTY_RDS = ('None', 'News', 'Current Affairs', 'Information', 'Sport', 'Education', 'Drama', 'Culture',
           'Science', 'Varied', 'Pop Music', 'Rock Music', 'Easy Listening', 'Light Classical',
           'Serious Classical', 'Other Music', 'Weather', 'Finance', "Children's Programmes",
           'Social Affairs', 'Religion', 'Phone-in', 'Travel', 'Leisure', 'Jazz Music',
           'Country Music', 'National Music', 'Oldies Music', 'Folk Music', 'Documentary',
           'Alarm Test', 'Alarm')

# RDS Open Data Application IDs and RT+ content types worth naming.
ODA_NAMES = {0x4BD7: 'RT+', 0x6552: 'eRT', 0xCD46: 'TMC', 0xCD47: 'TMC', 0xC3B0: 'iTunes tagging'}
RTPLUS_TYPES = {1: 'Title', 2: 'Album', 3: 'Track', 4: 'Artist', 5: 'Composition',
                7: 'Conductor', 8: 'Composer', 9: 'Band', 10: 'Comment', 11: 'Genre',
                12: 'News', 27: 'Alarm', 30: 'Info', 31: 'Programme', 32: 'Next programme'}
RTPLUS_ALARM = 27          # INFO.ALARM: public alert text (Alert FM's RadioText copy, NRSC-G300 7.2)

# Data services: non-programme data a station carries, watched for presence only.
# Paging, EWS and leased ODAs are addressed to their own receivers and often
# encrypted, so they are identified, never decoded (the Radiocommunication Act
# s. 9(2) bars divulging them); only public alert text (RT+ Alarm) is shown.
PROGRAMME_ODAS = {0x4BD7, 0x6552, 0xC3B0}   # RT+, eRT, iTunes tagging: programme metadata
UNANNOUNCED_DATA = {14: 'Paging (7A)', 16: 'TMC (8A)', 18: 'EWS (9A)',  # group type code: label
                    26: 'Paging (13A)'}
DATA_GAP_S = 15.0          # a service unseen this long is absent
DATA_STEADY_S = 300.0      # present this long without a gap: the station carries it, its loss alarms
                           # (shorter bursts, e.g. paging only during an alert, never alarm)


def parse_service_names(text):
    """'7A=Alert FM, SCA67=Muzak' -> {'7A': 'Alert FM', 'SCA67': 'Muzak'}: names for the
    data services by group type (or SCA67 / SCA92), since nothing on air names them."""
    out = {}
    for part in re.split(r'[,;]', text or ''):
        code, sep, name = part.partition('=')
        code = re.sub(r'\s+', '', code).upper()
        if sep and code and name.strip():
            out[code] = name.strip()
    return out

# Band scan: North American 200 kHz raster (88.1 ... 107.9 MHz), in tenths of MHz.
CHANNELS_MHZ10 = range(881, 1080, 2)
SCAN_CENTERS = (91.0e6, 97.0e6, 103.0e6, 109.0e6)  # even tenths: DC never on a channel
SCAN_HALF_WIDTH = 3.0e6    # use only the flat middle of each 8 MHz window
SCAN_MIN_SNR = 10.0        # dB above the window's noise floor
SCAN_SPLATTER_DB = 20.0    # ignore channels this far below a 200 kHz neighbour

# SoapySDRPlay3 module (radioconda has none: the SDRplay API is closed source, so it is
# built locally); used from ../soapysdrplay3-build/modules if there. SOAPY_SDR_PLUGIN_PATH overrides.
DEFAULT_PLUGIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '..', 'soapysdrplay3-build', 'modules')
SDRPLAY_API_DIR = r'C:\Program Files\SDRplay\API\x64'


def _soapy_env():
    if not os.environ.get('SOAPY_SDR_PLUGIN_PATH') and os.path.isdir(DEFAULT_PLUGIN_DIR):
        os.environ['SOAPY_SDR_PLUGIN_PATH'] = os.path.normpath(DEFAULT_PLUGIN_DIR)
    # SDRplay API DLL, plus radioconda's DLLs so the other Soapy modules load
    # quietly when this runs without `conda activate`.
    if os.name == 'nt' and SDRPLAY_API_DIR not in os.environ.get('PATH', ''):
        os.environ['PATH'] = os.pathsep.join([SDRPLAY_API_DIR, os.path.join(sys.prefix, 'Library', 'bin'),
                                              os.environ.get('PATH', '')])


def _retry(open_device, attempts=5):
    """The SDRplay service can take a moment to free the RSP1A after a close."""
    for i in range(attempts):
        try:
            return open_device()
        except RuntimeError:
            if i == attempts - 1:
                raise
            time.sleep(1.0)


def pick_initial(found, n=3):
    """Strongest n stations that fit together in one SDR window, sorted by frequency."""
    best = []
    for f0, _ in found:
        group = sorted((s for s in found if f0 <= s[0] <= f0 + MAX_SPAN + 1),
                       key=lambda s: -s[1])[:n]
        if (len(group), sum(s for _, s in group)) > (len(best), sum(s for _, s in best)):
            best = group
    return sorted(f for f, _ in best)


def band_scan(lna_state, if_gain_reduction, verbose=False):
    """Sweep 88-108 MHz once. Returns (found, iboc_scan):
    found = [(freq_hz, snr_db), ...] of stations; iboc_scan = {freq_hz: info} where
    info is the IBOC digital-to-analog power ratio in dBc, None (no IBOC
    sidebands), or 'adjacent' (a neighbour 200 kHz away hides the sidebands).

    Steps the RSP1A through SCAN_CENTERS, averages a spectrum at each, and
    measures every channel on the North American 200 kHz raster. A channel
    counts as a station when it stands SCAN_MIN_SNR dB above the noise floor
    and isn't just the sideband splatter of a much stronger neighbour. IBOC
    shows up as flat sidebands 129-199 kHz either side of the carrier,
    outside the receivers' channel filters, so it is detected here.
    """
    with _rsp1a_direct(lna_state, if_gain_reduction) as rsp:
        return _scan(rsp, verbose)


def _scan(rsp, verbose):
    nfft = 4096
    win = np.hanning(nfft).astype(np.float32)
    bin_hz = SAMP_RATE / nfft
    power = {}  # channel MHz*10 -> (density dB, floor dB, analog power, LSB dB, USB dB, IBOC power)
    sb_lo, sb_hi = int(129.4e3 / bin_hz), int(198.4e3 / bin_hz)
    an_half = int(100e3 / bin_hz)
    for center in SCAN_CENTERS:
        rsp.tune(center)
        rsp.capture(int(SAMP_RATE * 0.1))                 # let the tuner settle
        x = rsp.capture(int(SAMP_RATE * 0.25))
        frames = x[:len(x) // nfft * nfft].reshape(-1, nfft) * win
        psd = np.fft.fftshift(np.mean(np.abs(np.fft.fft(frames, axis=1)) ** 2, axis=0))
        psd_db = 10 * np.log10(psd + 1e-20)
        floor = float(np.percentile(psd_db, 20))
        for ch in CHANNELS_MHZ10:
            off = ch * 1e5 - center
            if abs(off) > SCAN_HALF_WIDTH:
                continue
            k = int(round(off / bin_hz)) + nfft // 2
            half = int(60e3 / bin_hz)
            lsb, usb = psd[k - sb_hi:k - sb_lo + 1], psd[k + sb_lo:k + sb_hi + 1]
            power[ch] = (10 * math.log10(np.mean(psd[k - half:k + half + 1])), floor,
                         float(np.sum(psd[k - an_half:k + an_half + 1])),
                         10 * math.log10(np.mean(lsb)), 10 * math.log10(np.mean(usb)),
                         float(np.sum(lsb) + np.sum(usb)))

    found, iboc_scan = [], {}
    for ch, (p, floor, an, lsb_db, usb_db, sb) in sorted(power.items()):
        snr = p - floor
        neighbours = [power[n][0] for n in (ch - 2, ch + 2) if n in power]
        splatter = neighbours and p < max(neighbours) - SCAN_SPLATTER_DB
        if snr >= SCAN_MIN_SNR and not splatter:
            found.append((ch * 100000, snr))
    stations = {f // 100000 for f, _ in found}
    for f, _ in found:
        ch = f // 100000
        _, floor, an, lsb_db, usb_db, sb = power[ch]
        if stations & {ch - 2, ch + 2}:
            iboc_scan[f] = 'adjacent'
        elif min(lsb_db, usb_db) - floor >= IBOC_MIN_DB:
            iboc_scan[f] = 10 * math.log10(sb / an)
        else:
            iboc_scan[f] = None
    if verbose:
        for ch, (p, floor, *_rest) in sorted(power.items()):
            f = ch * 100000
            print(f'{ch / 10:6.1f}  {p - floor:5.1f} dB  {"STATION" if f in iboc_scan else ""}  '
                  f'{"IBOC " + str(iboc_scan[f]) if f in iboc_scan and iboc_scan[f] is not None else ""}')
    return found, iboc_scan


class _Rsp:
    """What the band scan and gain calibration need from the SDR: tune(hz),
    set_gain(lna_state, if_gain_reduction) and capture(n) -> complex64 IQ."""

    def __init__(self, tune, set_gain, capture):
        self.tune, self.set_gain, self.capture = tune, set_gain, capture


@contextlib.contextmanager
def _rsp1a_direct(lna_state, if_gain_reduction, center_hz=None):
    """The RSP1A opened directly through SoapySDR (no flowgraph) and streaming;
    released on exit so the receiver can open it."""
    _soapy_env()
    import SoapySDR
    from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32

    dev = _retry(lambda: SoapySDR.Device('driver=sdrplay'))
    dev.setSampleRate(SOAPY_SDR_RX, 0, SAMP_RATE)
    dev.setBandwidth(SOAPY_SDR_RX, 0, 8e6)
    dev.setGainMode(SOAPY_SDR_RX, 0, False)

    def set_gain(lna, ifgr):
        dev.setGain(SOAPY_SDR_RX, 0, 'IFGR', min(max(ifgr, 20), 59))
        dev.setGain(SOAPY_SDR_RX, 0, 'RFGR', min(max(lna, 0), 9))

    set_gain(lna_state, if_gain_reduction)
    if center_hz:
        dev.setFrequency(SOAPY_SDR_RX, 0, center_hz)
    for key in ('rfnotch_ctrl', 'dabnotch_ctrl'):
        try:
            dev.writeSetting(key, 'false')
        except Exception:
            pass
    stream = dev.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
    dev.activateStream(stream)
    buf = np.empty(65536, np.complex64)

    def capture(n):
        out, got = np.empty(n, np.complex64), 0
        while got < n:
            sr = dev.readStream(stream, [buf], min(len(buf), n - got), timeoutUs=1000000)
            if sr.ret > 0:
                out[got:got + sr.ret] = buf[:sr.ret]
                got += sr.ret
        return out

    try:
        yield _Rsp(lambda hz: dev.setFrequency(SOAPY_SDR_RX, 0, hz), set_gain, capture)
    finally:
        dev.deactivateStream(stream)
        dev.closeStream(stream)
        dev.close()  # release the RSP1A before the receiver opens it


def calibrate_gain(rsp, center_hz, freqs_hz, progress=None):
    """Choose the LNA state and IF gain reduction for receiving freqs_hz with
    the SDR centred on center_hz. rsp is an _Rsp already tuned there.

    For each LNA state (least gain first) the IF gain reduction is set so the
    ADC's peaks sit at CAL_PEAK_DBFS, then each station's level over the noise
    floor is measured. Returns (lna, ifgr, report): the state giving the
    stations the best average S/N without overload (the least gain within
    CAL_TOLERANCE_DB of the best, since past the point where antenna noise
    dominates more gain only costs headroom), its IF gain reduction, and a
    one-line report."""
    nfft = 4096
    win = np.hanning(nfft).astype(np.float32)
    bin_hz = SAMP_RATE / nfft
    flat = slice(int(nfft / 2 - 3.6e6 / bin_hz), int(nfft / 2 + 3.6e6 / bin_hz))  # inside the IF filter

    def measure():
        rsp.capture(int(SAMP_RATE * 0.05))       # samples from before the gain change
        x = rsp.capture(int(SAMP_RATE * 0.2))
        mag = np.abs(x)
        peak_db = 20 * math.log10(float(np.percentile(mag, 99.99)) + 1e-12)
        clipped = bool(np.max(mag) >= CAL_CLIP)
        frames = x[:len(x) // nfft * nfft].reshape(-1, nfft) * win
        psd = np.fft.fftshift(np.mean(np.abs(np.fft.fft(frames, axis=1)) ** 2, axis=0))
        psd_db = 10 * np.log10(psd + 1e-20)
        floor = float(np.percentile(psd_db[flat], 20))
        snrs = []
        for f in freqs_hz:
            k = int(round((f - center_hz) / bin_hz)) + nfft // 2
            half = int(60e3 / bin_hz)
            snrs.append(10 * math.log10(float(np.mean(psd[k - half:k + half + 1]))) - floor)
        return peak_db, clipped, float(np.mean(snrs)), min(snrs)

    tried = []
    ifgr = 40
    for lna in CAL_LNA_STATES:
        rsp.set_gain(lna, ifgr)
        peak_db, clipped, snr, worst = measure()
        for _ in range(3):  # bring the ADC peaks to CAL_PEAK_DBFS (IF gain is about 1 dB per dB)
            new = int(round(min(max(ifgr + peak_db - CAL_PEAK_DBFS, 20), 59)))
            if new == ifgr:
                break
            ifgr = new
            rsp.set_gain(lna, ifgr)
            peak_db, clipped, snr, worst = measure()
            if abs(peak_db - CAL_PEAK_DBFS) <= 1.5:
                break
        tried.append((lna, ifgr, peak_db, clipped, snr, worst))
        if progress:
            progress(f'LNA {lna}: S/N {snr:.1f} dB (weakest {worst:.1f})' + (' (overload)' if clipped else ''))
        good = [t for t in tried if not t[3]]
        if good and snr < max(t[4] for t in good) - 6:
            break                                # past the best: more gain only adds overload
        last = [t[4] for t in tried[-3:]]
        if len(good) >= 4 and len(last) == 3 and max(last) - min(last) < 1.0:
            break                                # S/N has levelled off: antenna noise dominates
    good = [t for t in tried if not t[3]] or tried
    best = max(t[4] for t in good)
    lna, ifgr, peak_db, _, snr, worst = next(t for t in good if t[4] >= best - CAL_TOLERANCE_DB)
    report = (f'LNA {lna} \u00b7 IFGR {ifgr} dB: stations {snr:.0f} dB over the floor on average '
              f'(weakest {worst:.0f} dB), '
              f'ADC peaks {peak_db:.0f} dBFS ({len(tried)} LNA states tried)')
    return lna, ifgr, report


def calibrate_startup(receivers_hz, lna, ifgr, progress=None):
    """Gain calibration on the RSP1A before the receiver opens it."""
    center = _centre(receivers_hz)
    with _rsp1a_direct(lna, ifgr, center) as rsp:
        rsp.capture(int(SAMP_RATE * 0.1))  # let the tuner settle
        return calibrate_gain(rsp, center, list(receivers_hz), progress)


class IqTap(gr.sync_block):
    """Hands the SDR's IQ to grab() while one is waiting (live gain calibration)."""

    def __init__(self):
        gr.sync_block.__init__(self, name='iq_tap', in_sig=[(np.complex64, IQ_TAP_BATCH)], out_sig=None)
        self._want = 0
        self._chunks = []
        self._done = threading.Event()

    def grab(self, n, timeout=5.0):
        self._chunks = []
        self._done.clear()
        self._want = n
        if not self._done.wait(timeout):
            self._want = 0
            raise RuntimeError('no samples from the SDR')
        return np.concatenate(self._chunks)[:n]

    def work(self, input_items, output_items):
        if self._want > 0:
            for v in input_items[0]:
                self._chunks.append(v.copy())
                self._want -= len(v)
                if self._want <= 0:
                    self._done.set()
                    break
        return len(input_items[0])


class AdcMeter(gr.sync_block):
    """The wideband IQ's peak: the largest |I| or |Q| (full scale 1.0) since
    the last take(). The ADC clips each of I and Q at full scale."""

    def __init__(self):
        gr.sync_block.__init__(self, name='adc_meter', in_sig=[(np.complex64, ADC_BATCH)], out_sig=None)
        self._peak = None

    def take(self):
        """The peak since the last call; None if no samples came."""
        peak, self._peak = self._peak, None
        return peak

    def work(self, input_items, output_items):
        x = input_items[0].view(np.float32)  # I and Q interleaved
        peak = max(float(x.max()), -float(x.min()))
        self._peak = peak if self._peak is None else max(self._peak, peak)
        return len(input_items[0])


def _dbfs(amplitude):
    return 20 * math.log10(max(amplitude, 1e-12))


class AdcOverload:
    """Whether the RSP1A's ADC overloads while running. Gain calibration picks
    a gain that doesn't clip (CAL_CLIP) for the band as it was; this catches a
    stronger signal later, or a gain set too hot by --lna / --ifgr. Fed one
    peak a second: raised once ADC_OVERLOAD_N of the last ADC_OVERLOAD_WINDOW_S
    seconds reached CAL_CLIP, cleared after ADC_OVERLOAD_CLEAR_S without one."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.peak = None      # the last peak fed in
        self._hits = deque()  # when a peak reached CAL_CLIP

    def update(self, peak, now=None):
        """peak: from AdcMeter.take(). True if the overload is raised now,
        False if cleared now, else None."""
        now = time.monotonic() if now is None else now
        self.peak = peak
        if peak is not None and peak >= CAL_CLIP:
            self._hits.append(now)
        while self._hits and now - self._hits[0] > max(ADC_OVERLOAD_WINDOW_S, ADC_OVERLOAD_CLEAR_S):
            self._hits.popleft()
        recent = sum(now - t < ADC_OVERLOAD_WINDOW_S for t in self._hits)
        if not self.active and recent >= ADC_OVERLOAD_N:
            self.active = True
            return True
        if self.active and not any(now - t < ADC_OVERLOAD_CLEAR_S for t in self._hits):
            self.active = False
            return False
        return None


def make_rsp1a(center_hz, lna_state, if_gain_reduction):
    """Open the RSP1A through SoapySDR with fixed gain and the FM notch off."""
    _soapy_env()
    from gnuradio import soapy

    src = _retry(lambda: soapy.source('driver=sdrplay', 'fc32', 1, '', '', [''], ['']))
    src.set_sample_rate(0, SAMP_RATE)
    src.set_bandwidth(0, 8e6)
    src.set_frequency(0, center_hz)
    src.set_gain_mode(0, False)
    src.set_gain(0, 'IFGR', min(max(if_gain_reduction, 20), 59))
    src.set_gain(0, 'RFGR', min(max(lna_state, 0), 9))
    # The RSP1A has a switchable FM broadcast notch; it must be off for this.
    for key in ('rfnotch_ctrl', 'dabnotch_ctrl'):
        try:
            src.write_setting(key, False)
        except Exception as e:
            print(f'could not set {key}: {e}')
    return src


def _db(power):
    return 10 * math.log10(power) if power > 1e-20 else -math.inf


def _percentiles(x, qs):
    """np.percentile(x, qs) (linear interpolation) from one np.partition,
    without np.percentile's general-purpose overhead."""
    pos = [q / 100 * (len(x) - 1) for q in qs]
    lo = [min(int(p), len(x) - 2) for p in pos]
    part = np.partition(x, sorted({k for i in lo for k in (i, i + 1)}))
    return [float(part[i] + (p - i) * (part[i + 1] - part[i])) for p, i in zip(pos, lo)]


class FmMeter(gr.sync_block):
    """Measures a station from its channel IQ and MPX (both at QUAD_RATE).

    Results land in self.stats (a dict, replaced atomically) UPDATE_HZ times
    a second; on_stats(stats) is called with each result.
    MPX is scaled so 1.0 == 75 kHz deviation.
    """

    NFFT = int(QUAD_RATE / 50)  # 50 Hz bins

    def __init__(self, on_stats=None):
        gr.sync_block.__init__(self, name='fm_meter',
                               in_sig=[(np.complex64, FM_BATCH), (np.float32, FM_BATCH)], out_sig=None)
        self.stats = None
        self.last_update = None   # time.monotonic() of the last measurement: samples are flowing
        self._on_stats = on_stats
        self._period = int(QUAD_RATE / UPDATE_HZ)
        self._chunks = []
        self._count = 0
        self._iq_energy = 0.0
        self._win = np.hanning(self.NFFT).astype(np.float32)
        self._dc_win = np.hanning(self._period)
        self._freqs = np.fft.rfftfreq(self.NFFT, 1.0 / QUAD_RATE)
        # The quadrature demodulator's phase-difference output rolls off as
        # sinc(f/fs): -0.8 dB at 57 kHz, -2.2 dB at 92 kHz. Undo it.
        self._demod_comp = 1.0 / np.sinc(self._freqs / QUAD_RATE) ** 2
        self._psd = None
        self._rf = None
        self._offset = None
        self._peaks = deque(maxlen=UPDATE_HZ)  # 1 s peak hold
        self._pos = deque(maxlen=UPDATE_HZ)    # +/- peaks, 1 s hold
        self._neg = deque(maxlen=UPDATE_HZ)
        self._over = deque(maxlen=60 * UPDATE_HZ)          # over-mod excursions per update, 60 s
        self._over_prev = np.zeros(2, bool)                # was the last 1 ms window over 100/110%?
        self._mpx_ms = deque(maxlen=MPX_POWER_S * UPDATE_HZ)  # MPX mean square per update
        self._am = None
        self._am_hist = deque(maxlen=PEAK_AM_S * UPDATE_HZ)  # AM per update, for the peak gate
        self._rds = None
        self._rds_fft = None    # (block length, envelope length) the RDS measurement is set up for
        self._rds_hist = deque()  # per block: z² averaged down (RDS_ZZ_AVG), the last RDS_AVG_S
        self._rds_samples = 0     # MPX samples since the RDS measurement started (its 57 kHz phase)
        self._env_sum = 0.0
        self._env = []                                       # |IQ| chunks for this update
        self._rds_win = None
        self._phase_win = None
        self._rds_z = deque(maxlen=RDS_PHASE_S * UPDATE_HZ)  # RDS vs 3x pilot phasors (angle doubled)
        self._sync = None                                    # synchronous AM regression sums
        self._settle = SETTLE_UPDATES
        self._reset = False

    def reset(self):
        """Start fresh (new station). Takes effect in the flowgraph thread."""
        self._reset = True
        self.stats = None

    def work(self, input_items, output_items):
        iq, mpx = (a.reshape(-1) for a in input_items)  # batches -> samples
        if self._reset:
            self._reset = False
            self._chunks, self._count, self._iq_energy = [], 0, 0.0
            self._psd = self._rf = self._offset = self._am = self._rds = None
            self._rds_fft = None
            self._env_sum, self._env, self._sync = 0.0, [], None
            for d in (self._peaks, self._pos, self._neg, self._over, self._mpx_ms, self._am_hist,
                      self._rds_z):
                d.clear()
            self._over_prev = np.zeros(2, bool)
            self._settle = SETTLE_UPDATES
            self.stats = None
        self._iq_energy += float(np.vdot(iq, iq).real)
        env = np.abs(iq)
        self._env.append(env)
        self._env_sum += float(np.sum(env))
        self._chunks.append(mpx.copy())
        self._count += len(mpx)
        if self._count >= self._period:
            self.last_update = time.monotonic()
            self.stats = self._measure(np.concatenate(self._chunks),
                                       self._iq_energy / self._count, self._env_sum / self._count,
                                       np.concatenate(self._env))
            self._chunks, self._count, self._iq_energy, self._env_sum, self._env = [], 0, 0.0, 0.0, []
            if self._on_stats:
                self._on_stats(self.stats)
        return len(input_items[0])

    @staticmethod
    def _smooth(old, new, alpha):
        return new if old is None else old + alpha * (new - old)

    def _rds_power(self, x):
        """(RDS power in the MPX as a variance, how far its line stands above
        the median of the search band), over the last RDS_AVG_S.

        RDS is double-sideband suppressed-carrier: a real baseband m(t) on a
        57 kHz carrier. At complex baseband the band is z = m·e^(jφ) + n, so
        z² carries a steady line of power E[m²], while noise and programme
        leaking into the band, having no fixed phase, average out of it. So RDS
        needs no noise estimate. The blocks are joined on one 57 kHz phase
        reference and z² is integrated coherently over RDS_AVG_S, so bursty
        noise (multipath) averages out too. The carrier may be a few Hz off
        57 kHz (an encoder not locked to the pilot), which puts the line at twice
        the offset: the strongest within 2 x RDS_SEARCH_HZ is taken. Each block is
        Hann-windowed: unwindowed, the sidelobes of loud audio reach 57 kHz with a
        fixed phase and read as RDS."""
        n = len(x)
        df = QUAD_RATE / n
        k0, kw = round(57e3 / df), int(RDS_BW / df)
        m = 1 << (2 * kw + 1).bit_length()
        if self._rds_fft != (n, m):   # (first block, or a new block length: start over)
            self._rds_fft = (n, m)
            self._rds_win = np.hanning(n).astype(np.float32)
            t = np.arange(m) * (n / QUAD_RATE / m)
            self._rds_shift = np.exp(-2j * np.pi * (57e3 - k0 * df) * t)   # bin k0 -> exactly 57 kHz
            self._rds_hist.clear()
        start = self._rds_samples
        self._rds_samples += n
        # float32 FFT: 3x faster, and its error sits far below any RDS
        sel = spfft.rfft(x.astype(np.float32, copy=False) * self._rds_win)[k0 - kw:k0 + kw + 1] / np.sinc(57e3 / QUAD_RATE)
        spec = np.zeros(m, complex)
        spec[:kw + 1], spec[m - kw:] = sel[kw:], sel[:kw]
        z = np.fft.ifft(spec) * (2 * m / n)   # complex envelope: A cos(wt + p) -> A e^(jp)
        # on the 57 kHz phase running from the first block
        z *= self._rds_shift * np.exp(-2j * np.pi * (57000 * start % int(QUAD_RATE)) / QUAD_RATE)
        self._rds_hist.append((z * z).reshape(-1, RDS_ZZ_AVG).mean(axis=1))
        while len(self._rds_hist) * n > RDS_AVG_S * QUAD_RATE:
            self._rds_hist.popleft()
        zz = np.concatenate(self._rds_hist)
        nfft = 1 << (8 * len(zz) - 1).bit_length()   # zero-padded: a line falls between bins by little
        lines = np.abs(np.fft.fft(zz, nfft)) / len(zz)
        rate = m / RDS_ZZ_AVG * QUAD_RATE / n
        hz = np.fft.fftfreq(nfft, 1 / rate)
        w2 = 0.375   # mean of the Hann window squared: the power it takes away
        search = lines[np.abs(hz) <= 2 * RDS_SEARCH_HZ]
        peak = float(np.max(search))
        return peak / w2 / 2, peak / max(float(np.median(search)), 1e-30)

    @staticmethod
    def _sca(band, lo, hi):
        """SCA subcarrier injection (% of 75 kHz), or None if absent.

        The 77-82 kHz gap between the two SCA slots is empty on every
        station, so it is the noise reference; a subcarrier must stand
        SCA_MIN_DB above it.
        """
        floor = band(77e3, 82e3) / 5e3 * (hi - lo)
        power = band(lo, hi)
        if power < floor * 10 ** (SCA_MIN_DB / 10):
            return None
        return math.sqrt(2 * (power - floor)) * 100, _db(power / floor)

    RDS_M = 640  # RDS phase: pilot and RDS as complex baseband at 6.4 kS/s (640 of the 10 Hz bins)

    def _rds_phasor(self, x):
        """RDS's 57 kHz subcarrier against the pilot's third harmonic, for one
        update: a unit phasor at twice the phase difference, or None.

        One FFT of the MPX (a Hann-windowed block of QUAD_RATE / UPDATE_HZ
        samples: 10 Hz bins) gives both as complex baseband: the pilot
        (18.9-19.1 kHz) shifted down 19 kHz, made unit size and cubed, is the
        57 kHz reference; RDS (54.6-59.4 kHz) shifted down 57 kHz and
        multiplied by its conjugate leaves the BPSK data times e^(j phase).
        Squaring removes the data's sign, so the sum's angle is 2 x phase.
        A delay anywhere in the chain moves the pilot's third harmonic and
        RDS alike, so it cancels."""
        n = int(QUAD_RATE / UPDATE_HZ)
        if len(x) < n:
            return None
        if self._phase_win is None:
            self._phase_win = np.hanning(n).astype(np.float32)
        spec = np.fft.rfft(x[:n] * self._phase_win)
        df = QUAD_RATE / n
        m = self.RDS_M

        def baseband(lo, hi, centre):
            k0, k1, kc = round(lo / df), round(hi / df), round(centre / df)
            buf = np.zeros(m, np.complex128)
            buf[np.arange(k0 - kc, k1 - kc + 1) % m] = spec[k0:k1 + 1]
            return np.fft.ifft(buf)

        pilot = baseband(18.9e3, 19.1e3, 19e3)
        ref = pilot / np.maximum(np.abs(pilot), 1e-30)
        b = baseband(54.6e3, 59.4e3, 57e3) * np.conj(ref * ref * ref)
        z = complex(np.sum(b * b))
        return z / abs(z) if abs(z) > 0 else None

    def _sync_am(self, x, env):
        """Synchronous AM: the part of the carrier's envelope that follows the
        modulation, as the AM depth it gives at +/-75 kHz, or None while the
        modulation is too light to judge.

        The relative envelope is fitted to a*x + b*(x^2 - mean) (x = MPX,
        1.0 = 75 kHz): a sloped response (tuning off-centre) gives the x term,
        one too narrow for the sidebands the x^2 term. Envelope ripple not
        tied to the modulation (noise, hum) averages out; a short echo's is
        tied to it, so multipath counts.
        A fit, not a filter: every 4th sample (envelope and MPX at the same
        instants) gives the same answer for a quarter of the CPU."""
        n = min(len(x), len(env))
        x, env = np.ascontiguousarray(x[:n:4]), np.ascontiguousarray(env[:n:4])
        n = len(x)
        mean = float(np.mean(env))
        if mean <= 0:
            return None
        e = env / mean - 1.0
        q = x * x
        q -= float(np.mean(q))
        sums = np.array([np.dot(x, x), np.dot(x, q), np.dot(q, q), np.dot(x, e), np.dot(q, e)],
                        dtype=np.float64) / n
        self._sync = self._smooth(self._sync, sums, SYNC_AM_ALPHA)
        xx, xq, qq, xe, qe = self._sync
        det = xx * qq - xq * xq
        if xx < SYNC_AM_MIN_MOD ** 2 or det <= 0:
            return None
        a = (qq * xe - xq * qe) / det
        b = (xx * qe - xq * xe) / det
        t = np.linspace(-1.0, 1.0, 201)
        fit = a * t + b * t * t
        return float(np.max(fit) - np.min(fit)) / 2

    def _measure(self, x, iq_power, env_mean, env=None):
        # Carrier offset = DC of the MPX; Hann-weighted so bass leaks less,
        # then smoothed over a few seconds.
        if len(x) != len(self._dc_win):
            self._dc_win = np.hanning(len(x))
        w = self._dc_win
        mean = float(np.dot(w, x) / np.sum(w))
        self._offset = self._smooth(self._offset, mean, 0.03)
        self._rf = self._smooth(self._rf, iq_power, 0.3)
        x = x - mean
        frames = x[:len(x) // self.NFFT * self.NFFT].reshape(-1, self.NFFT) * self._win
        # One-sided power per bin, so summing a band gives that band's variance.
        psd = np.mean(np.abs(np.fft.rfft(frames, axis=1)) ** 2, axis=0)
        psd *= 2.0 / (self.NFFT * np.sum(self._win ** 2)) * self._demod_comp
        self._psd = self._smooth(self._psd, psd, 0.25)
        ax = np.abs(x)
        self._peaks.append(_percentiles(ax, (99.9,))[0])
        # Modulation-monitor style: +/- peaks (relative to the carrier's rest
        # frequency), 1 ms windows over 100%/110%, and BS.412 MPX power.
        neg, pos = _percentiles(x, (0.05, 99.95))
        self._pos.append(float(pos))
        self._neg.append(float(-neg))
        # Count excursions (runs of 1 ms windows over the limit), like a
        # monitor's peak counter, so one long burst counts once.
        win = int(QUAD_RATE * OVERMOD_WINDOW_S)
        sustained = ax.copy()
        for k in range(1, max(1, round(QUAD_RATE * OVERMOD_MIN_S))):  # min with ax shifted by k (wrapping)
            np.minimum(sustained[k:], ax[:-k], out=sustained[k:])
            np.minimum(sustained[:k], ax[-k:], out=sustained[:k])
        wmax = sustained[:len(x) // win * win].reshape(-1, win).max(axis=1)
        counts = []
        for i, limit in enumerate((1.0, 1.1)):
            over = wmax > limit
            starts = np.count_nonzero(over[1:] & ~over[:-1]) + int(bool(over[0]) and not self._over_prev[i])
            self._over_prev[i] = bool(over[-1])
            counts.append(starts)
        if self._settle:  # filters still settling after a (re)start: their transients aren't programme
            self._settle -= 1
        else:
            self._over.append(counts)
            self._mpx_ms.append(float(np.mean(x * x)))
        # A clean FM carrier has constant amplitude; envelope ripple is
        # multipath / synchronous AM (plus noise on weak signals).
        if env_mean > 0:
            # RMS ripple x sqrt(2): the % of a sine AM with the same RMS
            self._am = self._smooth(self._am, math.sqrt(2 * max(iq_power - env_mean ** 2, 0.0)) / env_mean, 0.3)
            if not self._settle:  # filters' start-up ripple isn't multipath
                self._am_hist.append(self._am)
        over = np.sum(self._over, axis=0) if self._over else np.zeros(2)
        sync_am = self._sync_am(x, env) if env is not None and not self._settle else None

        def band(lo, hi):
            return float(np.sum(self._psd[(self._freqs >= lo) & (self._freqs <= hi)])) + 1e-20

        # Guard-band noise density: the median bin, not the mean, so programme
        # there (clipper products, the encoder LPF's skirt) doesn't read as noise.
        # Each bin is first scaled to the band's mean f^2, as FM noise rises with f^2.
        g = (self._freqs >= 16e3) & (self._freqs <= 18.3e3)
        f2 = (18.3e3 ** 3 - 16e3 ** 3) / 3 / 2.3e3
        noise_per_hz = float(np.median(self._psd[g] * (f2 / self._freqs[g] ** 2))) / (QUAD_RATE / self.NFFT) + 1e-20
        pilot_pct = math.sqrt(2 * band(18.9e3, 19.1e3)) * 100
        self._rds, rds_line = self._rds_power(x)
        # Report RDS only when its line stands clear of the search band's noise.
        rds_pct = math.sqrt(2 * self._rds) * RDS_CREST * 100 if rds_line >= RDS_MIN_LINE else 0.0
        # RDS phase against the pilot's third harmonic, while both are on air.
        z = self._rds_phasor(x) if pilot_pct > 3.0 and rds_pct > 0.5 else None
        if z is None:
            self._rds_z.clear()
        else:
            self._rds_z.append(z)
        rds_phase = rds_lock = None
        if len(self._rds_z) >= UPDATE_HZ:  # a second's worth
            zs = complex(np.sum(self._rds_z))
            rds_lock = abs(zs) / len(self._rds_z)
            rds_phase = math.degrees(np.angle(zs)) / 2  # (-90, 90]: 0 = in phase, +/-90 = quadrature
        return {
            'rf_dbfs': _db(self._rf),
            'snr_db': _db(0.5 / (noise_per_hz * GUARD_TO_AUDIO)),
            'offset_hz': self._offset * MAX_DEV,
            'peak_dev_khz': max(self._peaks) * MAX_DEV / 1e3,
            'pos_pct': max(self._pos) * 100,
            'neg_pct': max(self._neg) * 100,
            'over100_min': int(over[0]),
            'over110_min': int(over[1]),
            # BS.412: 0 dBr = power of a sine at +/-19 kHz deviation.
            'mpx_dbr': _db(np.mean(self._mpx_ms) * MAX_DEV ** 2 / (19e3 ** 2 / 2)) if self._mpx_ms else -math.inf,
            'mpx_window_s': len(self._mpx_ms) / UPDATE_HZ,
            'am_pct': (self._am or 0.0) * 100,
            'am_max_pct': max(self._am_hist, default=0.0) * 100,  # over the last PEAK_AM_S
            'sync_am_pct': None if sync_am is None else sync_am * 100,
            'pilot_pct': pilot_pct,
            'rds_pct': rds_pct,
            'rds_phase_deg': rds_phase,  # vs 3x the pilot; None without both
            'rds_lock': rds_lock,        # 0-1: how steady that phase is
            **{f'sca{khz}_{key}': v for khz, lo, hi in ((67, 60e3, 74e3), (92, 85e3, 99e3))
               for key, v in zip(('pct', 'db'), self._sca(band, lo, hi) or (None, None))},
            # 500 Hz buckets centred on 0.5, 1.0 ... 100 kHz (so 19/38/57 kHz sit
            # mid-bucket), in dB re a 100% (75 kHz) sine: 9% pilot reads -21 dB.
            'mpx_db': 10 * np.log10(np.add.reduceat(self._psd[:2005], range(5, 2005, 10)) / 0.5 + 1e-12),
        }


# ITU-R BS.1770 K-weighting at 48 kHz: high shelf, then high-pass.
K_FILTERS = (([1.53512485958697, -2.69169618940638, 1.19839281085285],
              [1.0, -1.69065929318241, 0.73248077421585]),
             ([1.0, -2.0, 1.0],
              [1.0, -1.99004745483398, 0.99007225036621]))


class ScaMeter(gr.sync_block):
    """What each SCA subcarrier carries, from its FM-demodulated signal
    (inputs: 67 and 92 kHz, AUDIO_RATE, 1.0 = SCA_DEV). Every 2 s each is
    judged audio, data, tone or idle; self.kinds[67 | 92] is the majority of
    the last three judgements with, for data, the symbol rate if one was
    seen: (kind, baud or None), or None until there is a judgement.

    Programme audio keeps changing level and spectrum; data is steady and
    its spectrum stationary, and NRZ FSK data shows its symbol rate as a
    spectral line in |d/dt| of the demodulated signal."""

    WINDOW = 2 * AUDIO_RATE

    def __init__(self):
        gr.sync_block.__init__(self, name='sca_meter', in_sig=[(np.float32, SCA_BATCH)] * 2, out_sig=None)
        self.kinds = {67: None, 92: None}
        self._buf = {67: [], 92: []}
        self._verdicts = {67: deque(maxlen=3), 92: deque(maxlen=3)}
        self._reset = False

    def reset(self):
        """New station. Takes effect in the flowgraph thread."""
        self._reset = True
        self.kinds = {67: None, 92: None}

    def work(self, input_items, output_items):
        if self._reset:
            self._reset = False
            for khz in (67, 92):
                self._buf[khz].clear()
                self._verdicts[khz].clear()
        for khz, x in zip((67, 92), input_items):
            buf = self._buf[khz]
            buf.append(x.reshape(-1).copy())
            if sum(len(b) for b in buf) >= self.WINDOW:
                verdicts = self._verdicts[khz]
                verdicts.append(self.judge(np.concatenate(buf)[:self.WINDOW].astype(np.float64)))
                buf.clear()
                kinds = [k for k, _ in verdicts]
                kind = max(set(kinds), key=kinds.count)
                bauds = [b for k, b in verdicts if k == 'data' and b]
                self.kinds = {**self.kinds, khz: (kind, float(np.median(bauds)) if bauds else None)}
        return len(input_items[0])

    @staticmethod
    def judge(x):
        """(kind, baud or None) for 2 s of demodulated subcarrier."""
        x = x - np.mean(x)
        if np.sqrt(np.mean(x * x)) < 0.02:                  # < ~120 Hz RMS deviation
            return 'idle', None
        # 20 ms frame levels: programme varies, data doesn't
        frames = x[:len(x) // 960 * 960].reshape(-1, 960)
        level = 10 * np.log10(np.mean(frames * frames, axis=1) + 1e-12)
        level_sd = float(np.std(level[level > level.max() - 40]))
        # 200 ms spectra in 16 log bands: how much they change frame to frame
        n = 9600
        spec = np.abs(np.fft.rfft(x[:len(x) // n * n].reshape(-1, n) * np.hanning(n), axis=1)) ** 2
        f = np.fft.rfftfreq(n, 1 / AUDIO_RATE)
        edges = np.geomspace(300, 15000, 17)
        bands = np.stack([spec[:, (f >= lo) & (f < hi)].sum(axis=1) for lo, hi in zip(edges, edges[1:])], axis=1)
        flux = float(np.mean(np.abs(np.diff(10 * np.log10(bands + 1e-12), axis=0))))
        # symbol-rate line in |d/dt| (the transitions of NRZ data); prepend keeps
        # the length 96000, which FFTs 8x faster than 95999 (= 17 x 5647)
        d = np.abs(np.diff(x, prepend=x[0]))
        line = np.abs(np.fft.rfft((d - d.mean()) * np.hanning(len(d)))) ** 2
        fd = np.fft.rfftfreq(len(d), 1 / AUDIO_RATE)
        band = (fd > 150) & (fd < 16000)
        k = int(np.argmax(line[band]))
        line_db = 10 * math.log10(line[band][k] / (np.median(line[band]) + 1e-20) + 1e-20)
        if line_db > 80:                                    # a single steady tone
            return 'tone', None
        baud = float(fd[band][k]) if line_db > 35 else None
        if baud or (level_sd < 1.5 and flux < 1.6):
            return 'data', baud
        return 'audio', None


class AudioMeter(gr.sync_block):
    """Loudness (BS.1770) and stereo image from de-emphasised L/R, plus L, R,
    L+R and L-R modulation from the pre-de-emphasis matrix, all at AUDIO_RATE.

    Inputs: L, R (de-emphasised), M = (L+R)/2 and S = (L-R)/2 as transmitted
    (MPX units, 1.0 = 75 kHz). Results land in self.stats every 100 ms;
    self.scope holds recent L/R samples for the goniometer.
    """

    def __init__(self):
        gr.sync_block.__init__(self, name='audio_meter',
                               in_sig=[(np.float32, AUDIO_BATCH)] * 4, out_sig=None)
        self.stats = None
        self.scope = None
        self._hop = AUDIO_RATE // UPDATE_HZ
        self._chunks = ([], [], [], [])
        self._count = 0
        self._zi = [[np.zeros(2) for _ in K_FILTERS] for _ in range(2)]
        self._kpow = deque(maxlen=30)      # per-hop K-weighted (sum, n): 3 s
        self._sums = deque(maxlen=3)       # per-hop stereo sums: 300 ms
        self._tpk = deque(maxlen=UPDATE_HZ)  # per-hop true peaks: 1 s hold
        self._tp_tail = [np.zeros(self.TP_TAIL), np.zeros(self.TP_TAIL)]
        self._mod = deque(maxlen=UPDATE_HZ)  # per-hop L/R/M/S peaks: 1 s hold
        self._clear_gated()
        self._reset = False
        self._reset_all = False

    # Integrated loudness keeps the gated 400 ms blocks as a histogram of their
    # loudness (GATE_STEP LU bins from -70 LUFS), each bin's summed power and
    # count, so a monitor running for weeks uses fixed memory and time.
    GATE_STEP = 0.01
    GATE_BINS = 8000  # -70 .. +10 LUFS

    def _clear_gated(self):
        self._gate_pow = np.zeros(self.GATE_BINS)
        self._gate_n = np.zeros(self.GATE_BINS, np.int64)

    def reset_integrated(self):
        self._reset = True

    def reset(self):
        """Start fresh (new station). Takes effect in the flowgraph thread."""
        self._reset_all = True
        self.stats = self.scope = None

    def work(self, input_items, output_items):
        ins = [a.reshape(-1) for a in input_items]  # batches -> samples
        if self._reset_all:
            self._reset_all = False
            self._chunks, self._count = ([], [], [], []), 0
            self._tp_tail = [np.zeros(self.TP_TAIL), np.zeros(self.TP_TAIL)]
            for d in (self._kpow, self._sums, self._tpk, self._mod):
                d.clear()
            self._clear_gated()
            self.stats = self.scope = None
        for chunk, x in zip(self._chunks, ins):
            chunk.append(x.copy())
        self._count += len(ins[0])
        if self._count >= self._hop:
            self._process(*(np.concatenate(c) for c in self._chunks))
            self._chunks = ([], [], [], [])
            self._count = 0
        return len(input_items[0])

    def _kweight(self, ch, x):
        for i, (b, a) in enumerate(K_FILTERS):
            x, self._zi[ch][i] = sps.lfilter(b, a, x, zi=self._zi[ch][i])
        return x

    TP_TAIL = 32  # input samples carried between hops for true-peak oversampling
    # resample_poly's own 4x filter (Kaiser, beta 5, 81 taps), designed once: it
    # would otherwise redesign it on every call
    TP_TAPS = sps.firwin(81, 1 / 4, window=('kaiser', 5.0))

    def _true_peak(self, ch, x):
        """4x-oversampled peak. Each hop is overlapped with the previous hop's
        tail and the filter's edge ringing is discarded, so block boundaries
        don't inflate the reading."""
        y = sps.resample_poly(np.concatenate((self._tp_tail[ch], x)), 4, 1, window=self.TP_TAPS)
        self._tp_tail[ch] = x[-self.TP_TAIL:]
        half = 4 * self.TP_TAIL // 2
        return float(np.max(np.abs(y[half:-half])))

    def _process(self, l, r, mid, side):
        l64, r64 = l.astype(np.float64), r.astype(np.float64)
        n = len(l)
        kl, kr = self._kweight(0, l64), self._kweight(1, r64)
        self._kpow.append((np.dot(kl, kl) + np.dot(kr, kr), n))
        s, m = l64 - r64, l64 + r64
        self._sums.append(np.array([np.dot(l64, l64), np.dot(r64, r64), np.dot(l64, r64),
                                    np.dot(s, s), np.dot(m, m), n]))
        self._tpk.append([self._true_peak(0, l64), self._true_peak(1, r64)])
        self.scope = (l[-960:].copy(), r[-960:].copy())   # 20 ms; the small goniometer draws the last 400
        self._mod.append([np.max(np.abs(mid + side)), np.max(np.abs(mid - side)),
                          np.max(np.abs(mid)), np.max(np.abs(side))])

        def lufs(blocks_):
            e = sum(b[0] for b in blocks_)
            cnt = sum(b[1] for b in blocks_)
            return -0.691 + _db(e / cnt), e / cnt

        momentary, m_pow = lufs(list(self._kpow)[-4:])
        short_term, _ = lufs(self._kpow)
        if self._reset:
            self._clear_gated()
            self._reset = False
        if len(self._kpow) >= 4 and momentary > -70:
            k = min(int((momentary + 70) / self.GATE_STEP), self.GATE_BINS - 1)
            self._gate_pow[k] += m_pow
            self._gate_n[k] += 1
        integrated = -math.inf
        total = int(self._gate_n.sum())
        if total:
            rel_gate = -0.691 + _db(float(self._gate_pow.sum()) / total) - 10
            k = max(math.ceil((rel_gate + 70) / self.GATE_STEP), 0)
            n = int(self._gate_n[k:].sum())
            if n:
                integrated = -0.691 + _db(float(self._gate_pow[k:].sum()) / n)

        ll, rr, lr, ss, mm, cnt = np.sum(self._sums, axis=0)
        tp = np.max(self._tpk, axis=0)
        mod = np.max(self._mod, axis=0) * 100
        self.stats = {
            'mod_l': mod[0], 'mod_r': mod[1], 'mod_m': mod[2], 'mod_s': mod[3],
            'momentary': momentary,
            'short_term': short_term,
            'integrated': integrated,
            'tp_l': 20 * math.log10(tp[0] + 1e-10),
            'tp_r': 20 * math.log10(tp[1] + 1e-10),
            'rms_l': _db(ll / cnt),
            'rms_r': _db(rr / cnt),
            'correlation': lr / math.sqrt(ll * rr) if ll * rr > 1e-20 else 0.0,
            'width_db': _db(ss / mm) if mm > 1e-20 else -math.inf,
        }


class RdsState(gr.sync_block):
    """Collects gr-rds parser output into a dict, counts decoded groups, and
    decodes the raw groups for what the parser doesn't report: group-type
    statistics, ECC (1A), ODA announcements (3A), PTYN (10A), RT+ tags and
    which data services (paging, EWS, ODAs) are on air."""

    def __init__(self):
        gr.sync_block.__init__(self, name='rds_state', in_sig=None, out_sig=None)
        self.fields = {}
        self.groups = 0
        self._lock = threading.Lock()
        self._raw = self._fresh_raw()
        self.group_sink = None  # called with (a, b, c, d) for each error-free group
        for port, handler in (('groups', self._on_group), ('parsed', self._on_parsed)):
            self.message_port_register_in(pmt.intern(port))
            self.set_msg_handler(pmt.intern(port), handler)

    def reset(self, on_release, hold_s=1.5):
        """New station: drop the old station's groups still in the pipeline
        for hold_s, then call on_release (resets the parser) and start fresh."""
        self.fields = {}
        with self._lock:
            self._raw = self._fresh_raw()
        self._on_release = on_release
        self._hold_until = time.monotonic() + hold_s

    @staticmethod
    def _fresh_raw():
        return {'types': Counter(), 'ecc': None, 'oda': {}, 'ptyn': [' '] * 8, 'ptyn_ab': None,
                'rtplus': {}, 'rtplus_toggle': None, 'rtplus_at': 0.0, 'rtplus_for': None,
                'rt': '', 'rt_ab': None, 'rt_seg': {}, 'rt_flip_at': 0.0, 'pty': None, 'ct': None,
                'ps': '', 'ps_buf': [' '] * 8, 'ps_mask': 0, 'ps_changes': deque(), 'ps_at': 0.0,
                'data_seen': {}, 'rp_codes': 0, 'opc': 0, 'paging_id': None}

    def snapshot(self):
        """Thread-safe copy of the raw-group decode for the GUI."""
        with self._lock:
            r = self._raw
            return {'types': dict(r['types']), 'ecc': r['ecc'], 'oda': dict(r['oda']),
                    'ptyn': ''.join(r['ptyn']).strip() if r['ptyn_ab'] is not None else '',
                    'rtplus': self._rtplus_items(r), 'pty': r['pty'], 'ps': r['ps'], 'ct': r['ct'],
                    'ps_dynamic': self._ps_dynamic(r), 'ps_age': time.monotonic() - r['ps_at'],
                    'data': {k: (time.monotonic() - t, g) for k, (t, g) in r['data_seen'].items()},
                    'rp_codes': r['rp_codes'], 'opc': r['opc'], 'paging_id': r['paging_id']}

    @staticmethod
    def _data_key(raw, gtype):
        """The data service a group belongs to (its label), or None for programme data."""
        if gtype in (0, 6):
            return None
        for aid, g in raw['oda'].items():
            if g == gtype:
                return None if aid in PROGRAMME_ODAS else f'ODA {ODA_NAMES.get(aid, f"{aid:04X}")}'
        return UNANNOUNCED_DATA.get(gtype)

    @staticmethod
    def _rtplus_items(raw):
        """RT+ items as [(content type, text)], only for the RadioText they belong
        to and only once that text is complete; [] otherwise."""
        rt = raw['rt']
        if not raw['rtplus'] or not rt:
            return []
        if raw['rtplus_for'] is None:  # waiting for its text; a station that never flips A/B: take the current one
            if time.monotonic() - raw['rtplus_at'] <= RTPLUS_LEAD_S:
                return []
        elif raw['rtplus_for'] != raw['rt_ab']:
            return []
        return [(ct, rt[s:s + n + 1].strip()) for ct, (s, n) in raw['rtplus'].items()
                if s + n < len(rt) and rt[s:s + n + 1].strip()]

    @staticmethod
    def _ps_dynamic(raw):
        """Scrolling or block PS: the complete PS changed 3+ times in DYNAMIC_PS_S."""
        changes = raw['ps_changes']
        while changes and time.monotonic() - changes[0] > DYNAMIC_PS_S:
            changes.popleft()
        return len(changes) >= 3

    def _held(self):
        until = getattr(self, '_hold_until', None)
        if until is None:
            return False
        if time.monotonic() >= until:
            self._hold_until = None
            self._on_release()
            self.fields = {}
        return True  # also drop the message that ends the hold

    def _on_group(self, msg):
        if self._held():
            return
        self.groups += 1
        # gr-rds sends (nil . u8vector): blocks A-D big-endian, then offset letters.
        data = pmt.u8vector_elements(pmt.cdr(msg))
        if len(data) >= 8:
            group = tuple((data[i] << 8) | data[i + 1] for i in range(0, 8, 2))
            with self._lock:
                self._decode(*group)
            if self.group_sink:
                self.group_sink(*group)

    def _decode(self, a, b, c, d):
        raw = self._raw
        gtype = b >> 11                      # group type * 2 + version (A=0, B=1)
        name = f'{gtype >> 1}{"AB"[gtype & 1]}'
        raw['types'][name] += 1
        raw['pty'] = (b >> 5) & 0x1F
        key = self._data_key(raw, gtype)
        if key:
            raw['data_seen'][key] = (time.monotonic(), name)
        if gtype in (0, 1):                                  # 0A/0B: PS, two characters per group
            # Take a PS only when segments 0-3 arrive in order within one cycle,
            # so a scrolling or block PS is shown a whole frame at a time.
            addr = b & 3
            if addr == 0:
                raw['ps_mask'] = 0
            if raw['ps_mask'] == (1 << addr) - 1:
                raw['ps_buf'][addr * 2:addr * 2 + 2] = bytes([d >> 8, d & 0xFF]).decode('latin-1')
                raw['ps_mask'] |= 1 << addr
                if raw['ps_mask'] == 0xF:
                    ps = ''.join(raw['ps_buf'])
                    if ps != raw['ps']:
                        if raw['ps']:
                            raw['ps_changes'].append(time.monotonic())
                        raw['ps'] = ps
                        raw['ps_at'] = time.monotonic()
                    raw['ps_mask'] = 0
            else:
                raw['ps_mask'] = 0                           # a segment was missed: wait for the next 0
        if gtype == 2:                                       # 1A: radio paging codes (EN 50067 Annex M)
            raw['rp_codes'] = b & 0x1F
            if (c >> 12) & 7 == 2:                           # 1A variant 2: paging identification
                raw['paging_id'] = c & 0xFFF
        if gtype == 2 and (c >> 12) & 7 == 0:              # 1A variant 0: paging operator code + ECC
            raw['opc'] = (c >> 8) & 0xF
            raw['ecc'] = c & 0xFF
        elif gtype == 6:                                     # 3A: ODA announcement
            raw['oda'][d] = b & 0x1F
        elif gtype == 8:                                     # 4A: clock time (UTC + local offset)
            mjd = ((b & 3) << 15) | (c >> 1)
            hour, minute = ((c & 1) << 4) | (d >> 12), (d >> 6) & 0x3F
            offset = (d & 0x1F) * (-30 if d & 0x20 else 30)  # minutes
            if hour < 24 and minute < 60 and mjd > 15079:   # 15079 = 1900-03-01
                utc = datetime.datetime(1858, 11, 17) + datetime.timedelta(days=mjd, hours=hour, minutes=minute)
                raw['ct'] = (utc + datetime.timedelta(minutes=offset), offset)
        elif gtype == 20:                                    # 10A: PTYN
            ab = (b >> 4) & 1
            if raw['ptyn_ab'] is not None and ab != raw['ptyn_ab']:
                raw['ptyn'] = [' '] * 8
            raw['ptyn_ab'] = ab
            seg = (b & 1) * 4
            raw['ptyn'][seg:seg + 4] = bytes([c >> 8, c & 0xFF, d >> 8, d & 0xFF]).decode('latin-1')
        elif gtype == 4:                                     # 2A: RadioText, kept here to match RT+ against
            ab, now = (b >> 4) & 1, time.monotonic()
            if ab != raw['rt_ab']:                           # a new text
                if raw['rt_ab'] is not None:
                    # RT+ sent just before it is for it; anything older was for the old text
                    if now - raw['rtplus_at'] <= RTPLUS_LEAD_S:
                        raw['rtplus_for'] = ab
                    else:
                        raw['rtplus'], raw['rtplus_for'] = {}, None
                raw['rt_ab'], raw['rt_seg'], raw['rt'], raw['rt_flip_at'] = ab, {}, '', now
            raw['rt_seg'][b & 0xF] = bytes([c >> 8, c & 0xFF, d >> 8, d & 0xFF]).decode('latin-1')
            text = ''.join(raw['rt_seg'].get(i, '\0' * 4) for i in range(16))
            body = text.split('\r', 1)[0]
            if '\0' not in body:                             # every segment up to the end is in
                raw['rt'] = body.rstrip()
        if gtype == raw['oda'].get(0x4BD7) and gtype not in (0, 6):  # RT+ tags
            toggle, now = (b >> 4) & 1, time.monotonic()
            if toggle != raw['rtplus_toggle']:               # a new item
                # for the text that has just changed (tags sent after it), else for the next one
                recent_flip = now - raw['rt_flip_at'] <= RTPLUS_LEAD_S
                raw['rtplus_for'] = raw['rt_ab'] if raw['rtplus_toggle'] is None or recent_flip else None
                raw['rtplus'], raw['rtplus_toggle'], raw['rtplus_at'] = {}, toggle, now
            tags = {ctype: (start, length) for ctype, start, length in (
                (((b & 7) << 3) | (c >> 13), (c >> 7) & 0x3F, (c >> 1) & 0x3F),
                (((c & 1) << 5) | (d >> 11), (d >> 5) & 0x3F, d & 0x1F)) if ctype}
            if tags:
                raw['rtplus'].update(tags)
            else:
                raw['rtplus'] = {}                           # "no tags": nothing is tagged now

    def _on_parsed(self, msg):
        if self._held():
            return
        if pmt.is_tuple(msg):
            kind = pmt.to_long(pmt.tuple_ref(msg, 0))
            self.fields[kind] = pmt.symbol_to_string(pmt.tuple_ref(msg, 1))


class RdsGroupServer:
    """TCP server streaming one receiver's error-free RDS groups as hex text:
    one group per line, four blocks of four hex digits, CR LF
    (`C6B200C8E0CD4349`), as an Inovonics INOmini 633 or RDS Spy sends them.

    While no group has gone out for a second, an all-errored line
    (`---- ---- ---- ----`) is sent each second: the receiver is alive but
    decodes no RDS, so a client can tell "no RDS off air" from "monitor
    silent". Clients only listen; anything they send is ignored.
    """

    HEARTBEAT_S = 1.0
    SEND_TIMEOUT_S = 2.0  # a client that can't take a line in this long is dropped
    BACKLOG = 64          # lines queued for one client; a client this far behind is dropped

    def __init__(self, bind, port):
        self.port = port
        self._clients = {}  # socket -> its queue of lines, sent by its own thread
        self._lock = threading.Lock()
        self._last = 0.0
        self._closed = False
        self._sock = socket.create_server((bind, port))
        self._acceptor = threading.Thread(target=self._accept, daemon=True)
        self._acceptor.start()
        threading.Thread(target=self._heartbeat, daemon=True).start()

    @property
    def clients(self):
        with self._lock:
            return len(self._clients)

    def send_group(self, a, b, c, d):
        self._last = time.monotonic()
        self._send(f'{a:04X}{b:04X}{c:04X}{d:04X}\r\n'.encode())

    def _accept(self):
        # On Windows, closing a listening socket from another thread while
        # accept() blocks on it doesn't reliably stop it listening, so this
        # thread polls for close() and closes the socket itself.
        self._sock.settimeout(0.1)
        while not self._closed:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(self.SEND_TIMEOUT_S)
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            q = queue.Queue(self.BACKLOG)
            with self._lock:
                if self._closed:
                    conn.close()
                    continue
                self._clients[conn] = q
            threading.Thread(target=self._writer, args=(conn, q), daemon=True).start()
        self._sock.close()

    def close(self):
        """Drop every client and stop listening. Returns once the port is free
        (a tenth of a second at most), so it can be opened again at once."""
        self._closed = True
        with self._lock:
            for conn in list(self._clients):
                self._drop(conn)
        self._acceptor.join(1.0)

    def _heartbeat(self):
        while not self._closed:
            time.sleep(self.HEARTBEAT_S)
            if time.monotonic() - self._last >= self.HEARTBEAT_S:
                self._send(b'---- ---- ---- ----\r\n')

    def _send(self, data):
        # Never blocks: the RDS decoder calls this. Each client's own thread
        # does the sending, so a stalled client can't hold the decoder up.
        with self._lock:
            for conn, q in list(self._clients.items()):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    self._drop(conn)

    def _drop(self, conn):
        """Forget a client and close it; its writer then stops. Call holding _lock."""
        q = self._clients.pop(conn, None)
        if q is not None:
            with contextlib.suppress(queue.Full):
                q.put_nowait(None)
        conn.close()

    def _writer(self, conn, q):
        while (data := q.get()) is not None:
            try:
                conn.sendall(data)
            except OSError:
                with self._lock:
                    self._drop(conn)
                return


_cache_root = None


def cache_dir():
    """This session's cache folder (images, service information), made on first use."""
    global _cache_root
    if _cache_root is None:
        _cache_root = tempfile.mkdtemp(prefix=CACHE_PREFIX)
    return _cache_root


def clear_cache(stale=False):
    """Delete this session's cache, or (stale=True) ones left by a session that crashed."""
    global _cache_root
    if stale:
        tmp = tempfile.gettempdir()
        for name in os.listdir(tmp):
            if name.startswith(CACHE_PREFIX) and os.path.join(tmp, name) != _cache_root:
                shutil.rmtree(os.path.join(tmp, name), ignore_errors=True)
    elif _cache_root:
        shutil.rmtree(_cache_root, ignore_errors=True)
        _cache_root = None


class _DnsRecord(ctypes.Structure):
    """The part of Windows' DNS_RECORDW this needs (CNAME and SRV data)."""


_DnsRecord._fields_ = [
    ('pNext', ctypes.POINTER(_DnsRecord)), ('pName', ctypes.c_wchar_p),
    ('wType', ctypes.c_ushort), ('wDataLength', ctypes.c_ushort), ('Flags', ctypes.c_ulong),
    ('dwTtl', ctypes.c_ulong), ('dwReserved', ctypes.c_ulong),
    ('pNameTarget', ctypes.c_wchar_p),   # CNAME: pNameHost; SRV: pNameTarget
    ('wPriority', ctypes.c_ushort), ('wWeight', ctypes.c_ushort), ('wPort', ctypes.c_ushort),
    ('Pad', ctypes.c_ushort)]
DNS_TYPE_CNAME, DNS_TYPE_SRV = 5, 33


def dns_query(name, rtype):
    """CNAME targets or SRV (priority, weight, port, target) for name, through
    Windows' own resolver (no extra packages). [] when there are none (or
    off Windows, where no resolver is wired up)."""
    if os.name != 'nt':
        return []
    dnsapi = ctypes.windll.dnsapi
    dnsapi.DnsQuery_W.argtypes = [ctypes.c_wchar_p, ctypes.c_ushort, ctypes.c_ulong, ctypes.c_void_p,
                                  ctypes.POINTER(ctypes.POINTER(_DnsRecord)), ctypes.c_void_p]
    dnsapi.DnsQuery_W.restype = ctypes.c_long
    result = ctypes.POINTER(_DnsRecord)()
    status = dnsapi.DnsQuery_W(name, rtype, 0, None, ctypes.byref(result), None)
    if status in (9003, 9501):  # name does not exist, no records of this type
        return []
    if status:
        raise OSError(f'DNS query for {name} failed ({status})')
    out, rec = [], result
    try:
        while rec:
            r = rec.contents
            if r.wType == rtype:
                out.append(r.pNameTarget if rtype == DNS_TYPE_CNAME
                           else (r.wPriority, r.wWeight, r.wPort, r.pNameTarget))
            rec = r.pNext
    finally:
        dnsapi.DnsRecordListFree(result, 1)
    return out


def srv_order(records):
    """SRV (priority, weight, port, target) records as [(host, port)] in the
    order to try them (RFC 2782): lowest priority first, and within a priority
    a shuffle weighted by weight. A target of '.' (service not offered) is dropped."""
    out = []
    for prio in sorted({r[0] for r in records}):
        group = [r for r in records if r[0] == prio and r[3].rstrip('.')]
        while group:
            r = random.choices(group, weights=[w or 0.01 for _, w, _, _ in group])[0]
            group.remove(r)
            out.append((r[3].rstrip('.'), r[2]))
    return out


def radiodns_fm(pi, freq_hz, ecc, country):
    """(RadioDNS FQDN, bearerURI) of an FM service, or None when the GCC can't
    be known. GCC = PI country nibble + ECC; without an ECC it is derived from
    the receiver's country (TS 103 270 Annex A; in North America RBDS PIs C
    and B2-B7 are Canada (ECC A1), 1-9, A, B1, B8-BF, D and E the US (A0))."""
    pi = pi.lower()
    if len(pi) != 4:
        return None
    if not ecc and country in ('CA', 'US'):
        if pi[0] == 'c' or (pi[0] == 'b' and pi[1] in '234567'):
            ecc = 0xA1
        elif pi[0] in '123456789ade' or (pi[0] == 'b' and pi[1] in '189abcdef'):
            ecc = 0xA0
    if not ecc:
        return None
    gcc = f'{pi[0]}{ecc:02x}'
    freq = f'{int(round(freq_hz / 1e4)):05d}'  # 10 kHz units: 95.8 MHz -> 09580 (spec table 2)
    return f'{freq}.{pi}.{gcc}.fm.radiodns.org', f'fm:{gcc}.{pi}.{freq}'


def radiodns_iboc(country, facility, program):
    """(RadioDNS FQDN, bearerURI) of an IBOC service from nrsc5's country and
    facility ID: tx is the ID in 5 hex digits, cc the country letters packed
    5 bits each (A=0; US -> 292), mId 2, 3, ... for SPS1, SPS2, ... (TS 103 270 5.1.5)."""
    country = (country or '').upper()
    if len(country) != 2 or not country.isalpha() or facility is None:
        return None
    cc = f'{((ord(country[0]) - 65) << 5) | (ord(country[1]) - 65):03x}'
    tx = f'{facility:05x}'
    mid = f'{program + 1}.' if program else ''
    return f'{mid}{tx}.{cc}.hd.radiodns.org', f'hd:{cc}.{tx}' + (f'.{program + 1}' if program else '')


def _tag(el):
    return el.tag.rsplit('}', 1)[-1]


def parse_si(xml_bytes):
    """Services in an SPI service information file: bearers, names, description, logos."""
    services = []
    for svc in ET.fromstring(xml_bytes).iter():
        if _tag(svc) != 'service':
            continue
        info = {'bearers': [], 'names': {}, 'description': '', 'logos': []}
        for child in svc:
            tag = _tag(child)
            if tag == 'bearer' and child.get('id'):
                info['bearers'].append(child.get('id').lower())
            elif tag in ('shortName', 'mediumName', 'longName'):
                info['names'][tag] = (child.text or '').strip()
            elif tag == 'mediaDescription':
                for media in child:
                    if _tag(media) in ('shortDescription', 'longDescription') and not info['description']:
                        info['description'] = (media.text or '').strip()
                    elif _tag(media) == 'multimedia' and media.get('url'):
                        info['logos'].append((int(media.get('width') or 0), int(media.get('height') or 0),
                                              media.get('url')))
        services.append(info)
    return services


def pick_logo(logos):
    """The smallest square logo of at least 256 px, else the largest logo."""
    square = sorted(l for l in logos if l[0] == l[1] and l[0] >= 256)
    if square:
        return square[0][2]
    return max(logos, key=lambda l: l[0] * l[1])[2] if logos else None


class RadioDns:
    """RadioDNS lookups (ETSI TS 103 270) in a background thread, each FQDN
    once per session. A result is a dict with 'state' (looking up, not
    registered, needs client identifier, client identifier rejected, no
    service information, not listed, found, error) and, as far as it got,
    'target', 'spi', 'name', 'description', 'logo' (a cached file)."""

    USER_AGENT = f'{APP_NAME}/1.0'

    def __init__(self, client_id=None):
        self.client_id = client_id
        self.results = {}
        self._vis = {}     # FQDN -> RadioVis (the slideshow subscription)
        self._si = {}      # SPI host -> parsed services (or an error state)
        self._logos = {}   # logo URL -> cached file
        self._queue = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def lookup(self, fqdn, bearer):
        """The result so far for fqdn; queues the lookup the first time (and
        again RADIODNS_RETRY_S after an error)."""
        r = self.results.get(fqdn)
        if r is None or (r['state'] == 'error' and time.monotonic() - r['at'] > RADIODNS_RETRY_S):
            r = self.results[fqdn] = {'state': 'looking up', 'at': time.monotonic()}
            self._queue.put((fqdn, bearer))
        return r

    def _worker(self):
        while True:
            fqdn, bearer = self._queue.get()
            try:
                result = self._resolve(fqdn, bearer)
            except (OSError, ET.ParseError, ValueError) as e:
                result = {'state': 'error', 'error': str(e)}
            result['at'] = time.monotonic()
            self.results[fqdn] = result

    def vis(self, fqdn):
        """The station's slideshow subscription, or None if it has no RadioVIS.
        Asking keeps it alive; it disconnects RadioVis.IDLE_S after the last ask."""
        result = self.results.get(fqdn) or {}
        if not result.get('vis'):
            return None
        sub = self._vis.get(fqdn)
        if sub is None or sub.stopped:
            service = '/'.join(reversed(fqdn.split('.radiodns.org')[0].split('.')))  # fm/ce1/c479/09580
            sub = self._vis[fqdn] = RadioVis(result['vis'], service, self._download, self.client_id)
        sub.want()
        return sub

    def _resolve(self, fqdn, bearer):
        result = self._resolve_spi(fqdn, bearer)
        if result.get('target'):  # the slideshow is found the same way as the service information
            vis = []
            for transport, name in VIS_TRANSPORTS:
                try:
                    srv = dns_query(f'{name}.{result["target"]}', DNS_TYPE_SRV)
                except OSError:
                    continue
                vis += [(transport, host, port) for host, port in srv_order(srv)]
            if vis:
                result['vis'] = vis
        return result

    def _resolve_spi(self, fqdn, bearer):
        targets = dns_query(fqdn, DNS_TYPE_CNAME)
        if not targets:
            return {'state': 'not registered'}
        target = targets[0].rstrip('.')
        srv = srv_order(dns_query(f'_radiospi._tcp.{target}', DNS_TYPE_SRV))
        if not srv:
            return {'state': 'no service information', 'target': target}
        for i, (host, port) in enumerate(srv):  # the next server only when one can't be reached
            spi = host if port == 443 else f'{host}:{port}'
            try:
                services = self._service_info(spi)
                break
            except (OSError, ET.ParseError):
                if i == len(srv) - 1:
                    raise
        if isinstance(services, str):
            return {'state': services, 'target': target, 'spi': spi}
        base = bearer.rsplit('.', 1)[0] + '.*' if bearer.startswith('fm:') else None
        for svc in services:
            if bearer in svc['bearers'] or (base and base in svc['bearers']):
                names = svc['names']
                logo_url = pick_logo(svc['logos'])
                return {'state': 'found', 'target': target, 'spi': spi,
                        'name': names.get('mediumName') or names.get('longName') or names.get('shortName', ''),
                        'description': svc['description'],
                        'logo': self._logo(logo_url) if logo_url else None}
        return {'state': 'not listed', 'target': target, 'spi': spi}

    def _service_info(self, spi):
        """Parsed services from https://<spi>/radiodns/spi/3.1/SI.xml, fetched
        once per session, or the state why not."""
        if spi not in self._si:
            headers = {'User-Agent': self.USER_AGENT}
            if self.client_id:
                headers['Authorization'] = f'ClientIdentifier {self.client_id}'
            req = urllib.request.Request(f'https://{spi}/radiodns/spi/3.1/SI.xml', headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    self._si[spi] = parse_si(resp.read())
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    return 'needs client identifier'
                if e.code == 403:
                    return 'client identifier rejected'
                raise OSError(f'service information: HTTP {e.code}') from e
        return self._si[spi]

    def _logo(self, url):
        """The image at url, downloaded to the session cache once."""
        if url not in self._logos:
            self._logos[url] = self._download(url)
        return self._logos[url]

    def _download(self, url):
        """The image at url, downloaded to a new file in the session cache.
        OSError if it's over RADIODNS_IMAGE_MAX or isn't an image (by its
        content type or, when a server labels it generically, its first bytes)."""
        req = urllib.request.Request(url, headers={'User-Agent': self.USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read(RADIODNS_IMAGE_MAX + 1)
                ctype = resp.headers.get_content_type()
        except ValueError as e:  # not a URL urllib can fetch
            raise OSError(str(e)) from e
        if len(data) > RADIODNS_IMAGE_MAX:
            raise OSError(f'image over {RADIODNS_IMAGE_MAX >> 20} MB')
        if not ctype.startswith('image/') and not _image_type(data):
            raise OSError(f'not an image ({ctype})')
        ext = os.path.splitext(url.split('?', 1)[0])[1][:5] or '.img'
        fd, path = tempfile.mkstemp(suffix=ext, prefix='radiodns_', dir=cache_dir())
        with os.fdopen(fd, 'wb') as fh:
            fh.write(data)
        return path


class RadioVis:
    """A RadioDNS slideshow (ETSI TS 101 499 clause 7): the current slide image
    (downloaded with fetch(url) -> file), its click-through link and the
    station's slideshow text. Uses the first of the station's servers
    [(transport, host, port)] that works, trying them in order (VIS_TRANSPORTS:
    Server-sent Events, then Stomp, then HTTP long polling) and staying with
    one that worked after it drops. Runs while want() is called.

    A slide with a future trigger-time is downloaded when it arrives and shown
    at that time; one whose time has passed is not shown (5.3.2). One without
    a trigger-time shows at once, as the original RadioVIS (RVIS01) servers
    expect. A slide that can't be downloaded is skipped (error says why) and
    the last one stays. The last SLIDES slides stay cached (stations often
    rotate a few); older ones are deleted."""

    IDLE_S = 60
    SLIDES = 16
    LATE_S = 10       # a trigger-time this far past (clock and network skew) still shows
    TEXT_MAX = 128    # longer slideshow text is ignored (7.2.2)
    URL_MAX = 512     # longer slide and link URLs are ignored (7.2.3, 5.3.3)
    PUSH_TIMEOUT_S = 30  # Server-sent Events: reconnect after this long without a heartbeat (7.6.4)
    HTTP_TIMEOUT_S = 90  # HTTP: a long poll held open this long isn't an error (7.4.2)

    def __init__(self, servers, service, fetch, client_id=None):
        self.servers = list(servers)  # [(transport, host, port)], in the order to try
        self.service = service        # ServiceIdentifier topic path, e.g. fm/ce1/c479/09580
        self.fetch, self.client_id = fetch, client_id
        self.state = 'connecting'
        self.transport = None  # the transport in use (a VIS_TRANSPORTS key)
        self.text = ''
        self.error = None      # why the last slide wasn't shown, until one is
        self.stopped = False
        self._image = self._link = None
        self._pending = []     # (trigger time, seq, file, link) slides waiting for their time, soonest first
        self._seq = itertools.count()
        self._lock = threading.Lock()
        self._done = set()     # (transport, topic) the server refused or ended: not asked again this session
        self._worked = False   # this connection got through (so a drop retries the same server)
        self._wanted = time.monotonic()
        self._slides = OrderedDict()  # url -> cached file, oldest first
        threading.Thread(target=self._run, daemon=True).start()

    @property
    def image(self):
        """The slide on show (a cached file), after showing any whose trigger-time has come."""
        self._due()
        return self._image

    @property
    def link(self):
        """The current slide's click-through URL, or None."""
        self._due()
        return self._link

    def want(self):
        self._wanted = time.monotonic()

    def _idle(self):
        return time.monotonic() - self._wanted > self.IDLE_S

    def _due(self):
        now = time.time()
        with self._lock:
            while self._pending and self._pending[0][0] <= now:
                _, _, self._image, self._link = self._pending.pop(0)

    def _run(self):
        wait, i = 5, 0
        while not self._idle():
            transport, host, port = self.servers[i % len(self.servers)]
            self.transport, self.state = transport, 'connecting'
            self._worked = False
            try:
                getattr(self, '_' + transport)(host, port)
                wait = 5
            except (OSError, ValueError) as e:
                self.state = f'error: {e}'
                if not self._worked:  # couldn't use this server: try the next one
                    i += 1
                if self._worked or i % len(self.servers) == 0:  # dropped, or tried them all: wait first
                    time.sleep(wait)
                    wait = min(wait * 2, 120)
        self.stopped = True

    def _connected(self):
        self.state = 'connected' if self._image is None else 'showing'
        self._worked = True

    # ---- messages (the same from every transport)

    def _message(self, body, link=None, trigger=None):
        """A TEXT or SHOW message body, with a SHOW's link and trigger-time."""
        body = (body or '').strip()
        if body.startswith('SHOW '):
            self._show(body[5:].strip(), link, trigger)
        elif body.startswith('TEXT '):
            self._text(body[5:].strip())

    def _text(self, text):
        if len(text) <= self.TEXT_MAX:
            self.text = text

    @staticmethod
    def _when(trigger):
        """A trigger-time as a time.time() value; None for NOW, none given or unreadable."""
        trigger = (trigger or '').strip()
        if not trigger or trigger.upper() == 'NOW':
            return None
        try:
            t = datetime.datetime.fromisoformat(trigger.replace('Z', '+00:00'))
        except ValueError:
            return None
        if t.tzinfo is None:  # trigger times are UTC (6.2.4)
            t = t.replace(tzinfo=datetime.timezone.utc)
        return t.timestamp()

    def _show(self, url, link=None, trigger=None):
        """A slide: downloaded now, shown now or held until its trigger-time."""
        if not re.match(r'https?://', url) or len(url) > self.URL_MAX:
            return
        when = self._when(trigger)
        if when is not None and when < time.time() - self.LATE_S:
            return  # its time has passed: held, never shown (5.3.2), so not worth downloading
        link = (link or '').strip()
        link = link if re.match(r'https?://', link) and len(link) <= self.URL_MAX else None
        try:
            path = self._slide(url)
        except OSError as e:  # keep the connection and the slide on show
            self.error = f'{url}: {e}'
            return
        self.error = None
        with self._lock:
            if when is None or when <= time.time():
                self._image, self._link = path, link
                self.state = 'showing'
            else:
                bisect.insort(self._pending, (when, next(self._seq), path, link))
                del self._pending[self.SLIDES // 2:]  # a flood of future slides can't evict the cache

    def _slide(self, url):
        path = self._slides.pop(url, None)
        if path is None or not os.path.exists(path):
            path = self.fetch(url)
        self._slides[url] = path
        with self._lock:
            keep = {self._image} | {p[2] for p in self._pending}
        old = [u for u, p in self._slides.items() if p not in keep]
        for u in old[:max(0, len(self._slides) - self.SLIDES)]:
            try:
                os.remove(self._slides.pop(u))
            except OSError:
                pass
        return path

    # ---- Server-sent Events (7.6)

    def _push_url(self, host, port):
        netloc = host if port in (80, 443) else f'{host}:{port}'
        return f'{"http" if port == 80 else "https"}://{netloc}/radiodns/push/3/{self.service}'

    def _push(self, host, port):
        url = self._push_url(host, port)
        headers = {'User-Agent': RadioDns.USER_AGENT, 'Accept': 'text/event-stream'}
        if self.client_id:
            headers['Authorization'] = f'ClientIdentifier {self.client_id}'
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.PUSH_TIMEOUT_S) as resp:
            self._connected()
            event, data = '', []
            for raw in resp:  # a read that times out (no heartbeat) raises, and the caller reconnects
                if self._idle():
                    return
                line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
                if not line:  # the end of an event
                    if data:
                        self._push_event(event, '\n'.join(data))
                    event, data = '', []
                elif not line.startswith(':'):  # ':' alone is the heartbeat
                    key, _, value = line.partition(':')
                    value = value[1:] if value.startswith(' ') else value
                    if key == 'event':
                        event = value
                    elif key == 'data':
                        data.append(value)
            raise OSError('the slideshow server closed the connection')

    def _push_event(self, event, data):
        try:
            d = json.loads(data)
        except ValueError:
            return
        if not isinstance(d, dict):
            return
        if event == 'image' and isinstance(d.get('src'), str):
            self._show(d['src'].strip(), d.get('link'), d.get('triggerTime'))
        elif event == 'text' and isinstance(d.get('body'), str):
            self._text(d['body'].strip())

    # ---- Stomp (7.3)

    def _stomp(self, host, port):
        with socket.create_connection((host, port), timeout=15) as sock:
            send = lambda frame: sock.sendall(frame.encode() + b'\0')  # noqa: E731
            sock.settimeout(1)
            frames = self._stomp_frames(sock)
            send(f'CONNECT\naccept-version:1.0\nhost:{host}\n\n')
            self._stomp_wait(frames, lambda cmd, h: cmd == 'CONNECTED', 15)
            subscribed = 0
            for i, kind in enumerate(('image', 'text')):
                dest = f'/topic/{self.service}/{kind}'
                if ('stomp', dest) in self._done:
                    continue
                # one destination at a time, each confirmed by its receipt within 10 s (7.3.2)
                send(f'SUBSCRIBE\nid:{i}\ndestination:{dest}\nack:auto\nreceipt:{i}\n\n')
                if self._stomp_wait(frames, lambda cmd, h: cmd == 'RECEIPT' and h.get('receipt-id') == str(i), 10,
                                    refused=True):
                    subscribed += 1
                else:
                    self._done.add(('stomp', dest))
            if not subscribed:
                raise ValueError('the slideshow server refused every topic')
            self._connected()
            self._stomp_wait(frames, lambda cmd, h: False, None)

    def _stomp_wait(self, frames, until, timeout_s, refused=False):
        """Handles frames until one matches until(command, headers): True. False
        when timeout_s passes first or (refused=True) on an ERROR frame; an
        ERROR otherwise raises. Returns on going idle."""
        end = None if timeout_s is None else time.monotonic() + timeout_s
        for cmd, headers, body in frames:
            if cmd is None:  # a second without a frame
                if end is not None and time.monotonic() > end:
                    if refused:
                        return False
                    raise OSError('the slideshow server did not answer')
                continue
            if until(cmd, headers):
                return True
            if cmd == 'ERROR':
                if refused:
                    return False
                raise ValueError(headers.get('message') or body.strip() or 'refused')
            if cmd == 'MESSAGE':
                self._message(body, headers.get('link'), headers.get('trigger-time'))
        return False

    def _stomp_frames(self, sock):
        """(command, headers, body) for each frame received; (None, None, None)
        after a second without one. Ends on going idle."""
        buf = b''
        while not self._idle():
            try:
                data = sock.recv(65536)
            except socket.timeout:
                yield None, None, None
                continue
            if not data:
                raise OSError('the slideshow server closed the connection')
            buf += data
            while b'\0' in buf:
                frame, buf = buf.split(b'\0', 1)
                head, _, body = frame.lstrip(b'\r\n').decode('utf-8', errors='replace').partition('\n\n')
                lines = head.splitlines()
                if lines:
                    headers = {}
                    for line in lines[1:]:
                        key, sep, value = line.partition(':')
                        if sep:
                            headers.setdefault(key.strip(), value.strip())  # the first of a repeated header wins
                    yield lines[0].strip(), headers, body

    # ---- HTTP long polling (7.4)

    def _http(self, host, port):
        netloc = host if port in (80, 443) else f'{host}:{port}'
        base = f'{"https" if port == 443 else "http"}://{netloc}/radiodns/vis/vis.json'
        topics = [t for t in (f'/topic/{self.service}/image', f'/topic/{self.service}/text')
                  if ('http', t) not in self._done]
        if not topics:
            raise ValueError('the slideshow server refused every topic')
        errors = []
        polls = [threading.Thread(target=self._http_poll, args=(base, t, errors), daemon=True) for t in topics]
        for t in polls:  # one long poll per topic
            t.start()
        for t in polls:
            t.join()
        if errors:
            raise errors[0]

    def _http_poll(self, base, topic, errors):
        try:
            last_id = None
            while not self._idle():
                query = {'topic': topic} if last_id is None else {'topic': topic, 'last_id': last_id}
                req = urllib.request.Request(f'{base}?{urllib.parse.urlencode(query)}',
                                             headers={'User-Agent': RadioDns.USER_AGENT})
                try:
                    with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT_S) as resp:
                        self._connected()
                        frames = resp.read(32 << 10)  # at most 16 kB (7.4.6), and some slack
                except urllib.error.HTTPError as e:
                    if e.code == 404:  # the server doesn't have this topic: not asked again (7.4.7)
                        self._done.add(('http', topic))
                        return
                    raise
                except TimeoutError:  # the server had nothing to say: ask again (7.4.2)
                    continue
                frames = frames.decode('utf-8', errors='replace').strip()
                if m := re.fullmatch(r'[\w$.]+\((.*)\)\s*;?', frames, re.S):  # JSONP (7.4.5)
                    frames = m.group(1)
                frames = json.loads(frames)
                if isinstance(frames, dict):
                    frames = [frames]
                last_id = None
                for frame in frames[:8] if isinstance(frames, list) else ():  # oldest first (7.4.4)
                    if not isinstance(frame, dict):
                        continue
                    h = frame.get('headers') or {}
                    last_id = h.get('RadioVIS-Message-ID') or last_id
                    self._message(frame.get('body'), h.get('RadioVIS-Link'), h.get('RadioVIS-Trigger-Time'))
                if last_id is None:  # no message ID: don't ask again this session (7.4.3.2)
                    self._done.add(('http', topic))
                    return
        except (OSError, ValueError) as e:
            errors.append(e)


class IbocPipe(gr.sync_block):
    """Hands cs16 IQ to nrsc5's stdin from a writer thread. If nrsc5 falls
    behind, blocks are dropped (and counted) rather than stalling the SDR,
    which would hold up every receiver."""

    def __init__(self, stdin):
        gr.sync_block.__init__(self, name='iboc_pipe', in_sig=[(np.int16, IBOC_BATCH)], out_sig=None)
        self.dropped = 0
        self._q = queue.Queue(maxsize=64)
        threading.Thread(target=self._writer, args=(stdin,), daemon=True).start()

    def work(self, input_items, output_items):
        for batch in input_items[0]:
            try:
                self._q.put_nowait(batch.tobytes())
            except queue.Full:
                self.dropped += 1
        return len(input_items[0])

    def close(self):
        while True:  # make room for the stop marker
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._q.put(None)

    def _writer(self, stdin):
        while (data := self._q.get()) is not None:
            try:
                stdin.write(data)
            except (OSError, ValueError):
                break
        try:
            stdin.close()
        except OSError:
            pass


class IbocDecoder:
    """Decodes one station's IBOC with nrsc5. Cuts a +/-280 kHz channel (the
    IBOC sidebands sit 129-199 kHz either side of the carrier) out of the
    wideband stream, resamples it to IBOC_RATE and pipes it to nrsc5, which
    plays the chosen programme itself. nrsc5's log is parsed into status."""

    LOG = re.compile(r'^(?:\d\d:\d\d:\d\d )?(.*)$')

    def __init__(self, nrsc5, offset_hz, program):
        self.program = program
        self.status = {'synced': False, 'name': '', 'slogan': '', 'message': '',
                       'title': '', 'artist': '', 'album': '', 'genre': '', 'comment': '',
                       'alert': None, 'kbps': None, 'mer': None, 'ber': None, 'services': {},
                       'country': None, 'facility': None}
        # LOT files (images) land in a cache folder of this decoder's own, deleted in stop().
        self.cache = tempfile.mkdtemp(prefix='iboc_', dir=cache_dir())
        self._lock = threading.Lock()
        self._ports = {}         # LOT port -> (SIG audio service number or None, component MIME)
        self._lots = []          # (port, lot, path, received at)
        self._xhdr_lot = None    # album art LOT the current song's XHDR names
        self._sig = None
        self.proc = subprocess.Popen(self.command(nrsc5, program, self.cache), stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        rate = SAMP_RATE / IBOC_DECIM
        self.xlate = filter.freq_xlating_fir_filter_ccf(
            IBOC_DECIM, firdes.low_pass(1.0, SAMP_RATE, 280e3, 150e3), offset_hz, SAMP_RATE)
        resamp = filter.pfb.arb_resampler_ccf(IBOC_RATE / rate, flt_size=32)
        agc = analog.agc_cc(1e-4, 0.3, 1.0)  # constant-envelope FM: keep cs16 well scaled
        agc.set_max_gain(65536)
        to_s16 = blocks.complex_to_interleaved_short(False, 32767.0)
        self.pipe = IbocPipe(self.proc.stdin)
        self.blocks = (self.xlate, resamp, agc, to_s16, _batch(gr.sizeof_short, IBOC_BATCH), self.pipe)
        threading.Thread(target=self._read_log, daemon=True).start()

    @staticmethod
    def command(nrsc5, program, cache):
        return [nrsc5, '-r', '-', '--iq-input-format', 'cs16', '--dump-aas-files', cache, str(program)]

    def set_offset(self, offset_hz):
        self.xlate.set_center_freq(offset_hz)

    def stop(self):
        self.pipe.close()
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
        shutil.rmtree(self.cache, ignore_errors=True)

    def images(self):
        """(station logo, album art): cached files, or None.

        The logo is the newest file on a station-logo component, the art the
        file the current song's XHDR names on an album-art component. Files on
        this programme's SIG service are preferred (SIG audio service N is
        taken as programme N-1); without SIG information any will do."""
        with self._lock:
            def pick(mime, lot=None):
                files = [(port, n, path, at) for port, n, path, at in self._lots
                         if self._ports.get(port, (None, None))[1] == mime and (lot is None or n == lot)]
                ours = [f for f in files if self._ports[f[0]][0] == self.program + 1]
                files = ours or files
                return max(files, key=lambda f: f[3])[2] if files else None
            art = pick(MIME_PRIMARY_IMAGE, self._xhdr_lot) if self._xhdr_lot is not None else None
            return pick(MIME_STATION_LOGO), art

    def _add_lot(self, port, lot, name):
        path = os.path.join(self.cache, f'{lot}_{name}')
        now = time.monotonic()
        with self._lock:
            self._lots = [f for f in self._lots if f[2] != path] + [(port, lot, path, now)]
        keep = set(self.images())
        with self._lock:  # prune old images nothing shows
            for f in [f for f in self._lots if now - f[3] > IMAGE_KEEP_S and f[2] not in keep]:
                self._lots.remove(f)
                try:
                    os.remove(f[2])
                except OSError:
                    pass

    def _read_log(self):
        for raw in self.proc.stderr:
            self.parse(raw.decode('utf-8', 'replace').strip())
        self.status['synced'] = False

    def parse(self, line):
        """Update status from one line of nrsc5's log. ID3 (PSD) fields arrive
        only for the programme being played, title first, so a new title
        clears the last song's album, genre and comment."""
        st = self.status
        line = self.LOG.match(line).group(1)
        if line == 'Synchronized':
            st['synced'] = True
        elif line == 'Lost synchronization':
            st['synced'] = False
        elif line.startswith('Station name: '):
            st['name'] = line[14:].strip()
        elif line.startswith('Slogan: '):
            st['slogan'] = line[8:].strip()
        elif line.startswith('Message: '):
            st['message'] = line[9:].strip()
        elif line.startswith('Title: '):
            title = line[7:].strip()
            if title != st['title']:
                st['album'] = st['genre'] = st['comment'] = ''
                self._xhdr_lot = None   # the new song's XHDR (if any) follows
            st['title'] = title
        elif line.startswith('Artist: '):
            st['artist'] = line[8:].strip()
        elif line.startswith('Album: '):
            st['album'] = line[7:].strip()
        elif line.startswith('Genre: '):
            st['genre'] = line[7:].strip()
        elif m := re.match(r'Comment: lang=\S* (.*)$', line):
            st['comment'] = m.group(1).strip()
        elif line == 'Alert ended':
            st['alert'] = None
        elif line.startswith('Alert: '):
            st['alert'] = line[7:].strip()
        elif m := re.match(r'Audio bit rate: ([\d.]+) kbps', line):
            st['kbps'] = float(m.group(1))
        elif m := re.match(r'MER: ([-\d.]+) dB \(lower\), ([-\d.]+) dB \(upper\)', line):
            st['mer'] = (float(m.group(1)), float(m.group(2)))
        elif m := re.match(r'BER: ([\d.]+)', line):
            st['ber'] = float(m.group(1))
        elif m := re.match(r'Audio service (\d+): (\w+), type: ([^,]+)', line):
            st['services'] = {**st['services'], int(m.group(1)): m.group(3)}
        elif m := re.match(r'Country: (\w+), FCC facility ID: (\d+)', line):
            st['country'], st['facility'] = m.group(1), int(m.group(2))
        elif m := re.match(r'\s*SIG Service: type=(\w+) number=(\d+)', line):
            self._sig = int(m.group(2)) if m.group(1) == 'audio' else None
        elif m := re.match(r'\s*Data component: id=\d+ port=([0-9A-Fa-f]+) .*mime=([0-9A-Fa-f]+)', line):
            with self._lock:
                self._ports[int(m.group(1), 16)] = (self._sig, int(m.group(2), 16))
        elif m := re.match(r'LOT file: port=([0-9A-Fa-f]+) lot=(\d+) name=(.*?) size=\d+ mime=', line):
            self._add_lot(int(m.group(1), 16), int(m.group(2)), m.group(3))
        elif m := re.match(r'XHDR: (-?\d+) ([0-9A-Fa-f]+) (-?\d+)', line):
            param, mime, lot = int(m.group(1)), int(m.group(2), 16), int(m.group(3))
            if param == 0 and mime == MIME_PRIMARY_IMAGE:
                self._xhdr_lot = lot       # show this LOT as the song's album art
            elif param == 1:
                self._xhdr_lot = None      # flush: no image for this song


class PcmTap(gr.sync_block):
    """A receiver's browser audio. Inputs: analog L, analog R, SCA 67 and
    SCA 92 (mono). The chosen source (`source`: an index into WEB_SOURCES'
    values) goes as interleaved 16-bit stereo at `gain` to every function in
    `sinks` (one per listener); with no listeners nothing is done."""

    def __init__(self):
        gr.sync_block.__init__(self, name='pcm_tap', in_sig=[(np.float32, WEB_BATCH)] * 4, out_sig=None)
        self.sinks = {}
        self.source = 0
        self.gain = 0.0

    def work(self, input_items, output_items):
        sinks = list(self.sinks.values())
        if sinks:
            ins = input_items
            left, right = (ins[0], ins[1]) if self.source == 0 else (ins[self.source + 1],) * 2
            left, right = left.reshape(-1), right.reshape(-1)
            pcm = np.empty(2 * len(left), np.int16)
            k = self.gain * 32767
            pcm[0::2] = np.clip(left * k, -32768, 32767)
            pcm[1::2] = np.clip(right * k, -32768, 32767)
            data = pcm.tobytes()
            for sink in sinks:
                sink(data)
        return len(input_items[0])


def find_ffmpeg():
    """ffmpeg on the PATH, else one beside this folder (the installer's), else a WinGet install, else None."""
    found = shutil.which('ffmpeg')
    if found:
        return found
    bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ffmpeg',
                           'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    if os.path.exists(bundled):
        return os.path.normpath(bundled)
    pattern = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Packages',
                           '*FFmpeg*', '**', 'bin', 'ffmpeg.exe')
    matches = sorted(glob.glob(pattern, recursive=True))
    return matches[-1] if matches else None


def ffmpeg_formats(ffmpeg, wanted):
    """The WEB_FORMATS keys in `wanted` (in its order) that this ffmpeg can encode."""
    if not ffmpeg:
        return []
    try:
        out = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    encoders = {line.split()[1] for line in out.splitlines() if len(line.split()) > 1 and line.startswith(' A')}
    return [f for f in wanted if f in WEB_FORMATS and WEB_FORMATS[f]['encoder'] in encoders]


class AudioEncoder:
    """One listener's browser audio: an ffmpeg encoding a receiver's PcmTap to
    `fmt` (a WEB_FORMATS key) from the start of the stream, so formats with a
    header (Ogg, FLAC) are whole. Audio is dropped, never queued without
    limit, if ffmpeg falls behind, so the flowgraph is never held up."""

    def __init__(self, ffmpeg, tap, fmt):
        self.tap = tap
        self.proc = subprocess.Popen(
            [ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 's16le', '-ar', str(AUDIO_RATE), '-ac', '2',
             '-i', 'pipe:0', *WEB_FORMATS[fmt]['args'], '-flush_packets', '1', 'pipe:1'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._pcm = queue.Queue(maxsize=64)
        threading.Thread(target=self._write, daemon=True).start()
        tap.sinks[id(self)] = self._feed

    def _feed(self, data):
        try:
            self._pcm.put_nowait(data)
        except queue.Full:  # ffmpeg stalled: drop audio rather than hold up the flowgraph
            pass

    def _write(self):
        while (data := self._pcm.get()) is not None:
            try:
                self.proc.stdin.write(data)
            except (OSError, ValueError):
                break
        try:
            self.proc.stdin.close()
        except OSError:
            pass

    def chunks(self):
        """The encoded stream, until it ends."""
        while chunk := self.proc.stdout.read1(8192):
            yield chunk

    def close(self):
        self.tap.sinks.pop(id(self), None)
        while True:  # make room for the end marker
            try:
                self._pcm.put_nowait(None)
                break
            except queue.Full:
                try:
                    self._pcm.get_nowait()
                except queue.Empty:
                    pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class WebAudio:
    """A receiver's browser audio: its PcmTap and the encoders of its listeners."""

    def __init__(self, ffmpeg, tap):
        self.ffmpeg, self.tap = ffmpeg, tap
        self._encoders = set()
        self._lock = threading.Lock()

    @property
    def listeners(self):
        return len(self._encoders)

    def open(self, fmt):
        enc = AudioEncoder(self.ffmpeg, self.tap, fmt)
        with self._lock:
            self._encoders.add(enc)
        return enc

    def close(self, enc):
        with self._lock:
            self._encoders.discard(enc)
        enc.close()

    def close_all(self):
        """End every listener's stream (the receiver is going)."""
        with self._lock:
            encoders, self._encoders = list(self._encoders), set()
        for enc in encoders:
            self.tap.sinks.pop(id(enc), None)
            enc.proc.kill()


def _deemph_taps(tau, fs=AUDIO_RATE):
    """De-emphasis IIR taps, computed as gnuradio.analog.fm_deemph does
    (bilinear transform, pre-warped), so tau can change while running."""
    w_ca = 2.0 * fs * math.tan(1.0 / tau / (2.0 * fs))
    k = -w_ca / (2.0 * fs)
    b0 = -k / (1.0 - k)
    return [b0, b0], [1.0, -(1.0 + k) / (1.0 - k)]


def _min_buffer(block, items):
    """set_min_output_buffer without the info line GNU Radio logs for each call."""
    log = gr.logging()
    level = log.default_level()
    log.set_default_level(gr.log_levels.warn)
    block.set_min_output_buffer(items)
    log.set_default_level(level)
    return block


def _batch(itemsize, n, buffers=64):
    """stream_to_vector feeding a Python meter. GNU Radio sizes buffers in
    bytes, so with big vectors the default holds only a couple of batches and a
    brief Python stall would back up into the SDR (overflows); keep ~0.25 s."""
    return _min_buffer(blocks.stream_to_vector(itemsize, n), buffers)


class FmStation(gr.hier_block2):
    """One station: channel select -> WBFM -> stereo audio, RDS and meters.

    Input: complex wideband IQ at SAMP_RATE. Outputs: L and R audio at AUDIO_RATE.
    """

    def __init__(self, freq_hz, center_hz):
        gr.hier_block2.__init__(self, f'fm_station_{freq_hz / 1e6:.1f}',
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),
                                gr.io_signature(2, 2, gr.sizeof_float))
        self.freq_hz = freq_hz
        self.stereo = False      # decoding stereo now
        self.pilot = False       # a 19 kHz pilot is present
        self.force_mono = False
        self.pilot_hz = None
        self.volume = 1.0
        self.playing = False
        self.audio_source = 'analog'
        self.iboc = None         # IbocDecoder while IBOC is playing

        self.chan = chan = filter.freq_xlating_fir_filter_ccf(
            # Wide and flat: an FM signal's sidebands reach well past +/-100 kHz,
            # and cutting them distorts the MPX (L-R, RDS and SCA read low).
            CHAN_DECIM, firdes.low_pass(1.0, SAMP_RATE, CHAN_PASS_HZ + 17.5e3, 35e3),
            freq_hz - center_hz, SAMP_RATE)
        chan.set_output_multiple(CHAN_CHUNK)
        demod = analog.quadrature_demod_cf(QUAD_RATE / (2 * math.pi * MAX_DEV))

        # Stereo decoder: lock a PLL to the 19 kHz pilot, double it to 38 kHz,
        # and use it to bring L-R down to baseband (as in gr-rds' rds_rx example).
        pilot_taps = firdes.complex_band_pass(1.0, QUAD_RATE, 18980, 19020, 4000)  # wide; the PLL does the tracking
        pilot_bpf = filter.fir_filter_fcc(1, pilot_taps)
        self.pll = pll = analog.pll_refout_cc(0.001, 2 * math.pi * 19020 / QUAD_RATE,
                                   2 * math.pi * 18980 / QUAD_RATE)
        square = blocks.multiply_cc()
        ref38 = blocks.complex_to_imag()
        delay = blocks.delay(gr.sizeof_float, (len(pilot_taps) - 1) // 2)
        mix38 = blocks.multiply_ff()
        audio_taps = firdes.low_pass(1.0, QUAD_RATE, 15e3, 2e3)
        sum_lpf = filter.fir_filter_fff(AUDIO_DECIM, audio_taps)            # (L+R)/2
        # The carrier offset is DC in L+R: block it, as a receiver's audio is AC-coupled
        # (5 Hz high-pass), so it doesn't reach the audio, true peak or L/R meters.
        pole = math.exp(-2 * math.pi * 5 / AUDIO_RATE)
        sum_ac, diff_ac = (filter.iir_filter_ffd([(1 + pole) / 2, -(1 + pole) / 2], [1.0, -pole], False)
                           for _ in range(2))  # the same on L-R, keeping L+R and L-R matched
        # (L-R)/2; the quadrature demodulator's output is down by sinc(f/fs) at 38 kHz
        diff_lpf = filter.fir_filter_fff(AUDIO_DECIM, [-2 / np.sinc(38e3 / QUAD_RATE) * t for t in audio_taps])
        self.diff_gain = blocks.multiply_const_ff(0.0)  # 0 = mono until a pilot shows up
        left, right = blocks.add_ff(), blocks.sub_ff()
        self.deemph = deemph = [filter.iir_filter_ffd(*_deemph_taps(75e-6), False) for _ in range(2)]
        self.play_gain = [blocks.multiply_const_ff(0.0) for _ in range(2)]
        out_mix = [blocks.add_ff() for _ in range(2)]  # analog L/R + SCA 67 + SCA 92

        # SCA audio: the 67 and 92 kHz FM subcarriers, mono, 5 kHz, 150 us.
        self.sca_gain = {}
        sca_out = {}
        sca_demods = []
        for k, khz in enumerate((67, 92)):
            sca_bb = filter.freq_xlating_fir_filter_fcc(          # 384 -> 48 kS/s
                AUDIO_DECIM, firdes.low_pass(1.0, QUAD_RATE, 8e3, 3e3), khz * 1e3, QUAD_RATE)
            sca_demod = analog.quadrature_demod_cf(AUDIO_RATE / (2 * math.pi * SCA_DEV))
            sca_lpf = filter.fir_filter_fff(1, firdes.low_pass(1.0, AUDIO_RATE, 5e3, 1e3))
            sca_deemph = filter.iir_filter_ffd(*_deemph_taps(SCA_DEEMPH_S), False)
            gain = self.sca_gain[khz] = blocks.multiply_const_ff(0.0)
            self.connect(demod, sca_bb, sca_demod, sca_lpf, sca_deemph, gain)
            sca_out[f'sca{khz}'] = sca_deemph
            sca_demods.append(sca_demod)
            for ch in range(2):
                self.connect(gain, (out_mix[ch], 1 + k))

        # RDS: same chain as gr-rds' rds_rx example.
        rds_bb = filter.freq_xlating_fir_filter_fcc(            # 384 -> 24 kS/s
            int(QUAD_RATE / 24e3), firdes.low_pass(1.0, QUAD_RATE, 7.5e3, 5e3), 57e3, QUAD_RATE)
        resamp = filter.rational_resampler_ccc(19, 24)          # 24 kS/s -> 19 kS/s
        rrc = firdes.root_raised_cosine(1, 19e3, 19e3 / 8, 1.0, 151)
        manchester = filter.fir_filter_ccc(1, [rrc[n] - rrc[n + 8] for n in range(len(rrc) - 8)])
        agc = analog.agc_cc(2e-3, 0.585, 53)
        agc.set_max_gain(1000)
        bpsk = digital.constellation_bpsk().base()
        sync = digital.symbol_sync_cc(digital.TED_ZERO_CROSSING, 16, 0.01, 1.0, 1.0, 0.1, 1,
                                      bpsk, digital.IR_MMSE_8TAP, 128, [])
        costas = digital.constellation_receiver_cb(bpsk, 2 * math.pi / 100, -0.002, 0.002)
        diff = digital.diff_decoder_bb(2, digital.DIFF_DIFFERENTIAL)
        decoder = rds.decoder(False, False)
        self.parser = parser = rds.parser(False, False, 1)  # 1 = North American RBDS PTY names

        self.meter = FmMeter(on_stats=self._auto_stereo)
        self.audio_meter = AudioMeter()
        self.sca_meter = ScaMeter()
        for k, sca_demod in enumerate(sca_demods):
            self.connect(sca_demod, _batch(gr.sizeof_float, SCA_BATCH, 8), (self.sca_meter, k))
        self.rds = RdsState()

        self.connect(self, chan, demod)
        self.connect(chan, _batch(gr.sizeof_gr_complex, FM_BATCH), (self.meter, 0))
        self.connect(demod, _batch(gr.sizeof_float, FM_BATCH), (self.meter, 1))
        # stereo
        self.connect(demod, pilot_bpf, pll)
        self.connect(pll, (square, 0))
        self.connect(pll, (square, 1))
        self.connect(square, ref38, (mix38, 1))
        self.connect(demod, delay, sum_lpf, sum_ac)
        self.connect(delay, (mix38, 0))
        self.connect(mix38, diff_lpf, diff_ac, self.diff_gain)
        self.connect(sum_ac, (left, 0))
        self.connect(self.diff_gain, (left, 1))
        self.connect(sum_ac, (right, 0))
        self.connect(self.diff_gain, (right, 1))
        for i, ch in enumerate((left, right)):
            self.connect(ch, deemph[i], self.play_gain[i], (out_mix[i], 0))
            self.connect(out_mix[i], (self, i))
            self.connect(deemph[i], _batch(gr.sizeof_float, AUDIO_BATCH), (self.audio_meter, i))
        # pre-de-emphasis M and S for the L/R/L+R/L-R modulation meters
        self.connect(sum_ac, _batch(gr.sizeof_float, AUDIO_BATCH), (self.audio_meter, 2))
        self.connect(self.diff_gain, _batch(gr.sizeof_float, AUDIO_BATCH), (self.audio_meter, 3))
        # RDS
        self.connect(demod, rds_bb, resamp, manchester, agc, sync, costas, diff, decoder)
        self.msg_connect(decoder, 'out', parser, 'in')
        self.msg_connect(decoder, 'out', self.rds, 'groups')
        self.msg_connect(parser, 'out', self.rds, 'parsed')

        # Browser audio: this receiver's audio source at a fixed level (the
        # browser has its own volume), whether or not it plays on the PC.
        self.web_tap = PcmTap()
        for k, src in enumerate((deemph[0], deemph[1], sca_out['sca67'], sca_out['sca92'])):
            self.connect(src, _batch(gr.sizeof_float, WEB_BATCH, 8), (self.web_tap, k))

    def retune(self, freq_hz, center_hz):
        """Follow a new SDR centre and/or switch to another station."""
        self.chan.set_center_freq(freq_hz - center_hz)
        if freq_hz != self.freq_hz:
            self.freq_hz = freq_hz
            self.stereo = self.pilot = False
            self.pilot_hz = None
            self.diff_gain.set_k(0.0)
            self.parser.reset()
            self.rds.reset(on_release=self.parser.reset)
            self.meter.reset()
            self.audio_meter.reset()
            self.sca_meter.reset()

    def apply_settings(self, settings):
        """De-emphasis, stereo/mono and play volume from ReceiverSettings."""
        b, a = _deemph_taps(settings.deemphasis_us * 1e-6)
        for d in self.deemph:
            d.set_taps(b, a)
        self.force_mono = settings.stereo == 'mono'
        self.volume = settings.volume_pct / 100
        self.set_playing(self.playing)

    def _auto_stereo(self, stats):
        """Decode stereo only while a pilot is present (with hysteresis) and
        mono isn't forced."""
        self.pilot = stats['pilot_pct'] > (2.0 if self.pilot else 3.0)
        on = self.pilot and not self.force_mono
        if on != self.stereo:
            self.stereo = on
            self.diff_gain.set_k(1.0 if on else 0.0)
        # Pilot frequency from the PLL that locks to it (spec: 19 kHz +/- 2 Hz).
        if self.pilot:
            hz = self.pll.get_frequency() * QUAD_RATE / (2 * math.pi)
            self.pilot_hz = hz if self.pilot_hz is None else self.pilot_hz + 0.1 * (hz - self.pilot_hz)
        else:
            self.pilot_hz = None

    def set_playing(self, on):
        self.set_audio(self.audio_source, on)

    def set_audio(self, source, on):
        """Play `source` (an AUDIO_SOURCES key) through the app's audio, or
        nothing. IBOC plays through nrsc5, so its keys mute this output."""
        self.audio_source, self.playing = source, on
        level = PLAY_GAIN * self.volume if on else 0.0
        for g in self.play_gain:
            g.set_k(level if source == 'analog' else 0.0)
        for khz, g in self.sca_gain.items():
            g.set_k(level * SCA_LEVEL if source == f'sca{khz}' else 0.0)
        web = WEB_SOURCES.get(source)  # browser audio: the same source (IBOC: silence)
        self.web_tap.source = web or 0
        self.web_tap.gain = 0.0 if web is None else PLAY_GAIN * (SCA_LEVEL if web else 1.0)


def _centre(freqs_hz):
    """SDR centre for these stations: as near their midpoint as keeps every
    carrier DC_CLEAR_HZ off the RSP1A's DC offset and IMAGE_CLEAR_HZ off every
    other station's IQ image, with no station more than EDGE_HZ out. On the
    midpoint itself a lone station sits on the DC offset, and the two end
    stations sit on each other's images."""
    freqs = sorted(set(freqs_hz))
    mid = (freqs[0] + freqs[-1]) / 2
    room = max(0.0, EDGE_HZ - (freqs[-1] - freqs[0]) / 2)

    def clearance(c):
        dc = min(abs(f - c) for f in freqs) / DC_CLEAR_HZ
        image = min((abs(2 * c - a - b) for a in freqs for b in freqs if a < b), default=math.inf) / IMAGE_CLEAR_HZ
        return min(dc, image, 1.0)

    shifts = sorted((k * 25e3 for k in range(-int(room // 25e3), int(room // 25e3) + 1)), key=lambda s: (abs(s), -s))
    return max((mid + s for s in shifts), key=clearance)  # first (smallest shift) of the best


class FmMonitor(gr.top_block):
    """The RSP1A and up to MAX_RECEIVERS receivers, added and removed while
    running. Each receiver has a fixed slot (receiver 1-4): its input on the
    audio mixer and its RDS feed port. An empty slot feeds the mixer silence.
    The SDR re-centres on the receivers' stations whenever they change."""

    def __init__(self, receivers, lna_state, if_gain_reduction, source=None, source_factory=None):
        """receivers: {slot: freq_hz}, or a list of freqs for slots 0, 1, ..."""
        gr.top_block.__init__(self, APP_NAME)
        receivers = dict(enumerate(receivers)) if isinstance(receivers, (list, tuple)) else dict(receivers)
        self.center_hz = _centre(receivers.values())
        self.lna, self.ifgr = lna_state, if_gain_reduction
        self.gain_auto = False         # set by whoever calibrated the gain
        self.cal_center_hz = None      # where it was calibrated
        self._source_factory = source_factory  # () -> a new source, for reopening (tests); else the RSP1A
        self._sdr_lock = threading.RLock()  # the SDR reopening thread vs IBOC changes on the GUI thread
        self.src = _min_buffer(source or make_rsp1a(self.center_hz, lna_state, if_gain_reduction), SRC_BUFFER)
        self.adc = AdcMeter()  # the wideband peak, for the overload warning
        self._adc_in = _batch(gr.sizeof_gr_complex, ADC_BATCH, 8)
        self.connect(self.src, self._adc_in, self.adc)
        self.slots = [None] * MAX_RECEIVERS
        self._mix = [blocks.add_ff(), blocks.add_ff()]
        self._silence = [[blocks.null_source(gr.sizeof_float) for _ in range(2)]
                         for _ in range(MAX_RECEIVERS)]
        sink = audio.sink(AUDIO_RATE, '', True)
        for ch in range(2):
            self.connect(self._mix[ch], (sink, ch))
        for slot in range(MAX_RECEIVERS):
            if slot in receivers:
                self.slots[slot] = FmStation(receivers[slot], self.center_hz)
                self._plug(slot, self.slots[slot])
            else:
                self._plug_silence(slot)

    @property
    def stations(self):
        return [st for st in self.slots if st]

    def free_slot(self):
        return next((i for i, st in enumerate(self.slots) if st is None), None)

    def add_receiver(self, freq_hz):
        """Open a receiver on freq_hz in the first free slot; returns (slot, station)."""
        slot = self.free_slot()
        if slot is None:
            raise ValueError(f'all {MAX_RECEIVERS} receivers are in use')
        st = FmStation(freq_hz, self.center_hz)
        self.lock()  # rewire the running flowgraph
        try:
            self._unplug_silence(slot)
            self._plug(slot, st)
            self.slots[slot] = st
        finally:
            self.unlock()
        self._recentre()
        return slot, st

    def start_iboc(self, slot, program, nrsc5):
        """Attach an IbocDecoder for slot's station, playing `program` (0 = MPS).
        While the SDR is being reopened (no source) attach_sdr wires it up."""
        with self._sdr_lock:
            self.stop_iboc(slot)
            st = self.slots[slot]
            dec = IbocDecoder(nrsc5, st.freq_hz - self.center_hz, program)
            self.lock()
            try:
                self.connect(*((self.src,) if self.src else ()), *dec.blocks)
            finally:
                self.unlock()
            st.iboc = dec

    def stop_iboc(self, slot):
        with self._sdr_lock:
            st = self.slots[slot]
            dec = st.iboc if st else None
            if not dec:
                return
            st.iboc = None
            self.lock()
            try:
                self.disconnect(*((self.src,) if self.src else ()), *dec.blocks)
            finally:
                self.unlock()
        dec.stop()

    def recalibrate(self, progress=None):
        """Gain calibration on the running receiver (a few seconds; the
        receivers hear the gain steps). Returns calibrate_gain's report; on
        failure the previous gain is restored and the error raised."""
        tap = IqTap()
        batch = _batch(gr.sizeof_gr_complex, IQ_TAP_BATCH, 4)
        self.lock()
        try:
            self.connect(self.src, batch, tap)
        finally:
            self.unlock()

        def set_gain(lna, ifgr):
            self.src.set_gain(0, 'IFGR', min(max(ifgr, 20), 59))
            self.src.set_gain(0, 'RFGR', min(max(lna, 0), 9))

        try:
            freqs = [st.freq_hz for st in self.stations]
            lna, ifgr, report = calibrate_gain(_Rsp(None, set_gain, tap.grab), self.center_hz, freqs, progress)
        except Exception:
            set_gain(self.lna, self.ifgr)
            raise
        finally:
            self.lock()
            try:
                self.disconnect(self.src, batch, tap)
            finally:
                self.unlock()
        set_gain(lna, ifgr)
        self.lna, self.ifgr, self.gain_auto, self.cal_center_hz = lna, ifgr, True, self.center_hz
        return report

    def detach_sdr(self):
        """Stop the flowgraph and let go of the SDR (before reopening it)."""
        with self._sdr_lock:
            self.stop()
            self.wait()
            if self.src is None:
                return
            for st in self.stations:
                self.disconnect(self.src, st)
                if st.iboc:
                    self.disconnect(self.src, st.iboc.blocks[0])
            self.disconnect(self.src, self._adc_in)
            self.src = None
            gc.collect()  # the source block closes the device when it goes

    def attach_sdr(self):
        """Open the SDR again, wire it to the receivers and start. Raises if it can't be opened."""
        src = self._source_factory() if self._source_factory else make_rsp1a(self.center_hz, self.lna, self.ifgr)
        src = _min_buffer(src, SRC_BUFFER)
        with self._sdr_lock:
            for st in self.stations:
                self.connect(src, st)
                if st.iboc:
                    self.connect(src, st.iboc.blocks[0])
            self.connect(src, self._adc_in)
            self.src = src
            self.start()

    def stop_all_iboc(self):
        for slot in range(MAX_RECEIVERS):
            self.stop_iboc(slot)

    def remove_receiver(self, slot):
        self.stop_iboc(slot)
        st = self.slots[slot]
        st.set_playing(False)
        self.lock()
        try:
            self._unplug(slot, st)
            self._plug_silence(slot)
            self.slots[slot] = None
        finally:
            self.unlock()
        self._recentre()

    def set_freq(self, slot, freq_hz):
        """Move one receiver to another station; the SDR re-centres so all fit."""
        self._recentre({slot: freq_hz})

    def window_hz(self):
        """The band the receivers' stations can be chosen from (MAX_SPAN around their midpoint)."""
        freqs = [st.freq_hz for st in self.slots if st] or [self.center_hz]
        mid = (min(freqs) + max(freqs)) / 2
        return mid - MAX_SPAN / 2, mid + MAX_SPAN / 2

    def _recentre(self, changes=None):
        freqs = {i: st.freq_hz for i, st in enumerate(self.slots) if st}
        freqs.update(changes or {})
        center = _centre(freqs.values())
        if center != self.center_hz:
            if self.src is not None:  # (while the SDR is being reopened, it opens on the new centre)
                self.src.set_frequency(0, center)
            self.center_hz = center
        for i, f in freqs.items():
            self.slots[i].retune(f, center)
            if self.slots[i].iboc:
                self.slots[i].iboc.set_offset(f - center)

    def _plug(self, slot, st):
        self.connect(self.src, st)
        for ch in range(2):
            self.connect((st, ch), (self._mix[ch], slot))

    def _unplug(self, slot, st):
        self.disconnect(self.src, st)
        for ch in range(2):
            self.disconnect((st, ch), (self._mix[ch], slot))

    def _plug_silence(self, slot):
        for ch in range(2):
            self.connect(self._silence[slot][ch], (self._mix[ch], slot))

    def _unplug_silence(self, slot):
        for ch in range(2):
            self.disconnect(self._silence[slot][ch], (self._mix[ch], slot))


# --------------------------------------------------------------------------- GUI

RED, GREEN, DIM, ACCENT = '#ff6b6b', '#69db7c', '#8c9197', '#8ab4f8'
# High-performance HMI (ISA-101): normal readings are drawn in greys, so that
# amber (abnormal, or not judged) and red (out of limits, alarm) stand out.
NORMAL = '#7b8794'      # a bar or trace in its normal range
TEXT_LIT = '#e3e4e6'    # a flag that is set, a value
# Contrast (WCAG 2.1) on the dark backgrounds #16171a-#222328: text 4.5:1 or more
# (DIM 4.9, muted #9aa0a6 5.9, the rest higher); control outlines 3:1 or more
# (BORDER 3.3); disabled controls (exempt) stay readable at DISABLED 3.3.
BORDER, BORDER_HOVER, DISABLED = '#6f747c', '#9aa0a6', '#6f747c'
LCD = 'background: #0b1a0b; border: 1px solid #1f3a1f; border-radius: 6px;'

APP_QSS = """
QWidget { font-family: "Segoe UI"; font-size: 9pt; }
QToolTip { background: #2b2d31; color: #e0e0e0; border: 1px solid #3c4043; padding: 4px 6px; }
QFrame#row { background: #1e1f22; border: 1px solid #2e3035; border-radius: 6px; }
QFrame#row[selected="true"] { background: #1f232a; border-color: #3d5f8f; }
QFrame#detail { background: #1b1c20; border: 1px solid #3d5f8f; border-radius: 6px; }
QLabel#colHead { color: #8c9197; font-family: Consolas; font-size: 7pt; font-weight: 600; letter-spacing: 1px; }
QComboBox#freq { font-size: 15pt; font-weight: 600; padding: 0 4px; border-color: transparent; background: transparent; }
QComboBox#freq:hover { border-color: %BORDER%; }
QToolButton#rowBtn { padding: 0 4px; border-color: transparent; background: transparent; color: #9aa0a6; }
QToolButton#rowBtn:hover { border-color: %BORDER%; color: #e0e0e0; }
QTabBar#detailTabs::tab { background: transparent; color: #9aa0a6; padding: 2px 10px; border: none;
                          border-radius: 4px; margin-left: 2px; }
QTabBar#detailTabs::tab:selected { background: #2b2d31; color: #e3e4e6; }
QTabBar#detailTabs::tab:hover { color: #e3e4e6; }
QFrame#card { background: #222328; border: 1px solid #2a2c31; border-radius: 8px; }
QLabel#cardTitle { color: #9aa0a6; font-size: 8pt; font-weight: 600; letter-spacing: 1px; }
QLabel#chip { background: #24262b; border: 1px solid #30333a; border-radius: 10px; padding: 3px 10px; color: #c4c7cc; }
QLabel#appTitle { font-size: 15pt; font-weight: 600; color: #e8eaed; padding-right: 8px; }
QPushButton, QToolButton { background: #2b2d31; border: 1px solid %BORDER%; border-radius: 6px; padding: 5px 12px; }
QPushButton:hover, QToolButton:hover { background: #33363c; border-color: %BORDER_HOVER%; }
QPushButton:focus, QToolButton:focus { border: 1px solid #8ab4f8; }
QPushButton:disabled, QToolButton:disabled { color: %DISABLED%; background: #25272b; border-color: #3a3d44; }
QPushButton#help { border-radius: 16px; padding: 0; font-weight: 700; font-size: 11pt; color: #8ab4f8; }
QPushButton#primary { background: #2f6db5; border-color: #3d7fd0; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #3a7cc6; }
QPushButton#primary:focus { border-color: #ffffff; }
QPushButton#primary:disabled { background: #25272b; border-color: #3a3d44; color: %DISABLED%; }
QComboBox { background: #2b2d31; border: 1px solid %BORDER%; border-radius: 6px; padding: 3px 8px; }
QComboBox:hover { border-color: %BORDER_HOVER%; }
QComboBox:focus { border-color: #8ab4f8; }
QComboBox:disabled { color: %DISABLED%; border-color: #3a3d44; }
QComboBox QAbstractItemView { background: #222328; border: 1px solid %BORDER%; selection-background-color: #2f6db5; }
QLineEdit, QSpinBox, QDoubleSpinBox { background: #16171a; border: 1px solid %BORDER%; border-radius: 5px; padding: 3px 6px; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: %BORDER_HOVER%; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #8ab4f8; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: %DISABLED%; border-color: #3a3d44; }
QCheckBox { spacing: 8px; }
QCheckBox:disabled { color: %DISABLED%; }
QCheckBox::indicator, QGroupBox::indicator { width: 14px; height: 14px; border: 2px solid %BORDER_HOVER%;
                                             border-radius: 3px; background: #16171a; }
QCheckBox::indicator:hover, QGroupBox::indicator:hover, QCheckBox::indicator:focus { border-color: #8ab4f8; }
QCheckBox::indicator:checked, QGroupBox::indicator:checked { background: #8ab4f8; border-color: #8ab4f8;
                                                             image: url(%CHECK%); }
QCheckBox::indicator:disabled, QGroupBox::indicator:disabled { border-color: #4a4e56; background: #1c1d21; }
QCheckBox::indicator:checked:disabled { background: #4a4e56; border-color: #4a4e56; }
QRadioButton { spacing: 8px; }
QRadioButton:disabled { color: %DISABLED%; }
QRadioButton::indicator { width: 14px; height: 14px; border: 2px solid %BORDER_HOVER%; border-radius: 9px;
                          background: #16171a; }
QRadioButton::indicator:hover, QRadioButton::indicator:focus { border-color: #8ab4f8; }
QRadioButton::indicator:checked { border-color: #8ab4f8;
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.5, fx: 0.5, fy: 0.5,
                                stop: 0 #8ab4f8, stop: 0.5 #8ab4f8, stop: 0.6 #16171a, stop: 1 #16171a); }
QRadioButton::indicator:disabled { border-color: #4a4e56; }
QPlainTextEdit { background: #16171a; border: none; border-radius: 6px; padding: 4px; color: #c4c7cc;
                 font-family: Consolas; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 22px;
                       border: none; border-left: 1px solid %BORDER%; }
QComboBox::down-arrow { width: 10px; height: 6px; image: url(%ARROW%); }
QGroupBox { border: 1px solid %BORDER%; border-radius: 8px; margin-top: 14px; padding-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #8ab4f8; }
"""


def draw_icon(size):
    """The FM-Modmon-ms icon at `size` px: a blue tile with a broadcast mast sending waves."""
    img = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32_Premultiplied)
    img.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    s = float(size)
    grad = QtGui.QLinearGradient(0, 0, s, s)
    grad.setColorAt(0.0, QtGui.QColor('#4a95ea'))
    grad.setColorAt(1.0, QtGui.QColor('#1d4f91'))
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QtCore.QRectF(0, 0, s, s), 0.22 * s, 0.22 * s)

    white = QtGui.QColor('#ffffff')
    top = QtCore.QPointF(0.5 * s, 0.40 * s)
    pen = QtGui.QPen(white, max(1.2, 0.075 * s), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(QtCore.Qt.NoBrush)
    # mast: an A-frame from the top down to the base, with a cross brace
    p.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(0.34 * s, 0.84 * s), top, QtCore.QPointF(0.66 * s, 0.84 * s)]))
    if size >= 24:
        p.drawLine(QtCore.QPointF(0.415 * s, 0.66 * s), QtCore.QPointF(0.585 * s, 0.66 * s))
    # radio waves either side of the top
    for radius, alpha in ((0.17, 255), (0.29, 190)) if size >= 20 else ((0.22, 255),):
        wave = QtGui.QColor(white)
        wave.setAlpha(alpha)
        pen.setColor(wave)
        p.setPen(pen)
        box = QtCore.QRectF(top.x() - radius * s, top.y() - radius * s, 2 * radius * s, 2 * radius * s)
        p.drawArc(box, -40 * 16, 80 * 16)   # right
        p.drawArc(box, 140 * 16, 80 * 16)   # left
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(white)
    p.drawEllipse(top, max(1.0, 0.06 * s), max(1.0, 0.06 * s))
    p.end()
    return img


def splash_pixmap(scale=1.0):
    """The start-up card: a large logo with the app name under it, room at the
    bottom for the progress message. `scale` is Windows' display scaling
    (logical DPI / 96): text is scaled by Windows, so the card is drawn at the
    same scale to keep the logo in proportion to it."""
    w, h, logo = 360, 330, 180          # at 100% scaling
    pix = QtGui.QPixmap(int(w * scale), int(h * scale))
    pix.fill(QtGui.QColor('#1c1d21'))
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    p.scale(scale, scale)
    p.setPen(QtGui.QColor('#2c2e33'))
    p.drawRect(QtCore.QRectF(0.5, 0.5, w - 1, h - 1))
    p.drawImage(QtCore.QRectF((w - logo) / 2, 30, logo, logo), draw_icon(int(logo * scale)))
    font = QtGui.QFont('Segoe UI')
    font.setPixelSize(34)               # pixels, so the scale above isn't applied twice
    font.setWeight(QtGui.QFont.DemiBold)
    p.setFont(font)
    p.setPen(QtGui.QColor('#e8eaed'))
    p.drawText(QtCore.QRectF(0, 30 + logo + 12, w, 44), QtCore.Qt.AlignCenter, APP_NAME)
    p.end()
    return pix


def app_icon():
    icon = QtGui.QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QtGui.QPixmap.fromImage(draw_icon(size)))
    return icon


def _png(img):
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.WriteOnly)
    img.save(buf, 'PNG')
    return bytes(buf.data())


def ico_bytes(sizes=ICON_SIZES):
    """A Windows .ico holding the icon at each size (PNG-compressed entries)."""
    pngs = [(size, _png(draw_icon(size))) for size in sizes]
    head = struct.pack('<HHH', 0, 1, len(pngs))
    offset, entries, data = 6 + 16 * len(pngs), b'', b''
    for size, png in pngs:
        entries += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return head + entries + data


def install_icon(app):
    """Window/taskbar icon for the app, and fm-modmon-ms.ico (for shortcuts) if it isn't there."""
    try:  # without this Windows groups the app under python.exe and shows Python's icon
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass
    app.setWindowIcon(app_icon())
    if not os.path.exists(ICON_PATH):
        try:
            with open(ICON_PATH, 'wb') as fh:
                fh.write(ico_bytes())
        except OSError as e:
            print(f'could not write {ICON_PATH}: {e}')


def apply_dark_theme(app):
    app.setStyle('Fusion')
    P = QtGui.QPalette
    pal = QtGui.QPalette()
    for role, colour in ((P.Window, '#1e1f22'), (P.WindowText, '#e0e0e0'), (P.Base, '#16171a'),
                         (P.AlternateBase, '#26272b'), (P.Text, '#e0e0e0'), (P.Button, '#2b2d31'),
                         (P.ButtonText, '#e0e0e0'), (P.Highlight, '#2f6db5'),
                         (P.HighlightedText, '#ffffff'), (P.ToolTipBase, '#2b2d31'),
                         (P.ToolTipText, '#e0e0e0'), (P.Link, ACCENT)):
        pal.setColor(role, QtGui.QColor(colour))
    for role in (P.WindowText, P.Text, P.ButtonText):
        pal.setColor(P.Disabled, role, QtGui.QColor(DISABLED))
    pal.setColor(P.Window, QtGui.QColor('#17181b'))
    app.setPalette(pal)
    # Qt stylesheets can't draw the dropdown arrow once its box is styled, so
    # draw one into the session cache and point the stylesheet at it.
    arrow = QtGui.QPixmap(20, 12)
    arrow.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(arrow)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(QtGui.QColor('#9aa0a6'))
    p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(1, 1), QtCore.QPointF(19, 1), QtCore.QPointF(10, 11)]))
    p.end()
    arrow_path = os.path.join(cache_dir(), 'arrow.png')
    arrow.save(arrow_path)
    # ...and the checkbox tick: dark on the blue fill (8.2:1)
    tick = QtGui.QPixmap(28, 28)
    tick.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(tick)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtGui.QPen(QtGui.QColor('#0b1a33'), 4.2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
    p.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(5, 14.5), QtCore.QPointF(11.5, 21), QtCore.QPointF(23, 7)]))
    p.end()
    tick_path = os.path.join(cache_dir(), 'tick.png')
    tick.save(tick_path)
    qss = APP_QSS
    for token, value in (('%ARROW%', arrow_path.replace('\\', '/')), ('%CHECK%', tick_path.replace('\\', '/')),
                         ('%BORDER_HOVER%', BORDER_HOVER), ('%BORDER%', BORDER), ('%DISABLED%', DISABLED)):
        qss = qss.replace(token, value)
    app.setStyleSheet(qss)


def card(title=None, extra=None):
    """An inset card (QFrame#card) with an optional small uppercase title; returns (card, its layout)."""
    frame = QtWidgets.QFrame()
    frame.setObjectName('card')
    box = QtWidgets.QVBoxLayout(frame)
    box.setContentsMargins(10, 6, 10, 8)
    box.setSpacing(3)
    if title:
        head = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(title.upper())
        label.setObjectName('cardTitle')
        head.addWidget(label, 1)
        if extra:
            head.addWidget(extra)
        box.addLayout(head)
    return frame, box


class Meter(QtWidgets.QWidget):
    """A slim labelled level bar: filled from `origin` to the value in the
    colour of the zone the value is in, with tick marks, and the value as text."""

    def __init__(self, name, lo, hi, zones, origin=None, ticks=()):
        super().__init__()
        self.name, self.lo, self.hi, self.zones, self.ticks = name, lo, hi, zones, ticks
        self.origin = lo if origin is None else origin
        self.value, self.text = None, '-'
        self.name_w = None   # set to line several meters' bars up
        self.setMinimumHeight(22)
        self.setMinimumWidth(220)

    def set_value(self, value, text):
        if (value, text) != (self.value, self.text):
            self.value, self.text = value, text
            self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h, val_w = self.width(), self.height(), 78
        name_w = self.name_w or p.fontMetrics().horizontalAdvance(self.name) + 12
        p.setPen(QtGui.QColor('#9aa0a6'))
        p.drawText(QtCore.QRectF(0, 0, name_w, h), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self.name)
        track = QtCore.QRectF(name_w, h / 2 - 4, max(w - name_w - val_w - 8, 10), 8)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor('#2c2e33'))
        p.drawRoundedRect(track, 4, 4)

        def x(v):
            v = min(max(v, self.lo), self.hi)
            return track.left() + track.width() * (v - self.lo) / (self.hi - self.lo)

        if self.value is not None and math.isfinite(self.value):
            colour = next((c for upto, c in self.zones if self.value <= upto), self.zones[-1][1])
            x0, x1 = sorted((x(self.origin), x(self.value)))
            p.setBrush(QtGui.QColor(colour))
            p.drawRoundedRect(QtCore.QRectF(x0, track.top(), max(x1 - x0, 3), track.height()), 4, 4)
        p.setPen(QtGui.QPen(QtGui.QColor('#80868b'), 1))
        for t in self.ticks:
            p.drawLine(QtCore.QPointF(x(t), track.top() - 3), QtCore.QPointF(x(t), track.bottom() + 3))
        font = p.font()
        font.setBold(True)
        p.setFont(font)
        p.setPen(QtGui.QColor('#e8eaed'))
        p.drawText(QtCore.QRectF(w - val_w, 0, val_w, h), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, self.text)


# Widths of a station row's fixed columns (the text column takes the rest); the
# column headings above the rows use the same widths.
ROW_COLS = (('station', 'Station', 250), ('text', 'Text · RT+ · flags', 0),
            ('tapes', 'Now · peak hold · limit ▼', 300), ('trend', 'Trend · 5 min', 176),
            ('alarms', 'Alarms', 150))
TAPE_COLOURS = {None: NORMAL, 'warn': '#f0a35e', 'alarm': RED, 'off': '#5d6167'}


class Tape(QtWidgets.QWidget):
    """A slim labelled bar for the station rows and the detail cards: the value
    from `origin` in its state's colour, the normal range as a band on the
    track, an optional limit notch and (hold=True) a tick at the highest value
    of the last HOLD_S, as on a modulation monitor's peak-hold bar."""
    HOLD_S = 2.0

    def __init__(self, name, lo, hi, band=None, origin=None, hold=False, name_w=34, val_w=92):
        super().__init__()
        self.name, self.lo, self.hi, self.band, self.hold = name, lo, hi, band, hold
        self.origin = lo if origin is None else origin
        self.name_w, self.val_w = name_w, val_w
        self.value, self.text, self.state, self.limit, self.peak = None, '-', None, None, None
        self._peaks = deque()
        self._shown = None
        self.setMinimumHeight(16)
        self.setMinimumWidth(name_w + val_w + 60)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def sizeHint(self):
        return QtCore.QSize(self.name_w + self.val_w + 160, 16)

    def set_value(self, value, text, state=None, limit=None, band=None):
        """value None: nothing to show. state: None (normal) | 'warn' | 'alarm' | 'off' (not judged)."""
        now = time.monotonic()
        if self.hold and value is not None and math.isfinite(value):
            self._peaks.append((now, value))
        while self._peaks and now - self._peaks[0][0] > self.HOLD_S:
            self._peaks.popleft()
        self.peak = max(v for _, v in self._peaks) if self._peaks else None
        if band is not None:
            self.band = band
        self.value, self.text, self.state, self.limit = value, text, state, limit
        shown = (value, text, state, limit, self.peak, self.band)
        if shown != self._shown:
            self._shown = shown
            self.update()

    def clear(self):
        self._peaks.clear()
        self.set_value(None, '-')

    def _x(self, track, v):
        v = min(max(v, self.lo), self.hi)
        return track.left() + track.width() * (v - self.lo) / (self.hi - self.lo)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QtGui.QColor('#9aa0a6'))
        p.drawText(QtCore.QRectF(0, 0, self.name_w, h), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self.name)
        track = QtCore.QRectF(self.name_w, h / 2 - 3.5, max(w - self.name_w - self.val_w - 6, 10), 7)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor('#2a2c31'))
        p.drawRoundedRect(track, 2, 2)
        if self.band:
            a, b = self._x(track, self.band[0]), self._x(track, self.band[1])
            p.setBrush(QtGui.QColor('#30353c'))
            p.drawRect(QtCore.QRectF(a, track.top(), b - a, track.height()))
        colour = QtGui.QColor(TAPE_COLOURS.get(self.state, TAPE_COLOURS[None]))
        if self.value is not None and math.isfinite(self.value):
            x0, x1 = sorted((self._x(track, self.origin), self._x(track, self.value)))
            p.setBrush(colour)
            p.drawRoundedRect(QtCore.QRectF(x0, track.top(), max(x1 - x0, 2), track.height()), 1.5, 1.5)
        if self.origin != self.lo:
            p.setPen(QtGui.QPen(QtGui.QColor('#5d6167'), 1))
            x = self._x(track, self.origin)
            p.drawLine(QtCore.QPointF(x, track.top() - 3), QtCore.QPointF(x, track.bottom() + 3))
        if self.peak is not None:
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor('#e3e4e6'))
            x = self._x(track, self.peak)
            p.drawRect(QtCore.QRectF(x - 1, track.top() - 2, 2, track.height() + 4))
        if self.limit is not None:
            x = self._x(track, self.limit)
            p.setPen(QtGui.QPen(QtGui.QColor(RED), 1))
            p.drawLine(QtCore.QPointF(x, track.top() - 1), QtCore.QPointF(x, track.bottom() + 1))
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(RED))
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x - 3.5, 0), QtCore.QPointF(x + 3.5, 0),
                                           QtCore.QPointF(x, track.top() - 0.5)]))
        font = p.font()
        font.setBold(True)
        p.setFont(font)
        p.setPen(QtGui.QColor('#e3e4e6') if self.state in (None, 'off') else colour)
        p.drawText(QtCore.QRectF(w - self.val_w, 0, self.val_w, h), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
                   self.text)


class FreqCombo(QtWidgets.QComboBox):
    """The station selector as a row's headline: shows only the frequency (the
    list still names each station), and its list is as wide as the names."""

    def paintEvent(self, event):
        p = QtWidgets.QStylePainter(self)
        opt = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(opt)
        freq = self.currentData()
        if freq:
            opt.currentText = f'{freq / 1e6:.1f}'
        p.drawComplexControl(QtWidgets.QStyle.CC_ComboBox, opt)
        p.drawControl(QtWidgets.QStyle.CE_ComboBoxLabel, opt)

    def sizeHint(self):
        return QtCore.QSize(self.fontMetrics().horizontalAdvance('000.0') + 46, super().sizeHint().height())

    minimumSizeHint = sizeHint

    def showPopup(self):
        self.view().setMinimumWidth(self.view().sizeHintForColumn(0) + 24)
        super().showPopup()


class StationRow(QtWidgets.QFrame):
    """A receiver as one line in the main window (StationPanel fills it). A click
    selects the receiver for the detail view; a double click pops its detail out."""

    def __init__(self, on_click=None, on_double=None):
        super().__init__()
        self.setObjectName('row')
        self.on_click, self.on_double = on_click, on_double
        self.setProperty('selected', False)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

    def set_selected(self, on):
        if self.property('selected') != on:
            self.setProperty('selected', on)
            self.style().unpolish(self)
            self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.on_click:
            self.on_click()

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.on_double:
            self.on_double()


class Annunciator(QtWidgets.QWidget):
    """Every alarm as a lamp in a fixed grid, in the same place on every row, like
    a transmitter remote control's annunciator panel. The lamp's look says the
    alarm's state (StationPanel._alarm_states); hover one for what it means."""
    COLS = 4
    SHORT = {'CARRIER': 'CARR', 'SILENCE': 'SIL', 'OVERMOD': 'OVMD', 'PILOT': 'PILOT', 'PILOT_SPEC': 'P.SPEC',
             'SUBCARRIERS': 'SUBS', 'FREQUENCY': 'FREQ', 'RDS': 'RDS', 'PI': 'PI', 'ALERT': 'ALERT', 'DATA': 'DATA'}
    # state: (fill, text, outline or None, hatched)
    LOOK = {'clear': ('#26282d', '#7d838a', None, False),
            'waiting': ('#26282d', '#4f545a', None, False),
            'raised': ('#7a1f26', '#ffe0e0', '#c24a52', False),
            'pending': ('#4a3a1c', '#f0a35e', None, False),
            'suppressed': ('#26282d', '#f0a35e', None, True),
            'off': (None, '#4f545a', '#3a3d44', False)}
    MEANS = {'clear': 'clear', 'waiting': 'not judged yet (just tuned, or no readings)',
             'raised': 'RAISED', 'pending': 'its condition holds; raises once its delay has run',
             'suppressed': 'not judged now: reception not clean enough for the technical rules',
             'off': 'switched off for this receiver (Settings)'}

    def __init__(self):
        super().__init__()
        self.states = {}
        self.notes = {}
        self.setMinimumHeight(50)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setMouseTracking(True)

    def sizeHint(self):
        return QtCore.QSize(150, 50)

    def set_states(self, states, notes=None):
        """states: {alarm: state}; notes: {alarm: extra text for its tooltip}."""
        notes = notes or {}
        if states != self.states or notes != self.notes:
            self.states, self.notes = dict(states), dict(notes)
            self.update()

    def _cells(self):
        rows = (len(ALARM_DEFS) + self.COLS - 1) // self.COLS
        w, h, gap = self.width(), self.height(), 2
        cw, ch = (w - gap * (self.COLS - 1)) / self.COLS, (h - gap * (rows - 1)) / rows
        for i, (name, desc, _) in enumerate(ALARM_DEFS):
            r, c = divmod(i, self.COLS)
            yield name, desc, QtCore.QRectF(c * (cw + gap), r * (ch + gap), cw, ch)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        font = QtGui.QFont('Consolas')
        font.setPointSizeF(7)
        font.setBold(True)
        p.setFont(font)
        for name, _, rect in self._cells():
            fill, text, outline, hatched = self.LOOK[self.states.get(name, 'waiting')]
            p.setPen(QtCore.Qt.NoPen)
            if fill:
                p.setBrush(QtGui.QColor(fill))
                p.drawRoundedRect(rect, 2, 2)
            if hatched:
                p.setBrush(QtGui.QBrush(QtGui.QColor('#5a4424'), QtCore.Qt.BDiagPattern))
                p.drawRoundedRect(rect, 2, 2)
            if outline:
                p.setPen(QtGui.QPen(QtGui.QColor(outline), 1, QtCore.Qt.SolidLine if fill else QtCore.Qt.DashLine))
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)
            p.setPen(QtGui.QColor(text))
            p.drawText(rect, QtCore.Qt.AlignCenter, self.SHORT[name])

    def event(self, event):
        if event.type() == QtCore.QEvent.ToolTip:
            for name, desc, rect in self._cells():
                if rect.contains(QtCore.QPointF(event.pos())):
                    state = self.states.get(name, 'waiting')
                    tip = f'<b>{self.SHORT[name]}</b>: {desc}<br>{self.MEANS[state]}'
                    if self.notes.get(name):
                        tip += f'<br>{_html(self.notes[name])}'
                    QtWidgets.QToolTip.showText(event.globalPos(), tip, self, rect.toRect())
                    return True
            QtWidgets.QToolTip.hideText()
            return True
        return super().event(event)


def bucket(t, v, span, n, peak=True, end=None):
    """Readings (times t, values v) over the last `span` seconds into n equal
    buckets, oldest first: each bucket's maximum (peak) or mean; NaN where empty."""
    out = np.full(n, np.nan)
    if not len(t):
        return out
    end = t[-1] if end is None else end
    keep = (t > end - span) & np.isfinite(v)
    t, v = t[keep], v[keep]
    if not len(t):
        return out
    i = np.clip(((t - (end - span)) / span * n).astype(int), 0, n - 1)
    if peak:
        np.fmax.at(out, i, v)
    else:
        sums, counts = np.zeros(n), np.zeros(n)
        np.add.at(sums, i, v)
        np.add.at(counts, i, 1)
        with np.errstate(invalid='ignore'):
            out = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
    return out


class Spark(QtWidgets.QWidget):
    """A word-sized trend (Tufte's sparkline): the last few minutes of one reading
    as a filled line on a fixed scale, a dashed limit with the excursions over it
    filled red, a dotted reference line, and a dot on the newest value."""

    def __init__(self, lo, hi, limit=None, ref=None, height=26):
        super().__init__()
        self.lo, self.hi, self.limit, self.ref = lo, hi, limit, ref
        self.data = np.array([])
        self.excess = RED
        self.setFixedHeight(height)
        self.setMinimumWidth(80)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def set_data(self, values, limit=None, excess=RED):
        """values: bucketed readings, oldest first (NaN: no reading); excess: the
        colour of excursions over the limit (amber while the limit isn't judged)."""
        self.data = np.asarray(values, dtype=float)
        self.excess = excess
        self.limit = limit if limit is not None else self.limit
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QtGui.QColor('#1a1b1f'))
        n = len(self.data)

        def y(v):
            v = min(max(v, self.lo), self.hi)
            return h - 2 - (h - 4) * (v - self.lo) / (self.hi - self.lo)

        def x(i):
            return 1 + i * (w - 2) / max(n - 1, 1)

        if self.ref is not None:
            p.setPen(QtGui.QPen(QtGui.QColor('#5d6167'), 1, QtCore.Qt.DotLine))
            p.drawLine(QtCore.QPointF(0, y(self.ref)), QtCore.QPointF(w, y(self.ref)))
        if n:
            ok = np.isfinite(self.data)
            # one filled run per stretch of readings (a gap stays a gap)
            runs, start = [], None
            for i in range(n + 1):
                if i < n and ok[i]:
                    start = i if start is None else start
                elif start is not None:
                    runs.append((start, i))
                    start = None
            colour = QtGui.QColor(TAPE_COLOURS[None])
            for a, b in runs:
                pts = [QtCore.QPointF(x(i), y(self.data[i])) for i in range(a, b)]
                fill = QtGui.QPolygonF([QtCore.QPointF(x(a), h - 2)] + pts + [QtCore.QPointF(x(b - 1), h - 2)])
                c = QtGui.QColor(colour)
                c.setAlpha(45)
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(c)
                p.drawPolygon(fill)
                p.setPen(QtGui.QPen(colour, 1.1))
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawPolyline(QtGui.QPolygonF(pts))
            if self.limit is not None:
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(QtGui.QColor(self.excess))
                for i in np.nonzero(ok & (self.data > self.limit))[0]:
                    p.drawRect(QtCore.QRectF(x(i) - 0.8, y(self.data[i]), 1.8, y(self.limit) - y(self.data[i])))
            last = np.nonzero(ok)[0]
            if len(last):
                p.setBrush(QtGui.QColor('#e3e4e6'))
                p.drawEllipse(QtCore.QPointF(x(last[-1]), y(self.data[last[-1]])), 2, 2)
        if self.limit is not None:
            p.setPen(QtGui.QPen(QtGui.QColor(RED), 1, QtCore.Qt.DashLine))
            p.drawLine(QtCore.QPointF(0, y(self.limit)), QtCore.QPointF(w, y(self.limit)))


class PeakHistogram(QtWidgets.QWidget):
    """How peak modulation spreads: the share of updates (10 a second) at each
    peak level over the last few minutes, log height, in 2% bins. A tight peak
    just under the limit is a processed station; a tail past it, overshoot that a
    per-minute count flattens (the SOFIA 568's program-dynamics histogram)."""
    LO, HI, STEP = 60, 130, 2

    def __init__(self):
        super().__init__()
        self.counts, self.limit = None, None
        self.setFixedHeight(64)
        self.setMinimumWidth(160)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def set_data(self, peaks, limit):
        peaks = np.asarray(peaks, dtype=float)
        peaks = peaks[np.isfinite(peaks)]
        edges = np.arange(self.LO, self.HI + self.STEP, self.STEP)
        self.counts = np.histogram(np.clip(peaks, self.LO, self.HI - 1e-6), edges)[0] if len(peaks) else None
        self.limit = limit
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        fm_ = p.fontMetrics()
        axis = fm_.height()
        top, bottom = 2, h - axis - 1
        n = (self.HI - self.LO) // self.STEP

        def x(pct):
            return w * (pct - self.LO) / (self.HI - self.LO)

        p.fillRect(QtCore.QRectF(0, top, w, bottom - top), QtGui.QColor('#1a1b1f'))
        p.setPen(QtGui.QColor('#9aa0a6'))
        for pct in range(self.LO, self.HI, 10):
            left_ = pct == self.LO
            p.drawText(QtCore.QRectF(x(pct) - (0 if left_ else 20), bottom + 1, 40, axis),
                       QtCore.Qt.AlignLeft if left_ else QtCore.Qt.AlignHCenter, f'{pct}%' if pct % 20 == 0 else str(pct))
        if self.counts is not None and self.counts.max() > 0:
            top_log = math.log1p(self.counts.max())
            bw = w / n
            p.setPen(QtCore.Qt.NoPen)
            for i, c in enumerate(self.counts):
                if not c:
                    continue
                lo = self.LO + i * self.STEP
                colour = RED if self.limit is not None and lo >= self.limit else AMBER if lo >= 100 else TAPE_COLOURS[None]
                bh = (bottom - top) * math.log1p(c) / top_log
                p.setBrush(QtGui.QColor(colour))
                p.drawRect(QtCore.QRectF(i * bw + 0.5, bottom - bh, bw - 1, bh))
        if self.limit is not None:
            p.setPen(QtGui.QPen(QtGui.QColor(RED), 1, QtCore.Qt.DashLine))
            p.drawLine(QtCore.QPointF(x(self.limit), top), QtCore.QPointF(x(self.limit), bottom))


def alarm_episodes(log, end):
    """The alarm log's raise/clear pairs as [(name, start, stop or None while raised)]."""
    out, open_ = [], {}
    for t, name, raised in log:
        if raised:
            open_.setdefault(name, t)
        elif name in open_:
            out.append((name, open_.pop(name), t))
    out += [(name, t, None) for name, t in open_.items()]
    return sorted(out, key=lambda e: e[1])


def duration_text(seconds):
    s = int(max(seconds, 0))
    if s < 60:
        return f'{s} s'
    if s < 3600:
        return f'{s // 60} min {s % 60:02d} s'
    return f'{s // 3600} h {s % 3600 // 60:02d} min'


class HistoryStrips(QtWidgets.QWidget):
    """A receiver's readings over one time span as stacked strips on one time
    axis, with the alarm episodes underneath, and one cursor (follows the mouse)
    that reads every strip at the same instant, as on the Inovonics 541's
    history plots. Peak readings show each pixel's maximum, the rest its mean."""
    # title, unit, history keys, low, high, peak?, reference line
    STRIPS = (('Peak modulation', '%', ('pos_pct', 'neg_pct'), 0, 130, True, 100),
              ('RF level', 'dBFS', ('rf_dbfs',), -90, -10, False, None),
              ('MPX S/N', 'dB', ('snr_db',), 0, 70, False, None),
              ('AM / multipath', '%', ('am_pct',), 0, 40, True, PEAK_AM_PCT),
              ('Pilot', '%', ('pilot_pct',), 0, 12, False, None),
              ('RDS groups', '/s', ('rds_rate',), 0, 12, False, None),
              ('Loudness S', 'LUFS', ('short_term',), -40, 0, False, -23),
              ('MPX power', 'dBr', ('mpx_dbr',), -12, 6, False, 0))
    STRIP_H, LABEL_W, ALARM_H = 34, 150, 22

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.span = 300
        self.cursor_x = None
        self._data = None      # (end time, [(strip values)], episodes)
        self.setMouseTracking(True)
        self.setMinimumHeight(len(self.STRIPS) * self.STRIP_H + self.ALARM_H + 22)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def refresh(self):
        h = self.panel.history
        end = time.time()
        # one point per pixel, but no finer than the readings (a gap would break the line)
        rate = UPDATE_HZ if self.span <= History.FAST_S else 1
        n = min(max(self.width() - self.LABEL_W - 8, 50), int(self.span * rate))
        strips = []
        for _, _, keys, *_rest in self.STRIPS:
            peak = _rest[2]
            rows = [bucket(*h.series(k, self.span), self.span, n, peak, end) for k in keys]
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                strips.append(np.nanmax(rows, axis=0) if len(rows) > 1 else rows[0])
        self._data = (end, strips, alarm_episodes(h.alarm_log, end))
        self.update()

    def mouseMoveEvent(self, event):
        self.cursor_x = event.pos().x() if event.pos().x() >= self.LABEL_W else None
        self.update()

    def leaveEvent(self, event):
        self.cursor_x = None
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w = self.width()
        left, right = self.LABEL_W, w - 8
        fm_ = p.fontMetrics()
        if not self._data:
            return
        end, strips, episodes = self._data
        n = len(strips[0])
        at = None
        if self.cursor_x is not None and right > left:
            at = int(min(max((self.cursor_x - left) / (right - left) * n, 0), n - 1))
        for k, ((title, unit, _, lo, hi, _, ref), values) in enumerate(zip(self.STRIPS, strips)):
            top = k * self.STRIP_H
            box = QtCore.QRectF(left, top + 2, right - left, self.STRIP_H - 4)
            p.fillRect(box, QtGui.QColor('#141518'))

            def y(v):
                v = min(max(v, lo), hi)
                return box.bottom() - box.height() * (v - lo) / (hi - lo)

            limit = self.panel.readings.get('limit_pct') if title == 'Peak modulation' else None
            for line, style in ((ref, QtCore.Qt.DotLine), (limit, QtCore.Qt.DashLine)):
                if line is not None:
                    p.setPen(QtGui.QPen(QtGui.QColor(RED if style == QtCore.Qt.DashLine else '#5d6167'), 1, style))
                    p.drawLine(QtCore.QPointF(left, y(line)), QtCore.QPointF(right, y(line)))
            p.setPen(QtGui.QPen(QtGui.QColor(TAPE_COLOURS[None]), 1.1))
            pts, last = [], None
            gap = max(2, 2 * n / self.span)   # buckets: a gap over 2 s breaks the line
            for i in np.nonzero(np.isfinite(values))[0]:
                if last is not None and i - last > gap:
                    p.drawPolyline(QtGui.QPolygonF(pts))
                    pts = []
                pts.append(QtCore.QPointF(left + (right - left) * (i + 0.5) / n, y(values[i])))
                last = i
            if len(pts) > 1:
                p.drawPolyline(QtGui.QPolygonF(pts))
            if limit is not None:
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(QtGui.QColor(RED))
                for i in np.nonzero(np.isfinite(values) & (values > limit))[0]:
                    x = left + (right - left) * (i + 0.5) / n
                    p.drawRect(QtCore.QRectF(x - 0.7, y(values[i]), 1.6, y(limit) - y(values[i])))
            if at is not None:   # the reading nearest the cursor
                near = [values[i] for i in range(max(at - 2, 0), min(at + 3, n)) if math.isfinite(values[i])]
                shown = near[len(near) // 2] if near else math.nan
            else:
                shown = next((v for v in values[::-1] if math.isfinite(v)), math.nan)
            p.setPen(QtGui.QColor('#9aa0a6'))
            p.drawText(QtCore.QRectF(4, top, left - 10, self.STRIP_H / 2 + 2), QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom,
                       title)
            p.setPen(QtGui.QColor('#e3e4e6'))
            p.drawText(QtCore.QRectF(4, top + self.STRIP_H / 2, left - 10, self.STRIP_H / 2),
                       QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop,
                       f'{shown:.1f} {unit}' if math.isfinite(shown) else '-')
        # alarm episodes, on the same time axis
        top = len(self.STRIPS) * self.STRIP_H
        box = QtCore.QRectF(left, top + 2, right - left, self.ALARM_H - 4)
        p.fillRect(box, QtGui.QColor('#141518'))
        start = end - self.span

        def tx(t):
            return left + (right - left) * (t - start) / self.span

        active_at = []
        t_at = start + (at + 0.5) / n * self.span if at is not None else None
        p.setPen(QtCore.Qt.NoPen)
        for name, a, b in episodes:
            b_ = end if b is None else b
            if b_ < start:
                continue
            x0, x1 = tx(max(a, start)), tx(b_)
            p.setBrush(QtGui.QColor(RED))
            p.drawRect(QtCore.QRectF(x0, box.top(), max(x1 - x0, 2), box.height()))
            if x1 - x0 > fm_.horizontalAdvance(Annunciator.SHORT[name]) + 6:
                p.setPen(QtGui.QColor('#ffe0e0'))
                p.drawText(QtCore.QRectF(x0, box.top(), x1 - x0, box.height()), QtCore.Qt.AlignCenter,
                           Annunciator.SHORT[name])
                p.setPen(QtCore.Qt.NoPen)
            if t_at is not None and a <= t_at <= b_:
                active_at.append(Annunciator.SHORT[name])
        p.setPen(QtGui.QColor('#9aa0a6'))
        p.drawText(QtCore.QRectF(4, top, left - 10, self.ALARM_H), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                   'Alarms' + (f': {", ".join(active_at)}' if active_at else ''))
        # time axis and the cursor
        axis_top = top + self.ALARM_H
        for frac in (0, 0.25, 0.5, 0.75, 1):
            x = left + (right - left) * frac
            ago = self.span * (1 - frac)
            text = 'now' if not ago else (f'−{ago / 60:g} min' if ago >= 60 else f'−{ago:g} s')
            align = QtCore.Qt.AlignLeft if frac == 0 else QtCore.Qt.AlignRight if frac == 1 else QtCore.Qt.AlignHCenter
            rect = QtCore.QRectF(x - (0 if frac == 0 else 60 if frac == 1 else 30), axis_top + 2, 60, fm_.height())
            p.drawText(rect, align, text)
        if t_at is not None:
            x = left + (right - left) * (at + 0.5) / n
            p.setPen(QtGui.QPen(QtGui.QColor('#e3e4e6'), 1))
            p.drawLine(QtCore.QPointF(x, 0), QtCore.QPointF(x, axis_top))
            p.drawText(QtCore.QRectF(x + 4, axis_top + 2, 120, fm_.height()), QtCore.Qt.AlignLeft,
                       time.strftime('%H:%M:%S', time.localtime(t_at)))


class HistoryView(QtWidgets.QWidget):
    """The detail view's History tab: a span to look back over and the strips."""
    SPANS = (('1 min', 60), ('5 min', 300), ('1 hour', 3600))

    def __init__(self, panel):
        super().__init__()
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        head = QtWidgets.QHBoxLayout()
        self.span = QtWidgets.QComboBox()
        for label, seconds in self.SPANS:
            self.span.addItem(label, seconds)
        self.span.setCurrentIndex(1)
        self.span.activated.connect(lambda i: self._set_span(self.span.itemData(i)))
        note = QtWidgets.QLabel('Hover to read every strip at one moment. Up to 5 min: every update; '
                                'beyond: one point a second (peaks: its highest). Alarms: the last 24 h.')
        note.setStyleSheet('color: #8c9197;')
        head.addWidget(QtWidgets.QLabel('Span'))
        head.addWidget(self.span)
        head.addWidget(note, 1)
        box.addLayout(head)
        self.strips = HistoryStrips(panel)
        box.addWidget(self.strips)
        box.addStretch(1)

    def _set_span(self, seconds):
        self.strips.span = seconds
        self.strips.refresh()

    def refresh(self):
        self.strips.refresh()


class AlarmTable(QtWidgets.QTableWidget):
    """The alarms of this session, one row per alarm (raised to cleared) with how
    long it lasted, newest first; the ones still raised in red, their time running."""
    COLS = ('Raised', 'Station', 'Alarm', 'Duration', 'Cleared', 'Measured')

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().hide()
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setShowGrid(False)
        self.setWordWrap(False)
        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        for i, w in enumerate((130, 120, 200, 100, 70)):
            self.setColumnWidth(i, w)
        self.verticalHeader().setDefaultSectionSize(20)
        self.episodes = []   # {'key', 'station', 'desc', 'start', 'end' (None while raised), 'detail'}

    def raised(self, key, station, desc, detail, t=None):
        """key: which receiver and station (its title can change while the alarm is up)."""
        self.episodes.append({'key': key, 'station': station, 'desc': desc, 'start': t or time.time(), 'end': None,
                              'detail': detail})
        self.episodes = self.episodes[-500:]
        self.redraw()

    def cleared(self, key, desc, t=None):
        for e in reversed(self.episodes):
            if e['key'] == key and e['desc'] == desc and e['end'] is None:
                e['end'] = t or time.time()
                break
        self.redraw()

    def raised_now(self):
        return sum(e['end'] is None for e in self.episodes)

    def redraw(self):
        """Fill the table (and keep the running durations going): call once a second."""
        now = time.time()
        rows = list(reversed(self.episodes))
        if self.rowCount() != len(rows):
            self.setRowCount(len(rows))
        for r, e in enumerate(rows):
            on = e['end'] is None
            cells = (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e['start'])), e['station'], e['desc'],
                     duration_text((now if on else e['end']) - e['start']) + (' …' if on else ''),
                     'raised' if on else time.strftime('%H:%M:%S', time.localtime(e['end'])), e['detail'])
            for c, text in enumerate(cells):
                item = self.item(r, c)
                if item is None:
                    item = QtWidgets.QTableWidgetItem()
                    self.setItem(r, c, item)
                if item.text() != text:
                    item.setText(text)
                    item.setToolTip(text)
                item.setForeground(QtGui.QColor(RED if on else '#c4c7cc'))


def column_heads():
    """The headings over the station rows, at the rows' column widths."""
    head = QtWidgets.QWidget()
    box = QtWidgets.QHBoxLayout(head)
    box.setContentsMargins(11, 0, 11, 0)
    box.setSpacing(12)
    for _, title, width in ROW_COLS:
        label = QtWidgets.QLabel(title.upper())
        label.setObjectName('colHead')
        if width:
            label.setFixedWidth(width)
            box.addWidget(label)
        else:
            box.addWidget(label, 1)
    box.addSpacing(30)   # the row's settings / remove buttons
    return head


RDS_FLAGS =('TP', 'TA', 'music', 'stereo', 'AH', 'CMP')  # gr-rds flag string order (then static PTY)


def rds_flags(f):
    """gr-rds flag string ('1'/'0' for TP, TA, Music, Stereo(DI), AH, Compressed,
    static PTY) as {name: bool}, or None until a full one is decoded."""
    if len(f) < 7:
        return None
    return {name: f[i] == '1' for i, name in enumerate(RDS_FLAGS)}


def _flags_html(flags):
    """rds_flags() for a rich-text label."""
    if flags is None:
        return '-'

    def lit(name, on):
        return f'<b style="color:{TEXT_LIT}">{name}</b>' if on else f'<span style="color:{DIM}">{name}</span>'

    return ' '.join([
        lit('TP', flags['TP']), lit('TA', flags['TA']),
        '<b>Music</b>' if flags['music'] else '<b>Speech</b>',
        lit('DI-Stereo', flags['stereo']), lit('AH', flags['AH']), lit('CMP', flags['CMP']),
    ])


def _html(text):
    """Station-supplied text, safe to put in a rich-text label."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _num(v, unit, fmt='.1f'):
    return f'{v:{fmt}} {unit}' if math.isfinite(v) else f'-∞ {unit}'


def _fits(freqs):
    return max(freqs) - min(freqs) <= MAX_SPAN + 1


class MpxSpectrum(QtWidgets.QWidget):
    """Demodulated MPX spectrum, 0-100 kHz, 0 to -70 dB, with markers for the
    19 kHz pilot, the 38 kHz stereo subcarrier and 57 kHz RDS."""

    TOP, BOTTOM, MAX_KHZ = 0.0, -70.0, 100.0
    MARKERS = ((19, 'pilot', '#9aa0a6'), (38, '38k', '#6d737a'), (57, 'RDS', '#9aa0a6'),
               (67, 'SCA', '#6d737a'), (92, 'SCA', '#6d737a'))

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self._db = None

    def set_data(self, mpx_db):
        self._db = mpx_db
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        fm_ = p.fontMetrics()
        left, right = fm_.horizontalAdvance('-70 dB') + 8, self.width() - fm_.horizontalAdvance('100') // 2 - 6
        top, bottom = 6, self.height() - fm_.height() - 6
        p.fillRect(self.rect(), QtGui.QColor('#16171a'))

        def x(khz):
            return left + (right - left) * khz / self.MAX_KHZ

        def y(db):
            db = min(max(db, self.BOTTOM), self.TOP)
            return top + (bottom - top) * (self.TOP - db) / (self.TOP - self.BOTTOM)

        # grid and axis labels
        p.setPen(QtGui.QColor('#3c4043'))
        for db in range(0, -71, -10):
            p.drawLine(QtCore.QPointF(left, y(db)), QtCore.QPointF(right, y(db)))
        p.setPen(QtGui.QColor('#9aa0a6'))
        for db in range(0, -71, -10):
            p.drawText(QtCore.QRectF(0, y(db) - 8, left - 6, 16),
                       QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter, f'{db} dB')
        for khz in range(0, 101, 10):
            p.drawText(QtCore.QRectF(x(khz) - 20, bottom + 2, 40, fm_.height()),
                       QtCore.Qt.AlignHCenter, str(khz))

        if self._db is not None:
            khz = (np.arange(len(self._db)) + 1) * 0.5
            pts = [QtCore.QPointF(x(k), y(d)) for k, d in zip(khz.tolist(), self._db.tolist())]
            trace = QtGui.QPolygonF([QtCore.QPointF(x(0), y(self._db[0]))] + pts)
            fill = QtGui.QPolygonF(trace)
            fill.append(QtCore.QPointF(x(khz[-1]), bottom))
            fill.append(QtCore.QPointF(x(0), bottom))
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(159, 176, 191, 50))
            p.drawPolygon(fill)
            p.setPen(QtGui.QPen(QtGui.QColor('#9fb0bf'), 1.1))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawPolyline(trace)

        # subcarrier markers
        for khz_, label, colour in self.MARKERS:
            p.setPen(QtGui.QPen(QtGui.QColor(colour), 1, QtCore.Qt.DotLine))
            p.drawLine(QtCore.QPointF(x(khz_), top), QtCore.QPointF(x(khz_), bottom))
            p.drawText(QtCore.QPointF(x(khz_) + 4, top + fm_.ascent()), label)


class Goniometer(QtWidgets.QWidget):
    """L/R vectorscope: mono is a vertical line, wide stereo a fuzzy ball,
    out-of-phase content leans horizontal. Auto-scaled to fill the box.
    The small one (size px) draws the last `points` samples of each update;
    the large one (size None, resizable) keeps `history` updates, older ones
    fading, like a scope's afterglow. on_click: called when clicked."""

    def __init__(self, size=130, history=1, points=400):
        super().__init__()
        if size:
            self.setFixedSize(size, size)
        self._frames = deque(maxlen=history)
        self._points = points
        self.on_click = None

    def set_data(self, lr):
        if lr is None:
            self._frames.clear()
        else:
            self._frames.append(lr)
        self.update()

    def mouseReleaseEvent(self, event):
        if self.on_click and event.button() == QtCore.Qt.LeftButton:
            self.on_click()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor('#0b1a0b'))
        w = min(self.width(), self.height())
        x0, y0 = (self.width() - w) / 2, (self.height() - w) / 2
        c = w / 2
        big = w > 200
        p.setPen(QtGui.QPen(QtGui.QColor('#2a4a2a'), 1, QtCore.Qt.DotLine))
        for a, b in (((c, 0), (c, w)), ((0, c), (w, c)), ((0, 0), (w, w)), ((w, 0), (0, w))):
            p.drawLine(QtCore.QPointF(x0 + a[0], y0 + a[1]), QtCore.QPointF(x0 + b[0], y0 + b[1]))
        if big:
            p.drawEllipse(QtCore.QPointF(x0 + c, y0 + c), 0.45 * w, 0.45 * w)
            font = p.font()
            font.setPointSizeF(font.pointSizeF() * 1.3)
            p.setFont(font)
        p.setPen(QtGui.QColor('#6a8f6a'))
        pad = 8 if big else 4
        top = pad + p.fontMetrics().ascent()
        p.drawText(QtCore.QPointF(x0 + pad, y0 + top), 'L')
        p.drawText(QtCore.QPointF(x0 + w - pad - p.fontMetrics().horizontalAdvance('R'), y0 + top), 'R')
        p.drawText(QtCore.QPointF(x0 + c + 4, y0 + top), 'M')
        if big:
            p.drawText(QtCore.QPointF(x0 + pad, y0 + c - 4), '\u2212S')
            p.drawText(QtCore.QPointF(x0 + w - pad - p.fontMetrics().horizontalAdvance('+S'), y0 + c - 4), '+S')
        if not self._frames:
            return
        frames = []
        for l, r in self._frames:
            l = l[-self._points:] if self._points else l
            r = r[-self._points:] if self._points else r
            l, r = l.astype(np.float64), r.astype(np.float64)
            frames.append(((l + r) / math.sqrt(2), (r - l) / math.sqrt(2)))
        peak = max(max(np.max(np.abs(m)), np.max(np.abs(sd))) for m, sd in frames)
        k = 0.45 * w / max(peak, 1e-4)
        n = len(frames)
        for i, (mid, side) in enumerate(frames):  # oldest first, faintest
            colour = QtGui.QColor('#66ff66')
            colour.setAlphaF(0.25 + 0.75 * (i + 1) / n if n > 1 else 1.0)
            p.setPen(QtGui.QPen(colour, 1.6 if big else 1.0))
            xs, ys = (x0 + c + side * k).tolist(), (y0 + c - mid * k).tolist()
            p.drawPoints(QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in zip(xs, ys)]))


class StereoWindow(QtWidgets.QDialog):
    """A receiver's stereo image, large and live: goniometer with afterglow,
    phase-correlation bar and the stereo readouts. Opened by clicking the
    panel's goniometer; follows the panel until closed."""

    READOUTS = ('Correlation', 'Balance', 'Width (S/M)', 'Level L/R')

    def __init__(self, panel, parent):
        super().__init__(parent)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.resize(560, 660)
        layout = QtWidgets.QVBoxLayout(self)
        self.scope = Goniometer(size=None, history=8, points=None)
        self.scope.setMinimumSize(300, 300)
        layout.addWidget(self.scope, 1)
        self.phase = Meter('Phase', -1, 1, [(-0.0001, RED), (1, NORMAL)], origin=0, ticks=(0,))
        layout.addWidget(self.phase)
        self.readouts = QtWidgets.QLabel('')
        self.readouts.setAlignment(QtCore.Qt.AlignCenter)
        self.readouts.setStyleSheet('color: #9aa0a6; padding: 4px;')
        layout.addWidget(self.readouts)

    def follow(self, panel):
        st = panel.station
        self.setWindowTitle(f'{panel.title} \u2013 stereo image')
        self.scope.set_data(st.audio_meter.scope)
        corr = (st.audio_meter.stats or {}).get('correlation')
        self.phase.set_value(corr, '-' if corr is None else f'{corr:+.2f}')
        self.readouts.setText('   \u00b7   '.join(
            f'{n}: <b style="color:#e0e0e0">{QtGui.QTextDocumentFragment.fromHtml(panel.values[n].text()).toPlainText()}</b>'
            for n in self.READOUTS))


AMBER = '#f0a35e'
IMG_PX = 88        # station logo / album art on the panel
IMG_TIP_PX = 320   # and in their tooltips

# Alarm name, description, seconds the condition must hold before it raises or
# clears (SILENCE's is a receiver setting).
ALARM_DEFS = (
    ('CARRIER', 'carrier low or lost', 5),
    ('SILENCE', 'audio silence', 10),
    ('OVERMOD', 'over-modulation', 3),
    ('PILOT', 'stereo pilot lost', 5),
    ('PILOT_SPEC', 'stereo pilot out of tolerance', 10),
    ('SUBCARRIERS', 'subcarrier injection over the limit', 10),
    ('FREQUENCY', 'carrier frequency out of tolerance', 30),
    ('RDS', 'RDS lost', 10),
    ('BACKUP', 'possibly on N+1 (backup transmitter has no RDS)', 10),
    ('PI', 'wrong station (PI differs from expected)', 5),
    ('ALERT', 'emergency alert (IBOC or RT+ Alarm)', 0),  # IBOC: only while an IBOC programme is playing
    ('DATA', 'data service lost (paging, EWS, ODA or SCA data)', 60),
)

# FM technical rules the alarms check, per rule set. FCC: 47 CFR 73.1570(b)(2)
# (modulation), 73.322 (pilot), 73.319(d)(2) (subcarriers), 73.1545(b) (frequency).
# ISED: BETS-6 issue 3 A.2.2.2, A.2.2.4, 7.2.3 and BPR-3 issue 7 3.13.2 (the
# modulation, pilot and subcarrier limits match the FCC's; BPR-1 sets no
# numeric in-service frequency tolerance, so BETS-6's transmitter stability is used).
# The limits, each adjustable per receiver: (setting, label, unit, low, high, step).
LIMITS = (
    ('mod_base_pct', 'over-modulation base', '%', 50, 150, 0.5),
    ('mod_per_sub', 'subcarrier allowance (x injection)', '', 0, 2, 0.05),
    ('mod_max_pct', 'over-modulation maximum', '%', 50, 150, 0.5),
    ('pilot_min_pct', 'pilot minimum', '%', 0, 20, 0.1),
    ('pilot_max_pct', 'pilot maximum', '%', 0, 20, 0.1),
    ('pilot_tol_hz', 'pilot frequency tolerance', 'Hz', 0.1, 50, 0.1),
    ('sub_total_pct', 'subcarrier total', '%', 0, 50, 0.5),
    ('sub_high_pct', 'subcarriers above 75 kHz', '%', 0, 50, 0.5),
    ('freq_tol_hz', 'carrier frequency tolerance', 'Hz', 100, 10000, 100),
)
_COMMON = {'mod_base_pct': 100.0, 'mod_per_sub': 0.5, 'mod_max_pct': 110.0,
           'pilot_min_pct': 8.0, 'pilot_max_pct': 10.0, 'pilot_tol_hz': 2.0,
           'sub_total_pct': 20.0, 'sub_high_pct': 10.0}
RULES = {
    'fcc': {'name': 'FCC (47 CFR 73)', 'limits': {**_COMMON, 'freq_tol_hz': 2000.0}},
    'ised': {'name': 'ISED (BETS-6, BPR-3)', 'limits': {**_COMMON, 'freq_tol_hz': 1000.0}},
}


@dataclass
class ReceiverSettings:
    """One receiver's settings; saved with it in fm-modmon-ms_config.json."""
    name: str = ''
    deemphasis_us: int = 75          # 75 (Americas, Korea) or 50 (Europe, most elsewhere)
    stereo: str = 'auto'             # 'auto' or 'mono'
    volume_pct: int = 100            # play volume
    pty_names: str = 'rbds'          # 'rbds' (North America) or 'rds'
    expected_pi: str = ''            # 4 hex digits; the PI alarm compares with it
    service_names: str = ''          # names for data services, e.g. '7A=Alert FM' (parse_service_names)
    rds_feed: bool = True            # serve raw RDS groups over TCP
    rds_port: int = 0                # 0: the default, --rds-port + receiver number - 1
    audio_source: str = 'analog'     # an AUDIO_SOURCES key
    alarms: dict = field(default_factory=lambda: {name: True for name, *_ in ALARM_DEFS})
    silence_lufs: float = -45.0      # momentary loudness below this is silence
    silence_s: int = 10              # for this long
    min_snr_db: float = 15.0         # MPX S/N below this (or RF < -75 dBFS) is carrier low
    rules: str = ''                  # 'ised', 'fcc', 'custom', or '' = by --country (ISED for CA, else FCC)
    # the limits the alarms use with rules 'custom' (with a preset, the preset's)
    mod_base_pct: float = 100.0      # over-modulation above base + per_sub x subcarrier injection, at most max
    mod_per_sub: float = 0.5
    mod_max_pct: float = 110.0
    pilot_min_pct: float = 8.0       # stereo pilot injection range...
    pilot_max_pct: float = 10.0
    pilot_tol_hz: float = 2.0        # ...and frequency tolerance around 19 kHz
    sub_total_pct: float = 20.0      # all subcarriers together
    sub_high_pct: float = 10.0       # subcarriers above 75 kHz
    freq_tol_hz: float = 2000.0      # carrier frequency

    @classmethod
    def from_dict(cls, d):
        """Settings from a saved dict: unknown keys ignored, bad values back to defaults."""
        known = {f.name for f in fields(cls)}
        d = dict(d or {})
        if 'overmod_pct' in d and 'mod_base_pct' not in d and d.get('rules') == 'custom':
            # an earlier version's single custom limit: a fixed limit, no subcarrier allowance
            d.update(mod_base_pct=d['overmod_pct'], mod_per_sub=0.0, mod_max_pct=d['overmod_pct'])
        out = cls(**{k: v for k, v in d.items() if k in known})
        default = cls()
        if out.deemphasis_us not in (50, 75):
            out.deemphasis_us = default.deemphasis_us
        if out.stereo not in ('auto', 'mono'):
            out.stereo = default.stereo
        if out.pty_names not in ('rbds', 'rds'):
            out.pty_names = default.pty_names
        if out.audio_source not in dict(AUDIO_SOURCES):
            out.audio_source = default.audio_source
        out.expected_pi = str(out.expected_pi).strip().upper()
        out.service_names = ', '.join(f'{k}={v}' for k, v in parse_service_names(str(out.service_names)).items())
        if out.expected_pi and not (len(out.expected_pi) == 4 and
                                    all(c in '0123456789ABCDEF' for c in out.expected_pi)):
            out.expected_pi = ''
        alarms = out.alarms if isinstance(out.alarms, dict) else {}
        out.alarms = {name: bool(alarms.get(name, True)) for name, *_ in ALARM_DEFS}
        out.name = str(out.name or '')
        out.rds_feed = bool(out.rds_feed)

        def number(name, lo, hi, kind=float):  # a hand-edited value of the wrong type: the default
            try:
                v = float(getattr(out, name))
                setattr(out, name, kind(min(max(v, lo), hi)) if math.isfinite(v) else getattr(default, name))
            except (TypeError, ValueError):
                setattr(out, name, getattr(default, name))
        number('volume_pct', 0, 200, int)
        number('silence_s', 2, 300, int)
        number('silence_lufs', -70, -10)
        number('min_snr_db', 0, 60)
        number('rds_port', 0, 65535, int)
        if not (out.rds_port == 0 or out.rds_port >= 1024):
            out.rds_port = 0
        if out.rules not in ('', 'ised', 'fcc', 'custom'):
            out.rules = ''
        for name, _, _, lo, hi, _ in LIMITS:
            try:
                setattr(out, name, float(min(max(float(getattr(out, name)), lo), hi)))
            except (TypeError, ValueError):
                setattr(out, name, getattr(default, name))
        return out

    def to_dict(self):
        return asdict(self)

    def preset(self, country):
        """The rule set in force: 'ised', 'fcc' or 'custom'."""
        return self.rules or ('ised' if country == 'CA' else 'fcc')

    def limits(self, country):
        """The limits in force: the preset's, or this receiver's own (custom)."""
        rules = self.preset(country)
        if rules in RULES:
            return dict(RULES[rules]['limits'])
        return {name: getattr(self, name) for name, *_ in LIMITS}


ALARM_GRACE_S = 5  # ignore alarms this long after (re)tuning


class StationAlarms:
    """Raises an alarm once its condition has held for its delay, and clears it
    the same way, so brief dips don't flap. update() returns what changed."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.active = set()
        self._pending = {}
        self.seen_pilot = self.seen_rds = False
        self._t0 = time.monotonic()

    def hold(self):
        """Pause judging for ALARM_GRACE_S (gain steps, SDR reopened) without
        forgetting what is raised: no false 'cleared', no repeat 'ALARM'."""
        self._pending = {}
        self._t0 = time.monotonic()

    def pending(self):
        """The alarms whose change (raise or clear) waits for its delay."""
        return set(self._pending)

    def ready(self):
        """False during the grace period after (re)tuning, while the meters
        still hold some of the previous station's signal."""
        return time.monotonic() - self._t0 >= ALARM_GRACE_S

    def update(self, conditions, holds=None):
        """[(name, description, raised)] for the alarms raised or cleared now."""
        now = time.monotonic()
        changes = []
        if now - self._t0 < ALARM_GRACE_S:
            return changes
        for name, desc, hold in ALARM_DEFS:
            hold = (holds or {}).get(name, hold)
            want = bool(conditions.get(name))
            if want == (name in self.active):
                self._pending.pop(name, None)
                continue
            if now - self._pending.setdefault(name, now) >= hold:
                del self._pending[name]
                (self.active.add if want else self.active.discard)(name)
                changes.append((name, desc, want))
        return changes


def rds_conditions(seen_rds, rate, carrier, pilot_ok, silent, backup_on=True):
    """(RDS lost, possibly on N+1) alarm conditions. RDS gone while the carrier,
    pilot and audio stay fine points at the N+1 backup transmitter, whose exciter
    has no RDS encoder, rather than an RDS fault: that is BACKUP, not RDS, unless
    the BACKUP alarm is switched off for the receiver."""
    lost = seen_rds and rate < 1
    backup = backup_on and lost and not carrier and pilot_ok and not silent
    return lost and not backup, backup


class DataServices:
    """Which data services a station carries: a service present for DATA_STEADY_S
    without a gap of DATA_GAP_S is steady, and from then on its absence is a loss."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._since = {}     # present service: start of its current unbroken run
        self.steady = set()

    def update(self, present):
        """present: the services on air now. Returns the steady services missing."""
        now = time.monotonic()
        for key in list(self._since):
            if key not in present:
                del self._since[key]
        for key in present:
            if now - self._since.setdefault(key, now) >= DATA_STEADY_S:
                self.steady.add(key)
        return sorted(self.steady - set(present))


def mod_limit(rules, limits, stats):
    """(limit %, how it was worked out) for peak modulation with `limits`."""
    inj = (stats.get('rds_pct') or 0.0) + sum(stats.get(f'sca{k}_pct') or 0.0 for k in (67, 92))
    lim = limits
    limit = min(lim['mod_base_pct'] + lim['mod_per_sub'] * inj, lim['mod_max_pct'])
    name = RULES[rules]['name'] if rules in RULES else 'custom'
    return limit, (f'{name}: {lim["mod_base_pct"]:g}% + {lim["mod_per_sub"]:g} \u00d7 {inj:.1f}% subcarriers, '
                   f'max {lim["mod_max_pct"]:g}%')


def _level(v, warn=None, alarm=None):
    """'alarm' above `alarm`, 'warn' above `warn`, else None (normal)."""
    if alarm is not None and v > alarm:
        return 'alarm'
    if warn is not None and v > warn:
        return 'warn'
    return None


LEVEL_COLOURS = {'warn': AMBER, 'alarm': RED}


def _coloured(text, level):
    """text in its level's colour (as is when normal)."""
    colour = LEVEL_COLOURS.get(level)
    return f'<span style="color:{colour}">{text}</span>' if colour else text


def _pct_html(v, level):
    return _coloured(f'{v:.0f}%', level)


def rds_phase(phase, lock):
    """RDS phase vs 3x the pilot as (mode, level): mode 'in phase' |
    'quadrature' | 'drifting' (not locked to the pilot), or (None, None)."""
    if phase is None or lock is None:
        return None, None
    if lock < RDS_LOCKED:
        return 'drifting', 'warn'
    quad = abs(phase) > 45
    err = abs(phase) - 90 if quad else phase
    return ('quadrature' if quad else 'in phase'), ('alarm' if abs(err) > RDS_PHASE_TOL else None)


def _rds_phase_html(phase, mode, level):
    if mode is None:
        return '-'
    if mode == 'drifting':
        return _coloured('drifting: not locked to the pilot', level)
    return _coloured(f'{round(phase):+d}\u00b0 ({mode}, locked)', level)


def _sync_am_db(pct):
    return 20 * math.log10(pct / 100) if pct else -math.inf


def _sync_am_html(pct, level, multipath):
    if pct is None:
        return '-'
    text = f'{pct:.2f}%  ({_num(_sync_am_db(pct), "dB", ".0f")})'
    return f'<span style="color:{DIM}">{text}  multipath</span>' if multipath else _coloured(text, level)


class _Ring:
    """The last n (time, row of values) pairs, oldest first from view()."""

    def __init__(self, n, width):
        self.t = np.full(n, np.nan)
        self.v = np.full((n, width), np.nan, dtype=np.float32)
        self.i = self.count = 0

    def add(self, t, row):
        self.t[self.i], self.v[self.i] = t, row
        self.i = (self.i + 1) % len(self.t)
        self.count = min(self.count + 1, len(self.t))

    def view(self):
        order = np.roll(np.arange(len(self.t)), -self.i)[len(self.t) - self.count:]
        return self.t[order], self.v[order]


class History:
    """A receiver's recent readings, for trend displays: every refresh for
    FAST_S, and one point a second for SLOW_S (peak readings: the second's
    maximum; the rest: its mean); and the alarm changes of the last ALARM_LOG_S.
    Times are time.time(); a reading not available is NaN."""

    KEYS = ('pos_pct', 'neg_pct', 'rf_dbfs', 'snr_db', 'am_pct', 'offset_hz', 'pilot_pct', 'rds_pct',
            'rds_rate', 'mpx_dbr', 'momentary', 'short_term', 'correlation')
    PEAKS = ('pos_pct', 'neg_pct', 'am_pct')
    FAST_S, SLOW_S, ALARM_LOG_S = 300, 3600, 86400

    def __init__(self):
        self._peak = np.array([k in self.PEAKS for k in self.KEYS])
        self.reset()

    def reset(self):
        self.fast = _Ring(self.FAST_S * UPDATE_HZ, len(self.KEYS))
        self.slow = _Ring(self.SLOW_S, len(self.KEYS))
        self._second, self._acc = None, []
        self.alarm_log = deque()  # (time, alarm name, raised)

    def add(self, t, readings):
        """readings: {key: value or None}; keys not in KEYS are ignored."""
        row = np.array([np.nan if readings.get(k) is None else readings[k] for k in self.KEYS], dtype=np.float64)
        self.fast.add(t, row)
        second = int(t)
        if self._acc and second != self._second:
            self._close_second()
        self._second = second
        self._acc.append(row)

    def _close_second(self):
        rows = np.array(self._acc)
        self._acc = []
        with np.errstate(all='ignore'), warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)  # a reading missing the whole second: NaN
            row = np.where(self._peak, np.nanmax(rows, axis=0), np.nanmean(rows, axis=0))
        self.slow.add(float(self._second), row)

    def series(self, key, seconds=FAST_S):
        """(times, values) of one reading over the last `seconds`: every
        refresh up to FAST_S, one a second beyond that."""
        ring = self.fast if seconds <= self.FAST_S else self.slow
        t, v = ring.view()
        keep = t >= (t[-1] if len(t) else 0) - seconds
        return t[keep], v[keep, self.KEYS.index(key)]

    def log_alarm(self, t, name, raised):
        self.alarm_log.append((t, name, raised))
        while self.alarm_log and self.alarm_log[0][0] < t - self.ALARM_LOG_S:
            self.alarm_log.popleft()


# Alarms that judge the transmission against the rules: only on clean reception
JUDGED_CLEAN = ('OVERMOD', 'PILOT_SPEC', 'SUBCARRIERS', 'FREQUENCY')


class StationPanel(QtCore.QObject):
    """One receiver: measures it, judges its alarms, keeps its history, and shows
    it as a station row (self.row) and a detail view (self.detail)."""

    def __init__(self, station, stations, on_play, on_select, iboc_scan=None, on_remove=None, on_settings=None,
                 on_source=None, radiodns=None, country='CA', on_focus=None, on_pop=None):
        super().__init__()
        self.station = station
        self.slot = 0
        self.settings = ReceiverSettings()
        self.radiodns = radiodns
        self.country = country
        self.iboc_scan = iboc_scan if iboc_scan is not None else {}
        self.alarms = StationAlarms()
        self.data_services = DataServices()
        self._data_lost = []
        self._data_codes = {}  # service: its code for a name ('7A', 'SCA67')
        self._rt_alarm = ''
        self.rate = 0.0
        self._groups = deque()
        self.readings = {}      # the latest _measure(): every reading as plain values
        self.history = History()
        self._web_lists = None  # (stations, sources) for the web page; None = rebuild
        self.setObjectName('panel')
        self.on_focus, self.on_pop = on_focus, on_pop

        # ---- the station row: station, text, tapes, alarms, settings / remove
        self.row = StationRow(lambda: self.on_focus and self.on_focus(self),
                              lambda: self.on_pop and self.on_pop(self))
        row = QtWidgets.QHBoxLayout(self.row)
        row.setContentsMargins(10, 5, 6, 5)
        row.setSpacing(12)
        widths = {key: w for key, _, w in ROW_COLS}

        # Station selector: every station the scan found; ones that can't share
        # the SDR window with the other receivers are greyed out.
        self.combo = FreqCombo()
        self.combo.setObjectName('freq')
        for freq, snr in stations:
            self.combo.addItem(f'{freq / 1e6:.1f} MHz', freq)
            if snr is not None:
                self.combo.setItemData(self.combo.count() - 1,
                                       f'scan: {snr:.0f} dB above noise', QtCore.Qt.ToolTipRole)
        self.combo.setCurrentIndex(self.combo.findData(station.freq_hz))
        self.combo.setToolTip('Station: choose another to retune this receiver')
        self.combo.activated.connect(lambda i: on_select(self, self.combo.itemData(i)))
        self.ps = QtWidgets.QLabel('--------')
        self.ps.setTextFormat(QtCore.Qt.PlainText)
        self.ps.setAlignment(QtCore.Qt.AlignCenter)
        ps_font = QtGui.QFont('Consolas', 12, QtGui.QFont.Bold)
        self.ps.setFont(ps_font)
        self.ps.setStyleSheet(LCD + 'font-family: Consolas; font-size: 12pt; font-weight: bold;'
                              'color: #7cfc7c; padding: 1px 4px; border-radius: 4px;')
        self.ps.setFixedWidth(QtGui.QFontMetrics(ps_font).horizontalAdvance('M' * 8) + 14)
        # DYNAMIC PS: an amber chip beside the PS, shown only while it applies
        self.ps_mode = QtWidgets.QLabel('DYN')
        self.ps_mode.setStyleSheet('border-radius: 3px; padding: 1px 4px; font-weight: 600; font-size: 7pt;'
                                   'background: #33363c; color: #e3e4e6; border: 1px solid #44474e;')
        self.ps_mode.setToolTip('Dynamic PS: the PS has changed 3 or more times in the last '
                                f'{DYNAMIC_PS_S} s (scrolling or block text)')
        self.ps_mode.hide()
        self.meta = QtWidgets.QLabel('')
        self.meta.setTextFormat(QtCore.Qt.RichText)
        self.meta.setStyleSheet('color: #8c9197; font-size: 8pt;')
        self.meta.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        station_box = QtWidgets.QWidget()
        station_box.setFixedWidth(widths['station'])
        sb = QtWidgets.QVBoxLayout(station_box)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(2)
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(self.combo)
        top.addWidget(self.ps)
        top.addWidget(self.ps_mode)
        top.addStretch(1)
        sb.addLayout(top)
        sb.addWidget(self.meta)
        row.addWidget(station_box)

        # Radiotext: up to 64 characters on one line (cut at the column edge, all
        # of it in the tooltip); RT+ tags, else the RDS flags, under it.
        self.rt = QtWidgets.QLabel('')
        self.rt.setTextFormat(QtCore.Qt.PlainText)
        self.rt.setFont(QtGui.QFont('Consolas', 10))
        self.rt.setStyleSheet(LCD + 'color: #cfe8cf; padding: 2px 6px; font-family: Consolas; font-size: 10pt;'
                              'border-radius: 4px;')
        self.rt.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.rt.setMinimumHeight(QtGui.QFontMetrics(self.rt.font()).height() + 8)
        self.rtplus = QtWidgets.QLabel('')
        self.rtplus.setTextFormat(QtCore.Qt.RichText)
        self.rtplus.setStyleSheet('color: #c4c7cc;')
        self.rtplus.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        text_box = QtWidgets.QVBoxLayout()
        text_box.setSpacing(3)
        text_box.addWidget(self.rt)
        text_box.addWidget(self.rtplus)
        row.addLayout(text_box, 1)

        # now: peak modulation against the limit in force, RF level, AM / multipath
        self.tapes = {
            'mod': Tape('MOD', 0, 130, band=(85, 100), hold=True),
            'rf': Tape('RF', -90, -10, band=(-60, -10)),
            'am': Tape('AM', 0, 40, band=(0, PEAK_AM_PCT)),
        }
        self.tapes['mod'].setToolTip('Peak modulation +/−: bar, 2 s peak hold (tick) and the limit in force '
                                     '(red notch); the grey band is the normal range')
        self.tapes['rf'].setToolTip('RF level at the SDR')
        self.tapes['am'].setToolTip('AM on the carrier: multipath or a transmitter fault. Over-modulation is '
                                    f'not judged above {PEAK_AM_PCT:g}%, the other technical rules above '
                                    f'{CLEAN_AM_PCT:g}%')
        tapes = QtWidgets.QWidget()
        tapes.setFixedWidth(widths['tapes'])
        tb = QtWidgets.QVBoxLayout(tapes)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(1)
        for t in self.tapes.values():
            tb.addWidget(t)
        row.addWidget(tapes)

        # trend: the last 5 minutes of peak modulation, excursions over the limit in red
        self.trend_note = QtWidgets.QLabel('')
        self.trend_note.setStyleSheet('color: #8c9197; font-size: 7pt;')
        self.trend_note.setTextFormat(QtCore.Qt.RichText)
        self.spark = Spark(70, 125, limit=100)
        self.spark.setToolTip('Peak modulation, the last 5 minutes (each point: its highest); '
                              'red: over the limit in force')
        trend = QtWidgets.QWidget()
        trend.setFixedWidth(widths['trend'])
        tr = QtWidgets.QVBoxLayout(trend)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(1)
        tr.addWidget(self.trend_note)
        tr.addWidget(self.spark)
        row.addWidget(trend)
        self._trend_t = -math.inf
        self.web_trends = {}    # the sparklines and histogram for the web page

        # every alarm, always in the same place: raised, holding off, not judged, off
        self.annunciator = Annunciator()
        self.annunciator.setFixedWidth(widths['alarms'])
        row.addWidget(self.annunciator)

        self.settings_btn = QtWidgets.QToolButton()
        self.settings_btn.setObjectName('rowBtn')
        self.settings_btn.setText('⚙')
        self.settings_btn.setToolTip('Settings for this receiver')
        self.settings_btn.clicked.connect(lambda: on_settings(self) if on_settings else None)
        self.remove_btn = QtWidgets.QToolButton()
        self.remove_btn.setObjectName('rowBtn')
        self.remove_btn.setText('✕')
        self.remove_btn.setToolTip('Remove this receiver')
        self.remove_btn.clicked.connect(lambda: on_remove(self) if on_remove else None)
        buttons = QtWidgets.QVBoxLayout()
        buttons.setSpacing(0)
        buttons.addWidget(self.settings_btn)
        buttons.addWidget(self.remove_btn)
        row.addLayout(buttons)

        # ---- the detail view: this receiver in depth, under the rows or in its own window
        self.window = None      # its DetailWindow while popped out
        self.detail = QtWidgets.QFrame()
        self.detail.setObjectName('detail')
        layout = QtWidgets.QVBoxLayout(self.detail)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)
        self.detail_title = QtWidgets.QLabel('')
        self.detail_title.setStyleSheet('font-weight: 700; font-size: 10pt;')
        self.detail_sub = QtWidgets.QLabel('')
        self.detail_sub.setStyleSheet('color: #8c9197;')
        self.detail_sub.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.feed = None  # RdsGroupServer for this receiver, if any
        self.feed_label = QtWidgets.QLabel('')
        self.feed_label.setStyleSheet('color: #8c9197;')
        self.tabs = QtWidgets.QTabBar()
        self.tabs.setObjectName('detailTabs')
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.addTab('Overview')
        self.tabs.addTab('History')
        self.pop_btn = QtWidgets.QToolButton()
        self.pop_btn.setText('⧉  Pop out')
        self.pop_btn.setToolTip('Show this receiver in its own window (double-clicking its row does the same)')
        self.pop_btn.clicked.connect(lambda: self.on_pop and self.on_pop(self))
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self.detail_title)
        head.addWidget(self.detail_sub, 1)
        head.addWidget(self.feed_label)
        head.addWidget(self.tabs)
        head.addWidget(self.pop_btn)
        layout.addLayout(head)
        self.pages = QtWidgets.QStackedWidget()
        self.tabs.currentChanged.connect(self.pages.setCurrentIndex)
        self.tabs.currentChanged.connect(lambda i: i == 1 and self.history_view.refresh())
        layout.addWidget(self.pages)
        overview = QtWidgets.QWidget()
        ov = QtWidgets.QVBoxLayout(overview)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(6)
        self.pages.addWidget(overview)

        # IBOC, PSD, SIS and RadioDNS lines (each only while there is something to say),
        # with the station logo and album art beside them
        text_grid = QtWidgets.QGridLayout()
        text_grid.setHorizontalSpacing(8)
        text_grid.setVerticalSpacing(3)
        self.iboc_line, self.psd_line, self.sis_line, self.rdns_line = (QtWidgets.QLabel('-') for _ in range(4))
        self._iboc_rows = []   # IBOC, PSD and SIS rows: shown only when the station has IBOC
        self._rdns_row = ()     # the RadioDNS row: shown only while RadioDNS works for the station
        self._rdns_working = False
        self._stereo = None     # the large stereo-image window, once opened
        self.rdns_line.setToolTip('RadioDNS service information (ETSI TS 103 270 / TS 102 818)')
        self.logo_img, self.art_img = QtWidgets.QLabel(), QtWidgets.QLabel()
        for img in (self.logo_img, self.art_img):
            img.setFixedSize(IMG_PX, IMG_PX)
            img.setAlignment(QtCore.Qt.AlignCenter)
            img.hide()
            img.path = img.link = None
        # a RadioDNS slide's click-through link (TS 101 499 5.3.3) opens in the browser
        self.art_img.mousePressEvent = lambda e: self.art_img.link and QtGui.QDesktopServices.openUrl(
            QtCore.QUrl(self.art_img.link))
        text_grid.addWidget(self.logo_img, 0, 2, 4, 1)
        text_grid.addWidget(self.art_img, 0, 3, 4, 1)
        for w in (self.iboc_line, self.psd_line, self.sis_line, self.rdns_line):
            w.setTextFormat(QtCore.Qt.RichText)
            w.setStyleSheet('color: #c4c7cc;')
            # long text is cut at the edge (full text in the tooltip), never widening the view
            w.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.psd_line.setToolTip('IBOC programme service data (PSD) of the programme playing')
        self.sis_line.setToolTip('IBOC station information service (SIS)')
        for i, (title, widget) in enumerate((('IBOC', self.iboc_line), ('PSD', self.psd_line),
                                             ('SIS', self.sis_line), ('RadioDNS', self.rdns_line))):
            label = QtWidgets.QLabel(title)
            label.setStyleSheet('font-weight: bold; color: #9aa0a6;')
            label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            text_grid.addWidget(label, i, 0)
            text_grid.addWidget(widget, i, 1)
            if title == 'RadioDNS':
                self._rdns_row = (label, widget)
            else:
                self._iboc_rows.extend((label, widget))
        text_grid.setColumnStretch(1, 1)
        # start without the rows refresh() would hide anyway, so the window opens at its final height
        for w in self._iboc_rows if not self._iboc_lines() else ():
            w.hide()
        for w in self._rdns_row:
            w.hide()
        ov.addLayout(text_grid)

        self.values = {}
        self._kv_rows = {}      # readout: its (label, value), to hide when it isn't on air
        self.absent = {}        # card: its 'not on air' line
        cards = QtWidgets.QGridLayout()
        cards.setSpacing(8)
        ov.addLayout(cards)

        def dim_label(text=''):
            label = QtWidgets.QLabel(text)
            label.setStyleSheet('color: #8c9197; font-size: 8pt;')
            return label

        # modulation: peak tapes against the limit in force, then the counts and channels
        self.limit_note = dim_label()
        mod, box = card('Modulation', self.limit_note)
        self.peak_tapes = {key: Tape(name, 0, 130, band=(85, 100), hold=True, name_w=50, val_w=110)
                           for key, name in (('pos', '+ peak'), ('neg', '− peak'))}
        for t in self.peak_tapes.values():
            box.addWidget(t)
        self.peak_hist = PeakHistogram()
        self.peak_hist.setToolTip('How peak modulation spreads: the share of updates at each peak level over the '
                                  'last 5 minutes (log height). Red: over the limit in force; amber: over 100%')
        box.addWidget(dim_label('Peak distribution \u00b7 last 5 min'))
        box.addWidget(self.peak_hist)
        box.addLayout(self._kv(('Peak deviation', 'MPX power', 'Over 100%', 'Over 110%', 'L / R', 'L+R / L−R',
                                'Limit'), 2, wide=('Limit',)))
        box.addStretch(1)
        cards.addWidget(mod, 0, 0)

        # multiplex: spectrum, S/N, pilot and carrier tapes, the subcarriers
        mpx_card, box = card('Multiplex', dim_label('0–100 kHz'))
        self.mpx = MpxSpectrum()
        self.mpx.setMinimumHeight(140)
        box.addWidget(self.mpx)
        self.mpx_tapes = {
            'snr': Tape('S/N', 0, 70, band=(30, 70), name_w=50, val_w=110),
            'pilot': Tape('Pilot', 6, 12, band=(8, 10), name_w=50, val_w=110),
            'offset': Tape('Offset', -3000, 3000, origin=0, band=(-1000, 1000), name_w=50, val_w=110),
        }
        self.mpx_tapes['snr'].setToolTip('MPX S/N, unweighted 15 kHz; below the carrier alarm\'s setting is carrier low')
        self.mpx_tapes['pilot'].setToolTip('Pilot injection; the grey band is the range the rules allow')
        self.mpx_tapes['offset'].setToolTip('Carrier offset; the grey band is the tolerance (includes the SDR\'s own error)')
        for t in self.mpx_tapes.values():
            box.addWidget(t)
        box.addLayout(self._kv(('RF level', 'AM / multipath', 'Pilot freq', 'RDS injection', 'RDS phase', 'Sync AM',
                                'SCA 67 kHz', 'SCA 92 kHz', 'IBOC signal'), 2,
                               wide=('RDS phase', 'Sync AM', 'SCA 67 kHz', 'SCA 92 kHz', 'IBOC signal')))
        self.absent['mpx'] = dim_label()
        box.addWidget(self.absent['mpx'])
        box.addStretch(1)
        cards.addWidget(mpx_card, 0, 1)

        # RDS
        self.rds_note = dim_label()
        rds, box = card('RDS', self.rds_note)
        self.rds_spark = Spark(0, 12)
        self.rds_spark.setToolTip('RDS groups per second, the last 5 minutes (11.4/s is every group)')
        box.addWidget(self.rds_spark)
        box.addLayout(self._kv(('PI', 'PTY', 'PTYN', 'ECC', 'Groups/s', 'Group loss', 'Flags', 'ODA', 'Alt. freqs',
                                'Clock', 'Group types', 'Data services'), 2,
                               wide=('Flags', 'ODA', 'Alt. freqs', 'Clock', 'Group types', 'Data services')))
        self.absent['rds'] = dim_label()
        self.absent['rds'].setWordWrap(True)
        box.addWidget(self.absent['rds'])
        box.addStretch(1)
        cards.addWidget(rds, 0, 2)

        # audio: loudness, the stereo image, and what Play plays
        reset = QtWidgets.QToolButton()
        reset.setText('reset I')
        reset.setToolTip('Start the integrated loudness again')
        reset.setStyleSheet('padding: 0 6px;')
        reset.clicked.connect(station.audio_meter.reset_integrated)
        audio, box = card('Audio', reset)
        box.addLayout(self._kv(('Momentary', 'Short-term', 'Integrated', 'True peak L/R'), 2))
        self.lufs_spark = Spark(-40, 0, ref=-23)
        self.lufs_spark.setToolTip('Short-term loudness, the last 5 minutes (dotted: -23 LUFS)')
        box.addWidget(self.lufs_spark)
        self.gonio = Goniometer(size=104)
        self.gonio.setCursor(QtCore.Qt.PointingHandCursor)
        self.gonio.setToolTip('Click for a larger view')
        self.gonio.on_click = self._open_stereo
        self.meters = {'corr': Meter('Phase', -1, 1, [(-0.0001, RED), (1, NORMAL)], origin=0, ticks=(0,))}
        self.meters['corr'].setMinimumWidth(120)
        self.meters['corr'].name_w = 44
        stereo = QtWidgets.QHBoxLayout()
        stereo.setSpacing(8)
        stereo.addWidget(self.gonio, 0, QtCore.Qt.AlignTop)
        side = QtWidgets.QVBoxLayout()
        side.setSpacing(2)
        side.addWidget(self.meters['corr'])
        side.addLayout(self._kv(('Balance', 'Width (S/M)', 'Level L/R', 'Correlation'), 1))
        side.addStretch(1)
        stereo.addLayout(side, 1)
        box.addLayout(stereo)
        self.source = QtWidgets.QComboBox()
        for key, label in AUDIO_SOURCES:
            self.source.addItem(label, key)
        self.source.setToolTip('What Play plays')
        self.source.activated.connect(lambda i: on_source(self, self.source.itemData(i)) if on_source else None)
        self.play = QtWidgets.QPushButton('▶  Play')
        self.play.setCheckable(True)
        self.play.setStyleSheet('QPushButton { font-weight: 600; padding: 3px 10px; }'
                                'QPushButton:checked { background: #2f6db5; color: white;'
                                ' border: 1px solid #8ab4f8; border-radius: 6px; }'
                                'QPushButton:checked:hover { background: #3a7cc6; }')
        self.play.toggled.connect(lambda on: on_play(self, on))
        box.addStretch(1)
        audio_row = QtWidgets.QHBoxLayout()
        audio_row.addWidget(self.play, 1)
        audio_row.addWidget(self.source, 1)
        box.addLayout(audio_row)
        cards.addWidget(audio, 0, 3)
        for col, stretch in enumerate((24, 26, 24, 22)):
            cards.setColumnStretch(col, stretch)
        self.history_view = HistoryView(self)
        self.pages.addWidget(self.history_view)
        # readouts the tapes show instead: kept (hidden) so every reading still has its text
        for name in ('Peak + / −', 'MPX S/N', 'Carrier offset', 'Pilot (19 kHz)'):
            self.values[name] = QtWidgets.QLabel('-')

    def _kv(self, names, cols, wide=()):
        """Label/value pairs in `cols` columns; readouts in `wide` get a full-width
        row each at the end. Long values are cut at the card edge, never widening it."""
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        normal = [n for n in names if n not in wide]
        rows = (len(normal) + cols - 1) // cols
        for i, name in enumerate(normal + [n for n in names if n in wide]):
            if i < len(normal):
                row, col, span = i // cols, i % cols, 1
            else:
                row, col, span = rows + i - len(normal), 0, cols * 2 - 1
            label = QtWidgets.QLabel(name)
            label.setStyleSheet('color: #9aa0a6;')
            value = QtWidgets.QLabel('-')
            value.setTextFormat(QtCore.Qt.RichText)
            value.setStyleSheet('font-weight: 600;')
            value.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            grid.addWidget(label, row, col * 2)
            grid.addWidget(value, row, col * 2 + 1, 1, span)
            self.values[name] = value
            self._kv_rows[name] = (label, value)
        for col in range(cols):
            grid.setColumnStretch(col * 2 + 1, 1)
        return grid

    def static_ps(self):
        """The PS as a station name: '' while it is dynamic, None until a complete
        PS has held for PS_NAME_STABLE_S (so a scrolling PS's first frames
        don't become the name before it is recognised as dynamic)."""
        raw = self.station.rds.snapshot()
        if raw['ps_dynamic']:
            return ''
        if raw['ps'].strip() and raw['ps_age'] >= PS_NAME_STABLE_S:
            return raw['ps'].strip()
        return None

    @property
    def title(self):
        ps = self.static_ps() or self.station.rds.snapshot()['ps'].strip()
        return f'{self.station.freq_hz / 1e6:.1f}' + (f' {ps}' if ps else '')

    def set_fit(self, other_freqs):
        """Grey out stations that can't share the SDR window with other_freqs."""
        for i in range(self.combo.count()):
            ok = _fits(other_freqs + [self.combo.itemData(i)])
            self.combo.model().item(i).setEnabled(ok)
        self._web_lists = None

    def set_station_name(self, freq, ps):
        i = self.combo.findData(freq)
        if i >= 0:
            self.combo.setItemText(i, f'{freq / 1e6:.1f} MHz' + (f'  {ps}' if ps else ''))
            self._web_lists = None

    def source_key(self):
        return self.source.currentData()

    def set_source(self, key):
        self.source.setCurrentIndex(self.source.findData(key))

    def set_sources(self, nrsc5):
        """Grey out IBOC where it can't play: no nrsc5, or no IBOC found on this station."""
        scan = self.iboc_scan.get(self.station.freq_hz, 'unknown')
        why = ('nrsc5 not found (see --nrsc5)' if not nrsc5 else
               'The start-up scan found no IBOC on this station' if scan is None else '')
        for i, (key, _) in enumerate(AUDIO_SOURCES):
            if key.startswith('iboc'):
                item = self.source.model().item(i)
                item.setEnabled(not why)
                item.setToolTip(why)
        self._web_lists = None
        return not why

    IBOC_TEXT = ('artist', 'title', 'album', 'genre', 'comment', 'name', 'slogan', 'message', 'alert')

    def _iboc_readings(self):
        """The IBOC programme playing (from nrsc5's status), or None when none plays."""
        dec = self.station.iboc
        if not dec:
            return None
        st = dec.status
        return {'program': dec.program, 'service': st['services'].get(dec.program), 'synced': st['synced'],
                'kbps': st['kbps'] or None, 'mer_db': min(st['mer']) if st['mer'] else None, 'ber': st['ber'],
                'dropped': dec.pipe.dropped, **{k: st[k] for k in self.IBOC_TEXT}}

    @staticmethod
    def _iboc_line_text(ib):
        if not ib:
            return '-'
        parts = [dict(AUDIO_SOURCES)[f'iboc{ib["program"]}'].split()[1],
                 'synchronized' if ib['synced'] else f'<span style="color:{AMBER}">searching\u2026</span>']
        if ib['service'] is not None:
            parts[0] += f" ({ib['service']})"
        if ib['kbps']:
            parts.append(f"{ib['kbps']:.0f} kbps")
        if ib['mer_db'] is not None:
            parts.append(f"MER {ib['mer_db']:.1f} dB")
        if ib['ber'] is not None:
            parts.append(f"BER {ib['ber']:.1e}")
        if ib['dropped']:
            parts.append(f'<span style="color:{RED}">{ib["dropped"]} blocks dropped</span>')
        if ib['alert']:
            parts.append(f'<b style="color:{RED}">ALERT: {_html(ib["alert"])}</b>')
        return '  \u00b7  '.join(parts)

    @staticmethod
    def _psd_sis_text(ib):
        """(PSD line, SIS line) from nrsc5, each '-' when there is nothing."""
        if not ib:
            return '-', '-'
        song = ' \u2013 '.join(x for x in (ib['artist'], ib['title']) if x)
        psd = [x for x in (song, ib['album'], ib['genre'], ib['comment']) if x]
        sis = [x for x in (ib['name'], ib['slogan'], ib['message']) if x]
        return ('  \u00b7  '.join(map(_html, psd)) or '-', '  \u00b7  '.join(map(_html, sis)) or '-')

    def _rdns_lookups(self, pi, ecc):
        """[(label, result, slideshow or None)] for this station's RadioDNS
        services (FM, and IBOC while it plays)."""
        if not self.radiodns:
            return []
        out = []
        pi = (pi or '').strip()
        fm_key = radiodns_fm(pi, self.station.freq_hz, ecc, self.country) if pi else None
        if fm_key:
            out.append(('FM', self.radiodns.lookup(*fm_key), self.radiodns.vis(fm_key[0])))
        dec = self.station.iboc
        if dec:
            iboc_key = radiodns_iboc(dec.status['country'], dec.status['facility'], dec.program)
            if iboc_key:
                out.append(('IBOC', self.radiodns.lookup(*iboc_key), self.radiodns.vis(iboc_key[0])))
        return out

    @staticmethod
    def _rdns_text(result):
        state = result['state']
        if state == 'found':
            text = f"{_html(result['name'] or 'listed')} ({result['spi']})"
            if result.get('description'):
                text += f" \u2013 {_html(result['description'])}"
            return text
        if state == 'needs client identifier':
            return (f'registered ({result["target"]}); <span style="color:{AMBER}">service information '
                    'needs a client identifier</span>')
        if state in ('client identifier rejected', 'not listed', 'no service information'):
            return f'registered ({result["target"]}); <span style="color:{AMBER}">{state}</span>'
        if state == 'error':
            return f'<span style="color:{RED}">lookup failed: {_html(result.get("error", ""))}</span>'
        return f'<span style="color:{DIM}">{state}</span>'

    def _update_media(self, pi, ecc):
        """RadioDNS line (only while RadioDNS works for the station), station
        logo (IBOC on air, else RadioDNS) and album art (IBOC, else the RadioDNS slideshow)."""
        lookups = self._rdns_lookups(pi, ecc)
        working = [(label, r, vis) for label, r, vis in lookups
                   if r['state'] == 'found' or (vis and vis.image)]
        parts = []
        for label, r, vis in working:
            text = self._rdns_text(r) if r['state'] == 'found' else f'registered ({_html(r.get("target", ""))})'
            if vis and vis.image:
                text += f' \u00b7 slideshow ({VIS_TRANSPORT_NAMES[vis.transport]})'
                if vis.text:
                    text += f': \u201c{_html(vis.text)}\u201d'
            parts.append(f'{label}: {text}')
        self.rdns_line.setText('  \u00b7  '.join(parts) or '-')
        self.rdns_line.setToolTip(QtGui.QTextDocumentFragment.fromHtml(self.rdns_line.text()).toPlainText())
        self._rdns_working = bool(working)
        for w in self._rdns_row:
            if w.isHidden() == self._rdns_working:
                w.setVisible(self._rdns_working)
        logo, art = self.station.iboc.images() if self.station.iboc else (None, None)
        art_what, art_link = 'Album art', None
        for label, r, vis in reversed(lookups):  # IBOC's RadioDNS logo and slideshow before FM's
            logo = logo or r.get('logo')
            if not art and vis and vis.image:
                art, art_link = vis.image, vis.link
                art_what = 'Album art (RadioDNS slideshow)' + (f': {_html(vis.text)}' if vis.text else '')
                if art_link:
                    art_what += f'<br>Click to open {_html(art_link)}'
        self._show_image(self.logo_img, logo, 'Station logo')
        self._show_image(self.art_img, art, art_what)
        if self.art_img.link != art_link:
            self.art_img.link = art_link
            self.art_img.setCursor(QtCore.Qt.PointingHandCursor if art_link else QtCore.Qt.ArrowCursor)

    @staticmethod
    def _show_image(label, path, what):
        if path != label.path:
            label.path = path
            pix = QtGui.QPixmap(path) if path and os.path.exists(path) else QtGui.QPixmap()
            if pix.isNull():
                label.clear()
                label.hide()
                return
            label.setPixmap(pix.scaled(IMG_PX, IMG_PX, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            label.show()
        if not label.isHidden():  # the tooltip follows the slideshow text and link
            tip = f'{what}<br><img src="{path}" width="{IMG_TIP_PX}">'
            if label.toolTip() != tip:
                label.setToolTip(tip)

    def reset_display(self):
        self.ps.setText('--------')
        self.ps_mode.hide()
        self.rt.setText('')
        self.rtplus.setText('-')
        for value in self.values.values():
            value.setText('-')
        self._groups.clear()
        self.rate = 0.0
        self.alarms.reset()
        self.data_services.reset()
        self._data_lost = []
        self._data_codes = {}
        self._rt_alarm = ''
        self.readings = {}
        self.history.reset()
        for m in self.meters.values():
            m.set_value(None, '-')
        for t in (*self.tapes.values(), *self.peak_tapes.values(), *self.mpx_tapes.values()):
            t.clear()
        self.meta.setText('')
        self.annunciator.set_states({})
        self._trend_t = -math.inf
        self.web_trends = {}
        for spark in (self.spark, self.rds_spark, self.lufs_spark):
            spark.set_data([])
        self.peak_hist.set_data([], None)
        self.gonio.set_data(None)
        self.mpx.set_data(None)

    def _rds_rate(self):
        """Groups per second over the last 3 s."""
        now = time.monotonic()
        self._groups.append((now, self.station.rds.groups))
        while now - self._groups[0][0] > 3.0:
            self._groups.popleft()
        (t0, g0), (t1, g1) = self._groups[0], self._groups[-1]
        return (g1 - g0) / (t1 - t0) if t1 > t0 else 0.0

    def _sca_kind(self, khz, s):
        """'audio' | 'data' | 'tone' | 'idle' | 'weak' | 'checking', or None if there is no SCA."""
        if s is None or s[f'sca{khz}_pct'] is None:
            return None
        if s[f'sca{khz}_db'] < SCA_CLASSIFY_DB:
            return 'weak'
        kind = self.station.sca_meter.kinds[khz]
        return kind[0] if kind else 'checking'

    @staticmethod
    def _sca_kind_html(kind, baud):
        return {
            'audio': 'AUDIO',
            'data': 'DATA' + (f' ~{baud:.0f} Bd' if baud else '') + f' <span style="color:{DIM}">(not audio)</span>',
            'tone': 'TONE',
            'idle': f'<span style="color:{DIM}">IDLE (no modulation)</span>',
            'weak': f'PRESENT <span style="color:{DIM}">(too weak to tell)</span>',
            'checking': f'PRESENT <span style="color:{DIM}">(checking…)</span>',
        }[kind]

    def _sca_sources(self, sca):
        """Label the SCA audio sources with what they carry, so data isn't taken for audio."""
        for i, (key, label) in enumerate(AUDIO_SOURCES):
            if not key.startswith('sca'):
                continue
            kind = sca[int(key[3:])]['kind']
            text, tip = label, ''
            if kind is None:
                text, tip = f'{label} (none)', 'No subcarrier on this station'
            elif kind == 'data':
                text, tip = f'{label} (data)', 'This subcarrier carries data, not audio: there is nothing to listen to'
            elif kind == 'idle':
                text, tip = f'{label} (idle)', 'This subcarrier is on but carries nothing'
            if self.source.itemText(i) != text:
                self.source.setItemText(i, text)
                self.source.setItemData(i, tip, QtCore.Qt.ToolTipRole)
                self._web_lists = None

    def _open_stereo(self):
        if self._stereo is None:
            self._stereo = StereoWindow(self, self.detail)
        self._stereo.follow(self)
        self._stereo.show()
        self._stereo.raise_()
        self._stereo.activateWindow()

    def rules(self):
        """The rule set the alarms use: 'ised', 'fcc' or 'custom'."""
        return self.settings.preset(self.country)

    def _iboc_lines(self):
        """Whether to show the IBOC, PSD and SIS rows: IBOC found on this station, or playing."""
        return bool(self.station.iboc) or isinstance(self.iboc_scan.get(self.station.freq_hz), float)

    def _iboc_scan_readings(self):
        """What the start-up scan found of IBOC on this station: ('unscanned' |
        'adjacent' | 'absent' | 'detected', level in dBc or None)."""
        if self.station.freq_hz not in self.iboc_scan:
            return 'unscanned', None
        info = self.iboc_scan[self.station.freq_hz]
        if info == 'adjacent':
            return 'adjacent', None
        if info is None:
            return 'absent', None
        return 'detected', info

    @staticmethod
    def _iboc_text(found, dbc):
        if found == 'detected':
            return f'detected, {dbc:.0f} dBc'
        return f'<span style="color:{DIM}">' + {'unscanned': 'unknown (not scanned)',
                                                'adjacent': 'unknown (adjacent station)',
                                                'absent': 'not detected'}[found] + '</span>'

    def _measure(self):
        """Every reading of this receiver as plain values: text, numbers, lists
        (None: not received yet). 'levels' holds {reading: 'warn' | 'alarm'} for
        readings out of their range. Measurement and signal readings are present
        only once the meters have them ('has_signal', 'has_audio').
        Keeps the RDS rate, the data services and the RT+ alarm current."""
        st = self.station
        f = st.rds.fields
        raw = st.rds.snapshot()
        lv = {}
        r = {'freq_hz': st.freq_hz, 'levels': lv}

        # station text
        r['ps'] = raw['ps'] or (f[1].ljust(8) if 1 in f else None)
        r['ps_dynamic'] = raw['ps_dynamic']
        r['rt'] = f.get(4, '').strip()
        r['rtplus'] = [(t, RTPLUS_TYPES.get(t, f'type {t}'), text) for t, text in
                       sorted(raw['rtplus'], key=lambda kv: (kv[0] != RTPLUS_ALARM, kv[0] != 4, kv[0]))]
        self._rt_alarm = r['rt_alarm'] = next((text for t, text in raw['rtplus'] if t == RTPLUS_ALARM), '')
        r['iboc'] = self._iboc_readings()
        r['iboc_lines'] = self._iboc_lines()
        r['iboc_found'], r['iboc_dbc'] = self._iboc_scan_readings()

        # RDS
        r['pi'] = f.get(0)
        r['pty'] = ((PTY_RDS if self.settings.pty_names == 'rds' else PTY_RBDS)[raw['pty']]
                    if raw['pty'] is not None else f.get(2))
        r['flags'] = rds_flags(f.get(3, ''))
        r['clock'] = raw['ct']      # (local datetime, UTC offset in minutes) or None
        r['af'] = f.get(6) or ''
        r['ptyn'] = raw['ptyn'] or ''
        r['ecc'] = raw['ecc']       # None: not sent; 0: sent as 00 (not set)
        r['oda'] = [ODA_NAMES.get(aid, f'{aid:04X}') for aid in raw['oda']]
        self.rate = r['rds_rate'] = self._rds_rate()
        total = sum(raw['types'].values())
        r['rds_loss_pct'] = max(0.0, 1 - self.rate / 11.4) * 100 if total else None
        r['group_types'] = ([(k, n * 100 / total) for k, n in sorted(raw['types'].items(), key=lambda kv: -kv[1])]
                            if total else [])

        # signal and modulation
        s = st.meter.stats
        r['has_signal'] = bool(s)
        sca_kinds = {}
        if s:
            lim = self.settings.limits(self.country)
            limit, why = mod_limit(self.rules(), lim, s)
            tol = lim['freq_tol_hz']
            r.update(limits=lim, rf_dbfs=s['rf_dbfs'], snr_db=s['snr_db'], offset_hz=s['offset_hz'],
                     am_pct=s['am_pct'], pilot_pct=s['pilot_pct'], pilot_hz=st.pilot_hz, rds_pct=s['rds_pct'],
                     stereo_mode='stereo' if st.stereo else 'forced mono' if st.pilot else 'mono',
                     pos_pct=s['pos_pct'], neg_pct=s['neg_pct'], limit_pct=limit, limit_why=why,
                     dev_khz=s['peak_dev_khz'], over100_min=s['over100_min'], over110_min=s['over110_min'],
                     mpx_dbr=s['mpx_dbr'], mpx_window_s=s['mpx_window_s'], mpx_db=s['mpx_db'])
            # RDS phase only for a station with RDS: an SCA's skirt or noise in the 57 kHz band has a phase too.
            r['rds_phase_deg'] = s['rds_phase_deg'] if total else None
            r['rds_phase_mode'], level = rds_phase(r['rds_phase_deg'], s['rds_lock'])
            if level:
                lv['rds_phase_deg'] = level
            # Short echoes give the same AM as a mistuned transmitter: only judge it on a clean path.
            r['sync_am_pct'] = s['sync_am_pct']
            r['sync_am_multipath'] = s['am_max_pct'] >= PEAK_AM_PCT
            if (s['sync_am_pct'] is not None and not r['sync_am_multipath']
                    and _sync_am_db(s['sync_am_pct']) > -35):
                lv['sync_am_pct'] = 'warn'
            if tol and abs(s['offset_hz']) > tol:
                lv['offset_hz'] = 'alarm'
            if s['am_pct'] >= PEAK_AM_PCT:  # peaks aren't judged above this, nor other rules above CLEAN_AM_PCT
                lv['am_pct'] = 'alarm' if s['am_pct'] >= CLEAN_AM_PCT else 'warn'
            if st.pilot and not lim['pilot_min_pct'] <= s['pilot_pct'] <= lim['pilot_max_pct']:
                lv['pilot_pct'] = 'alarm'
            if st.pilot_hz is not None and abs(st.pilot_hz - 19000) > lim['pilot_tol_hz']:
                lv['pilot_hz'] = 'alarm'
            for key in ('pos_pct', 'neg_pct'):
                if level := _level(s[key], 100, limit):
                    lv[key] = level
            for khz in (67, 92):
                kind = sca_kinds[khz] = self._sca_kind(khz, s)
                r[f'sca{khz}_pct'] = s[f'sca{khz}_pct']
                r[f'sca{khz}_kind'] = kind
                r[f'sca{khz}_baud'] = (st.sca_meter.kinds[khz] or (None, None))[1]
        self._measure_data_services(r, raw, sca_kinds, total)

        # audio
        a = st.audio_meter.stats
        r['has_audio'] = bool(a)
        if a:
            r.update({k: a[k] for k in ('mod_l', 'mod_r', 'mod_m', 'mod_s', 'momentary', 'short_term', 'integrated',
                                        'tp_l', 'tp_r', 'rms_l', 'rms_r', 'correlation', 'width_db')})
            r['balance_db'] = a['rms_l'] - a['rms_r'] if math.isfinite(a['rms_l'] + a['rms_r']) else 0.0
            for key in ('mod_l', 'mod_r', 'mod_m', 'mod_s'):
                if level := _level(a[key], 100, 110):
                    lv[key] = level
            if a['correlation'] < 0:
                lv['correlation'] = 'alarm'
        return r

    def _measure_data_services(self, r, raw, sca_kinds, total):
        """r['data_services']: the data services on air now, [{'key', 'group' (its
        group type, None for SCA data), 'share_pct' (of RDS groups, or None),
        'paging' (1A paging details for the paging service)}]; r['data_lost']: the
        steady services now missing (also self._data_lost)."""
        present = {k: g for k, (age, g) in raw['data'].items() if age <= DATA_GAP_S}
        for khz in (67, 92):
            if sca_kinds.get(khz) == 'data':
                present[f'SCA {khz} kHz data'] = None
                self._data_codes[f'SCA {khz} kHz data'] = f'SCA{khz}'
        self._data_codes.update((k, g) for k, g in present.items() if g)
        self._data_lost = r['data_lost'] = self.data_services.update(present)
        paging = [f'1A paging codes {raw["rp_codes"]:02X}'] if raw['rp_codes'] else []
        paging += [f'operator code {raw["opc"]}'] if raw['opc'] else []
        paging += [f'paging ID {raw["paging_id"]:03X}'] if raw['paging_id'] is not None else []
        r['data_services'] = [
            {'key': key, 'group': g, 'paging': paging if key == UNANNOUNCED_DATA[14] else [],
             'share_pct': raw['types'].get(g, 0) * 100 / total if g and total else None}
            for key, g in sorted(present.items())]

    def _show(self, r):
        """Put _measure()'s readings on the panel's labels and meters."""
        v, lv = self.values, r['levels']
        st = self.station
        if r['ps'] is not None:
            self.ps.setText(r['ps'])
        self.ps_mode.setVisible(r['ps_dynamic'])
        self.rt.setText(r['rt'])
        show = r['iboc_lines']
        for w in self._iboc_rows:
            if w.isHidden() == show:
                w.setVisible(show)
        for label, text in zip((self.iboc_line, self.psd_line, self.sis_line),
                               (self._iboc_line_text(r['iboc']), *self._psd_sis_text(r['iboc']))):
            label.setText(text)
            label.setToolTip(QtGui.QTextDocumentFragment.fromHtml(text).toPlainText() if text != '-' else '')
        self._update_media(r['pi'], r['ecc'])
        tags = [(f'<span style="color:{RED}">' if t == RTPLUS_ALARM else '<span>')
                + f'<span style="color:{DIM}">{_html(name)}:</span> {_html(text)}</span>'
                for t, name, text in r['rtplus']]
        self.rtplus.setText('   ·   '.join(tags) if tags else _flags_html(r['flags']) if r['flags'] else
                            f'<span style="color:{DIM}">no RDS</span>' if r['pi'] is None else '')
        v['PI'].setText('-' if r['pi'] is None else r['pi'])
        v['PTY'].setText('-' if r['pty'] is None else r['pty'])
        v['Flags'].setText(_flags_html(r['flags']))
        if r['clock']:  # RDS sends UTC and the local offset: show local time
            local, offset = r['clock']
            v['Clock'].setText(f'{local:%Y-%m-%d %H:%M} local (UTC{"-" if offset < 0 else "+"}'
                               f'{abs(offset) // 60}:{abs(offset) % 60:02d})')
        else:
            v['Clock'].setText('-')
        v['Alt. freqs'].setText(r['af'] or '-')
        v['PTYN'].setText(r['ptyn'] or '-')
        v['ECC'].setText('-' if r['ecc'] is None else f"{r['ecc']:02X}" if r['ecc'] else '00 (not set)')
        v['ODA'].setText(', '.join(r['oda']) or '-')
        v['Groups/s'].setText(f"{r['rds_rate']:.1f}")
        v['Group loss'].setText('-' if r['rds_loss_pct'] is None else f"{r['rds_loss_pct']:.0f}%")
        v['Group types'].setText('  '.join(f'{k} {pct:.0f}%' for k, pct in r['group_types'][:5]) or '-')

        if r['has_signal']:
            v['RF level'].setText(_num(r['rf_dbfs'], 'dBFS'))
            v['MPX S/N'].setText(_num(r['snr_db'], 'dB'))
            v['Carrier offset'].setText(_coloured(f"{r['offset_hz']:+.0f} Hz", lv.get('offset_hz')))
            am_text = f"{r['am_pct']:.1f}%"
            am_note = {'warn': '  peaks unreliable', 'alarm': '  readings unreliable'}.get(lv.get('am_pct'), '')
            v['AM / multipath'].setText(_coloured(am_text + am_note, lv.get('am_pct')))
            v['Pilot (19 kHz)'].setText(
                _coloured(f"{r['pilot_pct']:.1f}%", lv.get('pilot_pct')) + '  ' +
                {'stereo': 'stereo',
                 'forced mono': f'<span style="color:{AMBER}">mono (forced)</span>',
                 'mono': f'<span style="color:{DIM}">mono</span>'}[r['stereo_mode']])
            if r['pilot_hz'] is not None:
                err = r['pilot_hz'] - 19000
                v['Pilot freq'].setText(_coloured(f"{r['pilot_hz']:.1f} Hz ({err:+.1f})", lv.get('pilot_hz')))
            else:
                v['Pilot freq'].setText('-')
            v['RDS injection'].setText(f"{r['rds_pct']:.1f}%")
            v['RDS phase'].setText(_rds_phase_html(r['rds_phase_deg'], r['rds_phase_mode'], lv.get('rds_phase_deg')))
            v['Sync AM'].setText(_sync_am_html(r['sync_am_pct'], lv.get('sync_am_pct'), r['sync_am_multipath']))
            v['IBOC signal'].setText(self._iboc_text(r['iboc_found'], r['iboc_dbc']))
            for khz in (67, 92):
                pct = r[f'sca{khz}_pct']
                v[f'SCA {khz} kHz'].setText(
                    f'{pct:.1f}%  ' + self._sca_kind_html(r[f'sca{khz}_kind'], r[f'sca{khz}_baud']) if pct is not None
                    else f'<span style="color:{DIM}">none</span>')
            self._sca_sources({khz: {'kind': r[f'sca{khz}_kind']} for khz in (67, 92)})
            v['Peak + / −'].setText(f"+{_pct_html(r['pos_pct'], lv.get('pos_pct'))}"
                                    f" / −{_pct_html(r['neg_pct'], lv.get('neg_pct'))}")
            v['Limit'].setText(f"{r['limit_pct']:.1f}%  <span style=\"color:{DIM}\">({_html(r['limit_why'])})</span>")
            v['Peak deviation'].setText(f"{r['dev_khz']:.1f} kHz  ({r['dev_khz'] / 0.75:.0f}%)")
            v['Over 100%'].setText(f"{r['over100_min']} /min")
            v['Over 110%'].setText(f"{r['over110_min']} /min")
            window = '' if r['mpx_window_s'] >= MPX_POWER_S else f"  ({r['mpx_window_s']:.0f} s)"
            v['MPX power'].setText(_num(r['mpx_dbr'], 'dBr', '+.1f') + window)
            self.mpx.set_data(r['mpx_db'])
            self._show_tapes(r)
            self._show_detail_tapes(r)
            self.values['Limit'].setToolTip(r['limit_why'])
        self._collapse(r)
        rate = r['rds_rate']
        self.rds_note.setText('' if r['pi'] is None else f'{rate:.1f}/s' + (
            f" \u00b7 loss {r['rds_loss_pct']:.0f}%" if r['rds_loss_pct'] is not None else ''))

        parts = []
        for d in r['data_services']:
            text = self._service_label(d['key'], html=True)
            if d['paging']:
                text += f' <span style="color:{DIM}">({", ".join(d["paging"])})</span>'
            if d['share_pct'] is not None:
                text += f" {d['share_pct']:.0f}%"
            parts.append(text)
        parts += [f'<span style="color:{RED}">{self._service_label(k, html=True)} lost</span>' for k in r['data_lost']]
        v['Data services'].setText('  ·  '.join(parts) or '-')

        if r['has_audio']:
            v['L / R'].setText(f"{_pct_html(r['mod_l'], lv.get('mod_l'))} / {_pct_html(r['mod_r'], lv.get('mod_r'))}")
            v['L+R / L−R'].setText(f"{_pct_html(r['mod_m'], lv.get('mod_m'))} / {_pct_html(r['mod_s'], lv.get('mod_s'))}")
            v['Momentary'].setText(_num(r['momentary'], 'LUFS'))
            v['Short-term'].setText(_num(r['short_term'], 'LUFS'))
            v['Integrated'].setText(_num(r['integrated'], 'LUFS'))
            v['True peak L/R'].setText(f"{r['tp_l']:.1f} / {r['tp_r']:.1f} dBTP")
            v['Level L/R'].setText(f"{_num(r['rms_l'], '')}/ {_num(r['rms_r'], 'dB')}")
            bal = r['balance_db']
            v['Balance'].setText('centre' if abs(bal) < 0.5 else
                                 f"{abs(bal):.1f} dB {'L' if bal > 0 else 'R'}")
            corr = r['correlation']
            v['Correlation'].setText(_coloured(f'{corr:+.2f}', lv.get('correlation')))
            v['Width (S/M)'].setText('mono' if not math.isfinite(r['width_db']) or r['width_db'] < -40
                                     else _num(r['width_db'], 'dB'))
            self.meters['corr'].set_value(corr, f'{corr:+.2f}')
        if st.audio_meter.scope is not None:
            self.gonio.set_data(st.audio_meter.scope)
        if self._stereo and self._stereo.isVisible():
            self._stereo.follow(self)

    def _show_tapes(self, r):
        """The station row's tapes: peak modulation against the limit in force, RF, AM."""
        lv = r['levels']
        peak = max(r['pos_pct'], r['neg_pct'])
        mod_state = lv.get('pos_pct') if r['pos_pct'] >= r['neg_pct'] else lv.get('neg_pct')
        if mod_state == 'alarm' and lv.get('am_pct'):
            mod_state = 'warn'   # over the limit, but multipath: not judged
        self.tapes['mod'].set_value(peak, f"+{r['pos_pct']:.0f} / −{r['neg_pct']:.0f}%", mod_state,
                                    limit=r['limit_pct'], band=(85, r['limit_pct']))
        self.tapes['mod'].setToolTip(f"Peak modulation +{r['pos_pct']:.0f}% / −{r['neg_pct']:.0f}% "
                                     f"({r['dev_khz']:.1f} kHz); limit {r['limit_pct']:.1f}% ({r['limit_why']}). "
                                     'Tick: 2 s peak hold; grey band: the normal range')
        self.tapes['rf'].set_value(r['rf_dbfs'], _num(r['rf_dbfs'], 'dBFS', '.0f'),
                                   'alarm' if r['rf_dbfs'] < -75 else None)
        self.tapes['rf'].setToolTip(f"RF level {_num(r['rf_dbfs'], 'dBFS')}, MPX S/N {_num(r['snr_db'], 'dB')}")
        self.tapes['am'].set_value(r['am_pct'], f"{r['am_pct']:.1f}%", lv.get('am_pct'))

    def _show_detail_tapes(self, r):
        lv = r['levels']
        lim = r['limit_pct']
        for key in ('pos', 'neg'):
            pct = r[f'{key}_pct']
            state = lv.get(f'{key}_pct')
            if state == 'alarm' and lv.get('am_pct'):
                state = 'warn'
            self.peak_tapes[key].set_value(pct, f"{pct:.0f}%  {pct * 0.75:.1f} kHz", state, limit=lim, band=(85, lim))
        self.limit_note.setText(f'limit {lim:.1f}% \u24d8')
        self.limit_note.setToolTip(f"Over-modulation limit in force: {r['limit_why']}")
        snr = r['snr_db']
        self.mpx_tapes['snr'].set_value(snr, _num(snr, 'dB'), 'alarm' if snr < self.settings.min_snr_db else None)
        lim_ = r['limits']
        if r['stereo_mode'] == 'mono':
            self.mpx_tapes['pilot'].set_value(None, 'none (mono)')
        else:
            self.mpx_tapes['pilot'].set_value(r['pilot_pct'], f"{r['pilot_pct']:.1f}%  {r['stereo_mode']}",
                                              lv.get('pilot_pct'), band=(lim_['pilot_min_pct'], lim_['pilot_max_pct']))
        tol = lim_['freq_tol_hz']
        off = self.mpx_tapes['offset']
        off.lo, off.hi = -3 * tol, 3 * tol
        off.set_value(r['offset_hz'], f"{r['offset_hz']:+.0f} Hz", lv.get('offset_hz'), band=(-tol, tol))

    def _collapse(self, r):
        """Hide the readouts a station doesn't carry, listing them once instead."""
        rds, mpx = [], []
        if r['pi'] is None:
            rds = ['PI', 'PTY', 'PTYN', 'ECC', 'Group loss', 'Flags', 'ODA', 'Alt. freqs', 'Clock', 'Group types',
                   'Data services']
        else:
            rds = [n for n, gone in (('PTYN', not r['ptyn']), ('ECC', r['ecc'] is None), ('ODA', not r['oda']),
                                     ('Alt. freqs', not r['af']), ('Clock', not r['clock']),
                                     ('Data services', not r['data_services'] and not r['data_lost'])) if gone]
        if r['has_signal']:
            mpx = [n for n, gone in (('Pilot freq', r['pilot_hz'] is None), ('RDS injection', r['pi'] is None),
                                     ('RDS phase', r['rds_phase_mode'] is None), ('Sync AM', r['sync_am_pct'] is None),
                                     ('SCA 67 kHz', r['sca67_pct'] is None), ('SCA 92 kHz', r['sca92_pct'] is None),
                                     ('IBOC signal', r['iboc_found'] != 'detected')) if gone]
        hidden = set(rds) | set(mpx)
        for name, widgets in self._kv_rows.items():
            for w in widgets:
                if w.isHidden() != (name in hidden):
                    w.setVisible(name not in hidden)
        short = {'SCA 67 kHz': 'SCA 67', 'SCA 92 kHz': 'SCA 92', 'IBOC signal': 'IBOC', 'RDS injection': 'RDS',
                 'Pilot freq': 'pilot', 'RDS phase': 'RDS phase', 'Sync AM': 'sync AM'}
        on_air = [short[n] for n in mpx if n in ('SCA 67 kHz', 'SCA 92 kHz', 'IBOC signal', 'RDS injection')]
        self.absent['mpx'].setText('Not on air: ' + ' \u00b7 '.join(on_air) if on_air else '')
        self.absent['mpx'].setVisible(bool(on_air))
        self.absent['rds'].setText('No RDS decoded' if r['pi'] is None else
                                   'Not sent: ' + ' \u00b7 '.join(rds) if rds else '')
        self.absent['rds'].setVisible(bool(rds))

    def _meta_text(self, r):
        """The row's second line: PI, PTY, RDS rate, stereo, receiver number."""
        parts = [f"<b style=\"color:#e3e4e6\">{r['pi']}</b>" if r['pi'] else 'no RDS']
        if r['pi']:
            if r['pty']:
                parts.append(_html(r['pty']))
            parts.append(f"RDS {r['rds_rate']:.1f}/s")
        if r.get('stereo_mode'):
            parts.append(r['stereo_mode'])
        parts.append(f'Rx {self.slot + 1}' + (f' {_html(self.settings.name)}' if self.settings.name else ''))
        return ' · '.join(parts)

    def _alarm_states(self, conditions, clean):
        """{alarm: state} for an annunciator: 'off' (switched off for this receiver),
        'raised', 'waiting' (not judged yet: grace period after tuning, or no
        readings), 'suppressed' (not judged now: reception not clean enough for the
        technical rules), 'pending' (its condition holds, its delay is running) or 'clear'."""
        out = {}
        pending = self.alarms.pending()
        for name, *_ in ALARM_DEFS:
            if not self.settings.alarms.get(name, True):
                out[name] = 'off'
            elif name in self.alarms.active:
                out[name] = 'raised'
            elif conditions is None or not self.alarms.ready():
                out[name] = 'waiting'
            elif name in JUDGED_CLEAN and not clean:
                out[name] = 'suppressed'
            elif name in pending:
                out[name] = 'pending'
            else:
                out[name] = 'clear'
        return out

    def refresh(self):
        """Measure, update every readout and the history; returns alarm changes
        as [(description, raised, details), ...]."""
        self.readings = r = self._measure()
        self._show(r)
        st = self.station
        f = st.rds.fields
        s, a = st.meter.stats, st.audio_meter.stats
        rate = r['rds_rate']

        changes = []
        conditions, clean = None, False
        if s and a:
            cfg = self.settings
            carrier = s['rf_dbfs'] < -75 or s['snr_db'] < cfg.min_snr_db
            if self.alarms.ready():
                self.alarms.seen_pilot |= st.pilot
                self.alarms.seen_rds |= rate > 5
            pi = f.get(0, '').strip().upper()
            # Multipath and noise spikes look like over-modulation (and upset the
            # other readings); only judge the technical rules on clean reception,
            # and peaks only on reception clean enough for them (ITU-R SM.1268).
            clean = not carrier and s['am_pct'] < CLEAN_AM_PCT and s['snr_db'] > 25
            peaks_clean = clean and s['am_max_pct'] < PEAK_AM_PCT
            rules = self.rules()
            lim = cfg.limits(self.country)
            limit, _ = mod_limit(rules, lim, s)
            tol = lim['freq_tol_hz']
            subcarriers = (s['rds_pct'] or 0.0) + sum(s[f'sca{k}_pct'] or 0.0 for k in (67, 92))
            silent = not carrier and a['momentary'] < cfg.silence_lufs
            rds_lost, backup = rds_conditions(self.alarms.seen_rds, rate, carrier,
                                              st.pilot or not self.alarms.seen_pilot, silent,
                                              cfg.alarms.get('BACKUP', True))
            conditions = {
                'CARRIER': carrier,
                'SILENCE': silent,
                'OVERMOD': (peaks_clean and max(s['pos_pct'], s['neg_pct']) > limit),
                'PILOT_SPEC': (clean and st.pilot and (not lim['pilot_min_pct'] <= s['pilot_pct'] <= lim['pilot_max_pct']
                                                       or (st.pilot_hz is not None
                                                           and abs(st.pilot_hz - 19000) > lim['pilot_tol_hz']))),
                'SUBCARRIERS': (clean and (subcarriers > lim['sub_total_pct']
                                           or (s['sca92_pct'] or 0.0) > lim['sub_high_pct'])),
                'FREQUENCY': bool(clean and tol and abs(s['offset_hz']) > tol),
                'PILOT': self.alarms.seen_pilot and not st.pilot,
                'RDS': rds_lost,
                'BACKUP': backup,
                'PI': bool(cfg.expected_pi and pi and pi != cfg.expected_pi),
                'ALERT': bool(st.iboc and st.iboc.status['alert']) or bool(self._rt_alarm),
                # RDS services only while RDS itself is fine (else the RDS alarm says it)
                'DATA': not carrier and any(k.startswith('SCA') or rate > 5 for k in self._data_lost),
            }
            changes = self.alarms.update({k: v and cfg.alarms.get(k, True) for k, v in conditions.items()},
                                         holds={'SILENCE': cfg.silence_s})
            if changes:
                for name, _, raised in changes:
                    self.history.log_alarm(time.time(), name, raised)
                details = self._alarm_details(s, a, lim, limit, subcarriers, rate, pi)
                changes = [(desc, raised, details.get(name, '')) for name, desc, raised in changes]
        r['alarms'] = self._alarm_states(conditions, clean)
        self.history.add(time.time(), r)
        if time.monotonic() - self._trend_t >= TREND_S:
            self._trend_t = time.monotonic()
            self._show_trends(r)
        feed = ''
        if self.feed:
            n = self.feed.clients
            feed = f' \u00b7 RDS feed TCP {self.feed.port} \u00b7 {n} client{"" if n == 1 else "s"}'
        name = f' \u00b7 {self.settings.name}' if self.settings.name else ''
        self.feed_label.setText(f'Receiver {self.slot + 1}{name}{feed}')
        self.meta.setText(self._meta_text(r))
        self.meta.setToolTip(self.feed_label.text())
        self.detail_title.setText(self.title)
        ecc = r['ecc']
        sub = [f"PI {r['pi']}" if r['pi'] else 'no RDS', _html(r['pty'] or '') if r['pi'] else '',
               f'ECC {ecc:02X}' if ecc else '', f"{RULES[self.rules()]['name'] if self.rules() in RULES else 'custom'} rules"]
        self.detail_sub.setText(' \u00b7 '.join(x for x in sub if x))
        if self.window:
            self.window.setWindowTitle(f'{self.title} \u2013 {APP_NAME}')
        if self.rt.toolTip() != r['rt']:
            self.rt.setToolTip(r['rt'])
        self.annunciator.set_states(r['alarms'], self._alarm_notes(r))
        return changes

    def trends(self, n=88):
        """The last TREND_SPAN_S, bucketed for sparklines: {'peak', 'rds_rate', 'short_term'}
        (n points each, NaN where there was no reading), 'peaks' (every update's peak),
        and 'over100' (updates over 100% in the last minute, as a count per minute)."""
        h = self.history
        t, pos = h.series('pos_pct', TREND_SPAN_S)
        _, neg = h.series('neg_pct', TREND_SPAN_S)
        with np.errstate(invalid='ignore'):
            peaks = np.fmax(pos, neg)
        end = t[-1] if len(t) else None
        return {'peak': bucket(t, peaks, TREND_SPAN_S, n, True, end),
                'rds_rate': bucket(*h.series('rds_rate', TREND_SPAN_S), TREND_SPAN_S, n, False, end),
                'short_term': bucket(*h.series('short_term', TREND_SPAN_S), TREND_SPAN_S, n, False, end),
                'peaks': peaks[np.isfinite(peaks)]}

    def _show_trends(self, r):
        tr = self.trends(max(self.spark.width() // 2, 40))
        limit = r.get('limit_pct')
        edges = np.arange(PeakHistogram.LO, PeakHistogram.HI + PeakHistogram.STEP, PeakHistogram.STEP)
        self.web_trends = {k: _Finite(np.round(np.nan_to_num(tr[k], nan=-999.0), 1).tolist())
                           for k in ('peak', 'rds_rate', 'short_term')}
        self.web_trends['hist'] = (np.histogram(np.clip(tr['peaks'], edges[0], edges[-1] - 1e-6), edges)[0].tolist()
                                   if len(tr['peaks']) else [])
        self.spark.set_data(tr['peak'], limit, AMBER if r.get('alarms', {}).get('OVERMOD') == 'suppressed' else RED)
        over = r.get('over100_min')
        self.trend_note.setText('peak modulation' + ('' if over is None else
                                                     f' \u00b7 {over}/min over 100%' if not over else
                                                     f' \u00b7 <b style="color:{AMBER}">{over}/min over 100%</b>'))
        if self.history_view.isVisible():
            self.history_view.refresh()
        if self.detail.isVisible():
            self.peak_hist.set_data(tr['peaks'], limit)
            self.rds_spark.set_data(tr['rds_rate'])
            self.lufs_spark.set_data(tr['short_term'])

    def _alarm_notes(self, r):
        """Why an alarm isn't judged now, for the annunciator's tooltips."""
        if not r.get('has_signal'):
            return {}
        why = (f"AM / multipath {r['am_pct']:.1f}%, S/N {_num(r['snr_db'], 'dB', '.0f')}"
               f" (judged under {CLEAN_AM_PCT:g}% AM and over 25 dB S/N; over-modulation under {PEAK_AM_PCT:g}%)")
        notes = {name: why for name, state in r['alarms'].items() if state == 'suppressed'}
        if r['alarms'].get('OVERMOD') in ('raised', 'pending', 'clear'):
            notes['OVERMOD'] = f"peak +{r['pos_pct']:.0f}% / \u2212{r['neg_pct']:.0f}%, limit {r['limit_pct']:.1f}%"
        return notes

    def _service_label(self, key, html=False):
        """A data service as shown: the name this receiver gives it, with what it is."""
        name = parse_service_names(self.settings.service_names).get(self._data_codes.get(key, ''))
        if not html:
            return f'{name} ({key})' if name else key
        return f'{_html(name)} <span style="color:{DIM}">{_html(key)}</span>' if name else _html(key)

    def _alarm_details(self, s, a, lim, limit, subcarriers, rate, pi):
        """What each alarm measured, against its limit, for the event log and notifications."""
        st, cfg = self.station, self.settings
        num = lambda v, fmt='.1f': format(v, fmt) if v is not None and math.isfinite(v) else '-'  # noqa: E731
        pilot_hz = f' at {num(st.pilot_hz)} Hz' if st.pilot_hz is not None else ''
        sca = ', '.join(f'SCA {k} {num(s[f"sca{k}_pct"])}%' for k in (67, 92) if s[f'sca{k}_pct'])
        return {
            'CARRIER': f'RF {num(s["rf_dbfs"])} dBFS, S/N {num(s["snr_db"])} dB '
                       f'(alarm below {cfg.min_snr_db:g} dB S/N or -75 dBFS)',
            'SILENCE': f'momentary loudness {num(a["momentary"])} LUFS '
                       f'(alarm below {cfg.silence_lufs:g} LUFS for {cfg.silence_s} s)',
            'OVERMOD': f'peak +{num(s["pos_pct"])}% / -{num(s["neg_pct"])}%, limit {num(limit)}%',
            'PILOT_SPEC': f'pilot {num(s["pilot_pct"])}%{pilot_hz} (allowed {lim["pilot_min_pct"]:g}-'
                          f'{lim["pilot_max_pct"]:g}%, 19000 +/- {lim["pilot_tol_hz"]:g} Hz)',
            'SUBCARRIERS': f'subcarriers {num(subcarriers)}% total (RDS {num(s["rds_pct"])}%'
                           + (f', {sca}' if sca else '') + f'; limits {lim["sub_total_pct"]:g}% total, '
                           f'{lim["sub_high_pct"]:g}% above 75 kHz)',
            'FREQUENCY': f'carrier offset {num(s["offset_hz"], "+.0f")} Hz (tolerance +/- {lim["freq_tol_hz"]:g} Hz, '
                         'includes the tuning error of the SDR)',
            'PILOT': f'pilot {num(s["pilot_pct"])}%',
            'RDS': f'RDS {num(rate)} groups/s',
            'BACKUP': f'RDS {num(rate)} groups/s while carrier, pilot ({num(s["pilot_pct"])}%) and audio '
                      f'({num(a["momentary"])} LUFS) are fine: the N+1 backup transmitter has no RDS encoder',
            'PI': f'PI {pi or "-"}, expected {cfg.expected_pi}',
            'ALERT': f'RT+ Alarm: {self._rt_alarm}' if self._rt_alarm else '',
            'DATA': (f'not on air for {DATA_GAP_S:.0f}+ s: {", ".join(map(self._service_label, self._data_lost))}'
                     if self._data_lost else ''),
        }

    def web_readings(self):
        """self.readings as plain JSON values for the web page, which draws the
        rows and the detail from them as the window does."""
        r = {k: v for k, v in self.readings.items() if k != 'mpx_db'}
        if r.get('clock'):
            local, offset = r['clock']
            r['clock'] = [local.strftime('%Y-%m-%d %H:%M'), offset]
        r['data_services'] = [dict(d, label=self._service_label(d['key'])) for d in r.get('data_services', [])]
        r['data_lost'] = [self._service_label(k) for k in r.get('data_lost', [])]
        r['radiodns'] = (QtGui.QTextDocumentFragment.fromHtml(self.rdns_line.text()).toPlainText()
                         if self._rdns_working else '')
        r['rules_name'] = RULES[self.rules()]['name'] if self.rules() in RULES else 'custom'
        return r

    def web_state(self, feed_port, default_port, listeners):
        """Everything the web page shows for this receiver, as plain JSON values:
        the readings, alarm states and trends (the page formats and draws them),
        and the controls' lists."""
        st = self.station
        scope = st.audio_meter.scope
        mpx = self.readings.get('mpx_db')

        def items(combo):
            return [{'value': combo.itemData(i), 'label': combo.itemText(i),
                     'enabled': combo.model().item(i).isEnabled(),
                     'tip': combo.itemData(i, QtCore.Qt.ToolTipRole) or combo.model().item(i).toolTip() or ''}
                    for i in range(combo.count())]

        if self._web_lists is None:
            self._web_lists = items(self.combo), items(self.source)
        stations, sources = self._web_lists
        return {
            'receiver': self.slot + 1, 'freq': st.freq_hz, 'title': self.title, 'name': self.settings.name,
            'readings': self.web_readings(), 'notes': self._alarm_notes(self.readings) if self.readings else {},
            'trends': self.web_trends,
            'mpx': None if mpx is None else _Finite(np.round(np.nan_to_num(mpx), 1).tolist()),
            'gonio': None if scope is None else [_Finite(np.round(np.nan_to_num(x[-400::2]), 4).tolist()) for x in scope],
            'status': self.feed_label.text(),
            'stations': stations,
            'source': self.source_key(), 'sources': sources,
            'removable': self.remove_btn.isEnabled(),
            'settings': self.settings.to_dict(), 'feed_port': feed_port, 'default_port': default_port,
            'images': {kind: (f'{abs(hash(label.path)):x}' if label.path and not label.isHidden() else None)
                       for kind, label in (('logo', self.logo_img), ('art', self.art_img))},
            'art_link': self.art_img.link if not self.art_img.isHidden() else None,
            'listeners': listeners,
        }


class NotifyForm(QtWidgets.QWidget):
    """Notification settings (email, webhook, which events) with a test send;
    in Settings and the setup wizard. The SMTP password typed here is stored
    (Windows Credential Manager) only by save_password()."""

    def __init__(self, settings, notifier, parent=None):
        super().__init__(parent)
        self.notifier = notifier
        form = QtWidgets.QVBoxLayout(self)
        form.setContentsMargins(0, 0, 0, 0)

        mail = QtWidgets.QGroupBox('Email (SMTP)')
        mail.setCheckable(True)
        mail.setChecked(settings.email)
        mf = QtWidgets.QFormLayout(mail)
        self.mail = mail
        self.smtp_host = QtWidgets.QLineEdit(settings.smtp_host)
        self.smtp_host.setPlaceholderText('e.g. smtp.office365.com')
        self.smtp_port = QtWidgets.QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(settings.smtp_port)
        self.smtp_security = QtWidgets.QComboBox()
        for key, label in (('starttls', 'STARTTLS (port 587)'), ('ssl', 'SSL/TLS (port 465)'), ('none', 'None (port 25)')):
            self.smtp_security.addItem(label, key)
        self.smtp_security.setCurrentIndex(self.smtp_security.findData(settings.smtp_security))
        self.smtp_security.currentIndexChanged.connect(self._security_port)
        server = QtWidgets.QHBoxLayout()
        server.addWidget(self.smtp_host, 1)
        server.addWidget(QtWidgets.QLabel('port'))
        server.addWidget(self.smtp_port)
        mf.addRow('Server:', server)
        mf.addRow('Security:', self.smtp_security)
        self.smtp_user = QtWidgets.QLineEdit(settings.smtp_user)
        self.smtp_user.setPlaceholderText('optional: sign-in name')
        mf.addRow('User name:', self.smtp_user)
        self._stored = credential_read(SMTP_CREDENTIAL) is not None
        self._forget = False
        self.smtp_password = QtWidgets.QLineEdit()
        self.smtp_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.smtp_password.setPlaceholderText('stored (type to change)' if self._stored else 'sign-in password')
        self.forget_btn = QtWidgets.QPushButton('Forget')
        self.forget_btn.setToolTip('Remove the stored SMTP password')
        self.forget_btn.setEnabled(self._stored)
        self.forget_btn.clicked.connect(self._forget_password)
        pw_row = QtWidgets.QHBoxLayout()
        pw_row.addWidget(self.smtp_password, 1)
        pw_row.addWidget(self.forget_btn)
        mf.addRow('Password:', pw_row)
        note = ('Kept in Windows Credential Manager, never in the settings file.'
                if os.name == 'nt' else 'Set FM_MODMON_SMTP_PASSWORD (it can only be stored on Windows).')
        if os.environ.get('FM_MODMON_SMTP_PASSWORD'):
            note += ' FM_MODMON_SMTP_PASSWORD is set, and is used instead.'
        note = QtWidgets.QLabel(note)
        note.setWordWrap(True)
        note.setStyleSheet(f'color: {DIM};')
        mf.addRow('', note)
        self.email_from = QtWidgets.QLineEdit(settings.email_from)
        self.email_from.setPlaceholderText('sender address (default: the user name)')
        mf.addRow('From:', self.email_from)
        self.email_to = QtWidgets.QLineEdit(settings.email_to)
        self.email_to.setPlaceholderText('one or more addresses, separated by commas')
        mf.addRow('To:', self.email_to)
        mail_test = QtWidgets.QHBoxLayout()
        self.mail_test_btn = QtWidgets.QPushButton('Send test email')
        self.mail_test_btn.setToolTip('Send a test message to the addresses above with these settings')
        self.mail_test_btn.clicked.connect(lambda: self._test('email'))
        self.mail_test_result = QtWidgets.QLabel('')
        self.mail_test_result.setWordWrap(True)
        mail_test.addWidget(self.mail_test_btn)
        mail_test.addWidget(self.mail_test_result, 1)
        mf.addRow('', mail_test)
        form.addWidget(mail)

        hook = QtWidgets.QGroupBox('Webhook')
        hook.setCheckable(True)
        hook.setChecked(settings.webhook)
        hf = QtWidgets.QFormLayout(hook)
        self.hook = hook
        self.webhook_url = QtWidgets.QLineEdit(settings.webhook_url)
        self.webhook_url.setPlaceholderText('https://...')
        hf.addRow('URL:', self.webhook_url)
        self.webhook_format = QtWidgets.QComboBox()
        for key, label in (('json', 'Generic JSON'), ('slack', 'Slack'), ('teams', 'Microsoft Teams (workflow)'),
                           ('discord', 'Discord')):
            self.webhook_format.addItem(label, key)
        self.webhook_format.setCurrentIndex(self.webhook_format.findData(settings.webhook_format))
        hf.addRow('Format:', self.webhook_format)
        form.addWidget(hook)

        events = QtWidgets.QGroupBox('Send')
        ef = QtWidgets.QHBoxLayout(events)
        self.events = {}
        for key, label in (('on_raise', 'Alarms raised'), ('on_clear', 'Alarms cleared'),
                           ('on_sdr', 'SDR lost / recovered'), ('on_start_stop', 'Start / stop')):
            box = QtWidgets.QCheckBox(label)
            box.setChecked(getattr(settings, key))
            ef.addWidget(box)
            self.events[key] = box
        ef.addStretch(1)
        form.addWidget(events)

        test_row = QtWidgets.QHBoxLayout()
        self.test_btn = QtWidgets.QPushButton('Send test')
        self.test_btn.clicked.connect(lambda: self._test(None))
        self.test_result = QtWidgets.QLabel('')
        self.test_result.setWordWrap(True)
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_result, 1)
        form.addLayout(test_row)
        self._test_job = None       # {'button', 'label', 'result'} while a test is out
        self._poll = QtCore.QTimer(self)
        self._poll.timeout.connect(self._test_done)

    def _security_port(self):
        default = {'starttls': 587, 'ssl': 465, 'none': 25}
        if self.smtp_port.value() in default.values():
            self.smtp_port.setValue(default[self.smtp_security.currentData()])

    def _forget_password(self):
        self._forget = True
        self.smtp_password.clear()
        self.smtp_password.setPlaceholderText('will be forgotten (type to set a new one)')
        self.forget_btn.setEnabled(False)

    def settings(self):
        return NotifySettings.from_dict({
            'email': self.mail.isChecked(), 'smtp_host': self.smtp_host.text().strip(),
            'smtp_port': self.smtp_port.value(), 'smtp_security': self.smtp_security.currentData(),
            'smtp_user': self.smtp_user.text().strip(), 'email_from': self.email_from.text().strip(),
            'email_to': self.email_to.text().strip(),
            'webhook': self.hook.isChecked(), 'webhook_url': self.webhook_url.text().strip(),
            'webhook_format': self.webhook_format.currentData(),
            **{key: box.isChecked() for key, box in self.events.items()}})

    def have_password(self):
        """Whether there will be an SMTP password once this form is saved."""
        return bool(self.smtp_password.text() or os.environ.get('FM_MODMON_SMTP_PASSWORD')
                    or (self._stored and not self._forget))

    def problems(self):
        return self.settings().problems(self.have_password())

    def save_password(self):
        """Store (or forget) the SMTP password as typed; raises OSError if it can't be stored."""
        if self.smtp_password.text():
            credential_write(SMTP_CREDENTIAL, self.smtp_password.text(), self.smtp_user.text().strip())
        elif self._forget:
            credential_delete(SMTP_CREDENTIAL)

    def _test(self, channel):
        """Send a test: channel 'email' (the button in the SMTP box) or None (every channel turned on)."""
        if self._test_job:
            return                  # one test at a time
        button, label = ((self.mail_test_btn, self.mail_test_result) if channel == 'email'
                         else (self.test_btn, self.test_result))
        new = self.settings()
        if channel == 'email':
            new = NotifySettings.from_dict({**new.to_dict(), 'email': True, 'webhook': False})
        problems = new.problems(self.have_password())
        if not (new.email or new.webhook):
            problems.append('turn on email and / or the webhook first')
        if problems:
            label.setText('\n'.join(problems))
            label.setStyleSheet(f'color: {RED};')
            return
        button.setEnabled(False)
        label.setStyleSheet(f'color: {DIM};')
        label.setText('sending…')
        job = self._test_job = {'button': button, 'label': label}
        typed = self.smtp_password.text() or None
        threading.Thread(target=lambda: job.update(result=self.notifier.test(new, typed)), daemon=True).start()
        self._poll.start(200)

    def _test_done(self):
        job = self._test_job
        if not job or 'result' not in job:
            return
        self._poll.stop()
        self._test_job = None
        job['button'].setEnabled(True)
        ok = all(err is None for _, err in job['result'])
        if job['button'] is self.mail_test_btn:
            err = job['result'][0][1] if job['result'] else 'not sent'
            reply = self.notifier.last_reply.get('email')
            text = (f'accepted for {", ".join(self.settings().recipients())}'
                    + (f'\nserver: {reply}' if reply else '')) if err is None else err
            job['label'].setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)  # copy the queue ID
        else:
            text = '\n'.join(f'{name}: {"sent" if err is None else err}' for name, err in job['result'])
        job['label'].setText(text)
        job['label'].setStyleSheet(f'color: {GREEN if ok else RED};')


class AppSettingsDialog(QtWidgets.QDialog):
    """Notifications (email, webhook, which events) and start with Windows;
    "Run setup again" closes it with RUN_SETUP for the setup wizard."""

    RUN_SETUP = 2

    def __init__(self, parent, settings, notifier):
        super().__init__(parent)
        self.setWindowTitle(f'{APP_NAME} settings')
        self.setMinimumWidth(600)
        layout = QtWidgets.QVBoxLayout(self)
        self.form = NotifyForm(settings, notifier)
        layout.addWidget(self.form)
        self.autostart = QtWidgets.QCheckBox('Start FM-Modmon-ms when I sign in to Windows')
        self.autostart.setChecked(autostart_enabled())
        layout.addWidget(self.autostart)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        setup = buttons.addButton('Run setup again…', QtWidgets.QDialogButtonBox.ResetRole)
        setup.setToolTip('Location and rules, web access and its password, notifications')
        setup.clicked.connect(lambda: self.done(self.RUN_SETUP))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self):
        return self.form.settings()

    def _accept(self):
        problems = self.form.problems()
        if problems:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), '\n'.join(problems))
            return
        try:
            self.form.save_password()
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), f'The SMTP password was not stored: {e}')
            return
        self.accept()


class _WizardPage(QtWidgets.QWizardPage):
    """A setup page; `check` returns an error to show, or None to go on."""

    def __init__(self, title, subtitle='', check=None):
        super().__init__()
        self.setTitle(title)
        self.setSubTitle(subtitle)
        self._check = check
        self.body = QtWidgets.QVBoxLayout(self)

    def validatePage(self):
        err = self._check() if self._check else None
        if err:
            QtWidgets.QMessageBox.warning(self, self.wizard().windowTitle(), err)
            return False
        return True


class SetupWizard(QtWidgets.QWizard):
    """Setup, at the first start (or --setup, or from Settings): where the monitor is
    (the alarm rules), the web version and its password, notifications, and
    starting with Windows. Read the results with app_config(), notify_settings()
    and autostart(); secrets are stored when Finish is clicked."""

    COUNTRIES = (('CA', 'Canada', 'ISED rules (BETS-6, BPR-3)'),
                 ('US', 'United States', 'FCC rules (47 CFR 73)'))

    def __init__(self, parent, app_cfg, notify, notifier, first_run=True):
        super().__init__(parent)
        self.setWindowTitle(f'{APP_NAME} setup')
        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        self.setOption(QtWidgets.QWizard.NoBackButtonOnStartPage)
        self.setMinimumSize(720, 640)
        self.cfg = app_cfg
        self.first_run = first_run
        self.addPage(self._welcome())
        self.addPage(self._location())
        self.addPage(self._web())
        self.addPage(self._notifications(notify, notifier))
        self.addPage(self._finish())

    @staticmethod
    def _note(text):
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f'color: {DIM};')
        return label

    def _welcome(self):
        page = _WizardPage(f'Welcome to {APP_NAME}' if self.first_run else f'{APP_NAME} setup',
                           'Multi-station FM modulation monitor')
        text = QtWidgets.QLabel(
            f'{APP_NAME} monitors up to four FM stations at once from one SDRplay RSP1A: modulation, '
            'pilot, RDS, subcarriers, loudness and stereo, with alarms on the technical rules.\n\n'
            'This setup takes a minute:\n'
            '    •  where the monitor is (which rules the alarms check)\n'
            '    •  the web version, and the password for its controls\n'
            '    •  where alarms are sent (email, webhook)\n'
            '    •  starting with Windows\n\n'
            + ('Everything can be changed later: Settings > Run setup again. Cancel keeps the defaults.'
               if self.first_run else 'Cancel leaves everything as it is.'))
        text.setWordWrap(True)
        page.body.addWidget(text)
        page.body.addStretch(1)
        return page

    def _location(self):
        page = _WizardPage('Where is the monitor?',
                           'The country sets the technical rules the alarms check (every limit can still be '
                           "adjusted per receiver), and tells RadioDNS where you are when a station sends no ECC.",
                           self._check_country)
        self.country_buttons = {}
        group = QtWidgets.QButtonGroup(page)
        for code, name, rules in self.COUNTRIES:
            button = QtWidgets.QRadioButton(f'{name} — {rules}')
            group.addButton(button)
            page.body.addWidget(button)
            self.country_buttons[code] = button
        other_row = QtWidgets.QHBoxLayout()
        self.country_other = QtWidgets.QRadioButton('Elsewhere — FCC limits; ISO country code:')
        group.addButton(self.country_other)
        self.country_code = QtWidgets.QLineEdit()
        self.country_code.setMaxLength(2)
        self.country_code.setFixedWidth(48)
        self.country_code.setPlaceholderText('GB')
        self.country_code.textEdited.connect(lambda: self.country_other.setChecked(True))
        other_row.addWidget(self.country_other)
        other_row.addWidget(self.country_code)
        other_row.addStretch(1)
        page.body.addLayout(other_row)
        if self.cfg.country in self.country_buttons:
            self.country_buttons[self.cfg.country].setChecked(True)
        else:
            self.country_other.setChecked(True)
            self.country_code.setText(self.cfg.country)
        page.body.addSpacing(12)
        page.body.addWidget(self._note('The band scan uses the North American 200 kHz channel raster '
                                       '(88.1–107.9 MHz).'))
        page.body.addStretch(1)
        return page

    def country(self):
        for code, button in self.country_buttons.items():
            if button.isChecked():
                return code
        return self.country_code.text().strip().upper()

    def _check_country(self):
        if not re.fullmatch(r'[A-Z]{2}', self.country()):
            return 'Enter the two-letter ISO country code (such as GB or MX).'
        return None

    def _web(self):
        page = _WizardPage('Web version',
                           'The same panels in a browser, with each station’s audio. Anyone who can open '
                           'the page can watch and listen; changing anything needs the password.',
                           self._check_web)
        self.web_on = QtWidgets.QGroupBox('Serve the web version')
        self.web_on.setCheckable(True)
        self.web_on.setChecked(bool(self.cfg.web_port))
        wf = QtWidgets.QFormLayout(self.web_on)
        self.web_port = QtWidgets.QSpinBox()
        self.web_port.setRange(1024, 65535)
        self.web_port.setValue(self.cfg.web_port or WEB_PORT)
        wf.addRow('Port:', self.web_port)
        self.web_local = QtWidgets.QRadioButton('This PC only (http://localhost)')
        self.web_network = QtWidgets.QRadioButton('Other computers on the network too')
        (self.web_local if self.cfg.web_bind == '127.0.0.1' else self.web_network).setChecked(True)
        reach = QtWidgets.QVBoxLayout()
        reach.addWidget(self.web_network)
        reach.addWidget(self.web_local)
        wf.addRow('Open to:', reach)
        self.web_pw = QtWidgets.QLineEdit()
        self.web_pw2 = QtWidgets.QLineEdit()
        for edit in (self.web_pw, self.web_pw2):
            edit.setEchoMode(QtWidgets.QLineEdit.Password)
        had = bool(self.cfg.web_password_hash)
        self.web_pw.setPlaceholderText('set (type to change)' if had else f'at least {MIN_WEB_PASSWORD} characters')
        self.web_pw2.setPlaceholderText('the same again')
        wf.addRow('Password:', self.web_pw)
        wf.addRow('Confirm:', self.web_pw2)
        self.web_pw_remove = QtWidgets.QCheckBox('Remove the password (controls only in a browser on this PC)')
        self.web_pw_remove.setVisible(had)
        self.web_pw_remove.toggled.connect(lambda on: (self.web_pw.setEnabled(not on), self.web_pw2.setEnabled(not on)))
        wf.addRow('', self.web_pw_remove)
        page.body.addWidget(self.web_on)
        notes = ('Without a password the controls work only in a browser on this PC. The password is kept '
                 'only as a salted hash. The web version is plain HTTP: use it on a network you trust, or '
                 'over a VPN or a TLS reverse proxy, not straight on the internet.')
        if os.environ.get('FM_MODMON_WEB_PASSWORD'):
            notes += ' FM_MODMON_WEB_PASSWORD is set, and is used instead of this password.'
        page.body.addWidget(self._note(notes))
        page.body.addStretch(1)
        return page

    def _check_web(self):
        pw, pw2 = self.web_pw.text(), self.web_pw2.text()
        if self.web_pw_remove.isChecked() or not (pw or pw2):
            return None
        if pw != pw2:
            return 'The two passwords are different.'
        if len(pw) < MIN_WEB_PASSWORD:
            return f'Use at least {MIN_WEB_PASSWORD} characters for the web password.'
        return None

    def _notifications(self, notify, notifier):
        page = _WizardPage('Notifications',
                           'Send alarms (raised and cleared), SDR lost / recovered and start / stop by email '
                           'and / or a webhook. Leave both off to use the event log only.',
                           self._check_notify)
        self.notify_form = NotifyForm(notify, notifier)
        scroll = QtWidgets.QScrollArea()   # the email fields need more room than the page has on small screens
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(self.notify_form)
        page.body.addWidget(scroll)
        return page

    def _check_notify(self):
        problems = self.notify_form.problems()
        return '\n'.join(problems) if problems else None

    def _finish(self):
        page = _WizardPage('Ready' if self.first_run else 'Save',
                           'Last step: starting with Windows.' if os.name == 'nt' else '')
        self.autostart_box = QtWidgets.QCheckBox(f'Start {APP_NAME} when I sign in to Windows')
        self.autostart_box.setChecked(autostart_enabled())
        self.autostart_box.setVisible(os.name == 'nt')
        page.body.addWidget(self.autostart_box)
        page.body.addSpacing(12)
        page.body.addWidget(self._note(
            f'Click Finish to start monitoring: {APP_NAME} scans the FM band, sets the RSP1A’s gain for '
            'the stations it finds, and opens a receiver on the strongest. "Add receiver" opens more.'
            if self.first_run else
            'Click Finish to save. Notifications and the web password apply at once; the country and web '
            'access at the next start.'))
        page.body.addStretch(1)
        return page

    def accept(self):
        try:
            self.notify_form.save_password()
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(), f'The SMTP password was not stored: {e}')
            return
        super().accept()

    def app_config(self):
        """The AppConfig chosen (the web password hashed)."""
        out = AppConfig.from_dict(self.cfg.to_dict())
        out.setup_done = True
        out.country = self.country()
        out.web_port = self.web_port.value() if self.web_on.isChecked() else 0
        out.web_bind = '127.0.0.1' if self.web_local.isChecked() else '0.0.0.0'
        if self.web_pw_remove.isChecked():
            out.web_password_hash = ''
        elif self.web_pw.text():
            out.web_password_hash = hash_password(self.web_pw.text())
        return out

    def notify_settings(self):
        return self.notify_form.settings()

    def autostart(self):
        return os.name == 'nt' and self.autostart_box.isChecked()


class ReceiverDialog(QtWidgets.QDialog):
    """Edits one receiver's ReceiverSettings."""

    def __init__(self, parent, slot, settings, feed_port, default_port=None, taken_ports=(), country='CA'):
        super().__init__(parent)
        self.setWindowTitle(f'Receiver {slot + 1} settings')
        form = QtWidgets.QFormLayout(self)

        self.name = QtWidgets.QLineEdit(settings.name)
        self.name.setPlaceholderText('optional, e.g. Main TX')
        self.name.setMaxLength(40)
        form.addRow('Name:', self.name)

        self.deemph = QtWidgets.QComboBox()
        self.deemph.addItem('75 \u00b5s (Americas, Korea)', 75)
        self.deemph.addItem('50 \u00b5s (Europe, most elsewhere)', 50)
        self.deemph.setCurrentIndex(self.deemph.findData(settings.deemphasis_us))
        form.addRow('De-emphasis:', self.deemph)

        self.stereo = QtWidgets.QComboBox()
        self.stereo.addItem('Stereo when a pilot is present', 'auto')
        self.stereo.addItem('Always mono', 'mono')
        self.stereo.setCurrentIndex(self.stereo.findData(settings.stereo))
        form.addRow('Stereo:', self.stereo)

        self.volume = QtWidgets.QSpinBox()
        self.volume.setRange(0, 200)
        self.volume.setSuffix(' %')
        self.volume.setValue(settings.volume_pct)
        form.addRow('Play volume:', self.volume)

        self.pty = QtWidgets.QComboBox()
        self.pty.addItem('RBDS (North America)', 'rbds')
        self.pty.addItem('RDS (Europe, elsewhere)', 'rds')
        self.pty.setCurrentIndex(self.pty.findData(settings.pty_names))
        form.addRow('PTY names:', self.pty)

        self.pi = QtWidgets.QLineEdit(settings.expected_pi)
        self.pi.setPlaceholderText('optional, e.g. C6B2')
        self.pi.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression('[0-9A-Fa-f]{0,4}')))
        form.addRow('Expected PI:', self.pi)

        self.service_names = QtWidgets.QLineEdit(settings.service_names)
        self.service_names.setPlaceholderText('optional, e.g. 7A=Alert FM, SCA67=Muzak')
        self.service_names.setToolTip("Names for this station's data services, by RDS group type (7A, 9A, ...)\n"
                                      'or SCA67 / SCA92. Nothing on air names them; these are shown\n'
                                      'in the Data services row and the "data service lost" alarm.')
        form.addRow('Data service names:', self.service_names)

        self.default_port, self.taken_ports = default_port, set(taken_ports)
        self.feed = QtWidgets.QCheckBox('Serve raw RDS groups over TCP' if feed_port
                                        else 'RDS feeds are off (--rds-port 0)')
        self.feed.setChecked(settings.rds_feed)
        self.feed.setEnabled(bool(feed_port))
        self.port = QtWidgets.QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(feed_port or RDS_TCP_PORT)
        self.port.setEnabled(bool(feed_port) and settings.rds_feed)
        self.port.setToolTip(f'Default {default_port}' if default_port else '')
        self.feed.toggled.connect(lambda on: self.port.setEnabled(on and bool(feed_port)))
        feed_row = QtWidgets.QHBoxLayout()
        feed_row.addWidget(self.feed)
        feed_row.addStretch(1)
        feed_row.addWidget(QtWidgets.QLabel('TCP port'))
        feed_row.addWidget(self.port)
        form.addRow('RDS feed:', feed_row)

        alarms = QtWidgets.QGroupBox('Alarms')
        grid = QtWidgets.QGridLayout(alarms)
        self.alarm_checks = {}
        for i, (name, desc, _) in enumerate(ALARM_DEFS):
            box = QtWidgets.QCheckBox(desc[0].upper() + desc[1:])
            box.setChecked(settings.alarms.get(name, True))
            self.alarm_checks[name] = box
            grid.addWidget(box, i, 0)

        def spin(value, lo, hi, suffix, decimals=0):
            w = QtWidgets.QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(decimals)
            w.setSuffix(suffix)
            w.setValue(value)
            return w

        self.min_snr = spin(settings.min_snr_db, 0, 60, ' dB S/N')
        self.silence_lufs = spin(settings.silence_lufs, -70, -10, ' LUFS')
        self.silence_s = spin(settings.silence_s, 2, 300, ' s')
        self.country = country
        self.limit_spins = {}
        for name, label, unit, lo, hi, step in LIMITS:
            w = spin(0, lo, hi, f' {unit}' if unit else '', 0 if step >= 1 else (2 if step < 0.1 else 1))
            w.setSingleStep(step)
            w.setToolTip(label[0].upper() + label[1:])
            w.valueChanged.connect(self._limit_edited)
            self.limit_spins[name] = w
        self.rules = QtWidgets.QComboBox()
        for key, label in (('', 'By country (ISED in Canada, else FCC)'), ('ised', RULES['ised']['name']),
                           ('fcc', RULES['fcc']['name']), ('custom', 'Custom (the limits below)')):
            self.rules.addItem(label, key)
        self.rules.setToolTip('Choosing a rule set fills in its limits; changing any limit makes them custom')
        self._loading = True
        self.rules.setCurrentIndex(max(0, self.rules.findData(settings.rules)))
        self._fill_limits(settings.limits(country))
        self._loading = False
        self.rules.currentIndexChanged.connect(self._rules_chosen)
        row = {name: i for i, (name, *_) in enumerate(ALARM_DEFS)}
        grid.addWidget(QtWidgets.QLabel('below'), row['CARRIER'], 1)
        carrier_row = QtWidgets.QHBoxLayout()
        carrier_row.addWidget(self.min_snr)
        carrier_row.addStretch(1)
        grid.addLayout(carrier_row, row['CARRIER'], 2)
        grid.addWidget(QtWidgets.QLabel('below'), row['SILENCE'], 1)
        silence = QtWidgets.QHBoxLayout()
        silence.addWidget(self.silence_lufs)
        silence.addWidget(QtWidgets.QLabel('for'))
        silence.addWidget(self.silence_s)
        silence.addStretch(1)
        grid.addLayout(silence, row['SILENCE'], 2)
        def line(*parts):
            box = QtWidgets.QHBoxLayout()
            for part in parts:
                if isinstance(part, str):
                    box.addWidget(QtWidgets.QLabel(part))
                else:
                    box.addWidget(part)
            box.addStretch(1)
            return box

        ls = self.limit_spins
        grid.addWidget(QtWidgets.QLabel('above'), row['OVERMOD'], 1)
        grid.addLayout(line(ls['mod_base_pct'], '+', ls['mod_per_sub'], '\u00d7 subcarriers, max', ls['mod_max_pct']),
                       row['OVERMOD'], 2)
        grid.addWidget(QtWidgets.QLabel('outside'), row['PILOT_SPEC'], 1)
        grid.addLayout(line(ls['pilot_min_pct'], '\u2013', ls['pilot_max_pct'], 'or 19 kHz \u00b1', ls['pilot_tol_hz']),
                       row['PILOT_SPEC'], 2)
        grid.addWidget(QtWidgets.QLabel('above'), row['SUBCARRIERS'], 1)
        grid.addLayout(line(ls['sub_total_pct'], 'total, or', ls['sub_high_pct'], 'above 75 kHz'), row['SUBCARRIERS'], 2)
        grid.addWidget(QtWidgets.QLabel('beyond'), row['FREQUENCY'], 1)
        grid.addLayout(line('\u00b1', ls['freq_tol_hz']), row['FREQUENCY'], 2)
        form.addRow('Rules:', self.rules)
        form.addRow(alarms)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _fill_limits(self, limits):
        for name, w in self.limit_spins.items():
            w.blockSignals(True)
            w.setValue(limits[name])
            w.blockSignals(False)

    def _rules_chosen(self):
        key = self.rules.currentData()
        if key == 'custom':
            return
        preset = key or ('ised' if self.country == 'CA' else 'fcc')
        self._fill_limits(RULES[preset]['limits'])

    def _limit_edited(self):
        if not self._loading and self.rules.currentData() != 'custom':
            self.rules.blockSignals(True)
            self.rules.setCurrentIndex(self.rules.findData('custom'))
            self.rules.blockSignals(False)

    def _accept(self):
        if self.feed.isChecked() and self.port.isEnabled() and self.port.value() in self.taken_ports:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(),
                                          f'TCP port {self.port.value()} is already used by another '
                                          'receiver or the web view.')
            return
        pi = self.pi.text().strip()
        if pi and len(pi) != 4:
            QtWidgets.QMessageBox.warning(self, self.windowTitle(),
                                          'Expected PI is four hex digits (such as C6B2), or empty.')
            return
        self.accept()

    def settings(self):
        return ReceiverSettings.from_dict({
            'name': self.name.text().strip(),
            'deemphasis_us': self.deemph.currentData(),
            'stereo': self.stereo.currentData(),
            'volume_pct': self.volume.value(),
            'pty_names': self.pty.currentData(),
            'expected_pi': self.pi.text(),
            'service_names': self.service_names.text(),
            'rds_feed': self.feed.isChecked(),
            'rds_port': 0 if self.port.value() == self.default_port else self.port.value(),
            'alarms': {name: box.isChecked() for name, box in self.alarm_checks.items()},
            'silence_lufs': self.silence_lufs.value(),
            'silence_s': int(self.silence_s.value()),
            'min_snr_db': self.min_snr.value(),
            'rules': self.rules.currentData(),
            **{name: w.value() for name, w in self.limit_spins.items()},
        })


@dataclass
class NotifySettings:
    """Where notifications go and which events; saved in fm-modmon-ms_config.json.
    The SMTP password is not here: see smtp_password()."""
    email: bool = False
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_security: str = 'starttls'   # 'starttls', 'ssl' or 'none'
    smtp_user: str = ''
    email_from: str = ''
    email_to: str = ''                # comma-separated
    webhook: bool = False
    webhook_url: str = ''
    webhook_format: str = 'json'      # 'json', 'slack', 'teams' or 'discord'
    on_raise: bool = True
    on_clear: bool = True
    on_sdr: bool = True
    on_start_stop: bool = True

    @classmethod
    def from_dict(cls, d):
        known = {f.name for f in fields(cls)}
        out = cls(**{k: v for k, v in (d or {}).items() if k in known})
        if out.smtp_security not in ('starttls', 'ssl', 'none'):
            out.smtp_security = 'starttls'
        if out.webhook_format not in ('json', 'slack', 'teams', 'discord'):
            out.webhook_format = 'json'
        try:
            out.smtp_port = int(out.smtp_port)
        except (TypeError, ValueError):
            out.smtp_port = 587
        return out

    def to_dict(self):
        return asdict(self)

    def recipients(self):
        return [a.strip() for a in self.email_to.replace(';', ',').split(',') if a.strip()]

    def problems(self, have_password=None):
        """What stops the enabled channels working, as text lines. have_password:
        whether there will be an SMTP password (default: whether one is stored or set)."""
        out = []
        if self.email:
            if not self.smtp_host:
                out.append('email: no SMTP server')
            if not self.recipients():
                out.append('email: no recipients')
            if not (self.email_from or self.smtp_user):
                out.append('email: no sender address')
            if self.smtp_user and not (smtp_password() if have_password is None else have_password):
                out.append('email: no password for the SMTP user name')
        if self.webhook and not re.match(r'https?://', self.webhook_url):
            out.append('webhook: the URL must start with https:// (or http://)')
        return out


# The web password is kept only as a salted PBKDF2 hash (in the settings file);
# the SMTP password, which has to be sent as it is, in Windows Credential Manager
# (protected by the signed-in Windows account), never in the settings file.
PBKDF2_ITERATIONS = 240_000
SMTP_CREDENTIAL = 'FM-Modmon-ms/smtp'
MIN_WEB_PASSWORD = 8
CRED_TYPE_GENERIC, CRED_PERSIST_LOCAL_MACHINE = 1, 2


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}'


def verify_password(password, stored):
    try:
        algo, iterations, salt, digest = stored.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        got = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(got, base64.b64decode(digest))
    except (ValueError, TypeError, AttributeError):
        return False


if os.name == 'nt':
    from ctypes import wintypes

    class _Credential(ctypes.Structure):
        _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD), ('TargetName', wintypes.LPWSTR),
                    ('Comment', wintypes.LPWSTR), ('LastWritten', wintypes.FILETIME),
                    ('CredentialBlobSize', wintypes.DWORD), ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
                    ('Persist', wintypes.DWORD), ('AttributeCount', wintypes.DWORD),
                    ('Attributes', ctypes.c_void_p), ('TargetAlias', wintypes.LPWSTR),
                    ('UserName', wintypes.LPWSTR)]


def credential_read(target):
    """A secret from Windows Credential Manager; None if none is stored (or off Windows)."""
    if os.name != 'nt':
        return None
    advapi = ctypes.windll.advapi32
    ptr = ctypes.POINTER(_Credential)()
    if not advapi.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(ptr)):
        return None
    try:
        c = ptr.contents
        return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode('utf-16-le')
    finally:
        advapi.CredFree(ptr)


def credential_write(target, secret, user=''):
    """Store a secret in Windows Credential Manager (an empty one deletes it)."""
    if not secret:
        credential_delete(target)
        return
    if os.name != 'nt':
        raise OSError('storing a password needs Windows Credential Manager; '
                      'set FM_MODMON_SMTP_PASSWORD instead')
    blob = secret.encode('utf-16-le')
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = _Credential(Type=CRED_TYPE_GENERIC, TargetName=target, Comment=f'{APP_NAME} password',
                       CredentialBlobSize=len(blob), CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
                       Persist=CRED_PERSIST_LOCAL_MACHINE, UserName=user or None)
    if not ctypes.windll.advapi32.CredWriteW(ctypes.byref(cred), 0):
        raise ctypes.WinError()


def credential_delete(target):
    if os.name == 'nt':
        ctypes.windll.advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0)


def smtp_password():
    """The SMTP password: FM_MODMON_SMTP_PASSWORD if set, else the one stored by Settings / Setup."""
    return os.environ.get('FM_MODMON_SMTP_PASSWORD') or credential_read(SMTP_CREDENTIAL)


@dataclass
class AppConfig:
    """App-wide settings, chosen in Setup; saved in the settings file's "app" section.
    Command-line options, where given, take precedence."""
    setup_done: bool = False
    country: str = 'CA'                # ISO country: ISED rules for CA, else FCC; RadioDNS
    web_port: int = WEB_PORT           # 0 = no web version
    web_bind: str = '0.0.0.0'          # '127.0.0.1' = this PC only
    web_password_hash: str = ''        # hash_password(); '' = controls only in a browser on this PC

    @classmethod
    def from_dict(cls, d):
        known = {f.name for f in fields(cls)}
        out = cls(**{k: v for k, v in (d or {}).items() if k in known})
        out.setup_done = bool(out.setup_done)
        out.country = str(out.country or '').strip().upper()
        if not re.fullmatch(r'[A-Z]{2}', out.country):
            out.country = 'CA'
        try:
            out.web_port = int(out.web_port)
        except (TypeError, ValueError):
            out.web_port = WEB_PORT
        if not (out.web_port == 0 or 1024 <= out.web_port <= 65535):
            out.web_port = WEB_PORT
        out.web_bind = str(out.web_bind or '0.0.0.0')
        out.web_password_hash = str(out.web_password_hash or '')
        return out

    def to_dict(self):
        return asdict(self)


class Notifier:
    """Sends events by email and / or webhook from a background thread.
    event() queues; events within NOTIFY_BATCH_S go out together; a failed
    send is retried after NOTIFY_RETRY_S; failures are put on self.results
    (lines for the event log, read by the GUI thread)."""

    KINDS = {'raise': 'on_raise', 'clear': 'on_clear', 'sdr': 'on_sdr', 'startstop': 'on_start_stop'}

    def __init__(self, settings, where):
        self.settings = settings
        self.where = where              # () -> (host name, web address or None) for the message
        self.results = queue.Queue()
        self.last_reply = {}            # channel -> the server's last answer to a message
        self._q = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def enabled(self, kind):
        s = self.settings
        return (s.email or s.webhook) and getattr(s, self.KINDS.get(kind, 'on_raise'))

    def event(self, kind, text):
        if self.enabled(kind):
            self._q.put((time.strftime('%Y-%m-%d %H:%M:%S'), kind, text))

    def send_now(self, kind, text, timeout=8):
        """Send one event at once, without retries (for "stopped", as the app exits)."""
        if self.enabled(kind):
            self._deliver([(time.strftime('%Y-%m-%d %H:%M:%S'), kind, text)], retries=(), timeout=timeout)

    def test(self, settings, password=None):
        """Send a test message with `settings` (and an SMTP password not stored yet);
        returns [(channel, error or None)]."""
        host, _ = self.where()
        return self._deliver([(time.strftime('%Y-%m-%d %H:%M:%S'), 'test',
                               f'test message from {APP_NAME} on {host}')], settings, retries=(), report=False,
                             password=password)

    def _run(self):
        while True:
            batch = [self._q.get()]
            deadline = time.monotonic() + NOTIFY_BATCH_S
            while (left := deadline - time.monotonic()) > 0:
                try:
                    batch.append(self._q.get(timeout=left))
                except queue.Empty:
                    break
            self._deliver(batch)

    def _deliver(self, batch, settings=None, retries=NOTIFY_RETRY_S, timeout=15, report=True, password=None):
        s = settings or self.settings
        results = []
        for name, send in (('email', self._email), ('webhook', self._webhook)):
            if not getattr(s, name):
                continue
            err = None
            for wait in (0, *retries):
                time.sleep(wait)
                try:
                    send(s, batch, timeout, password)
                    err = None
                    break
                except Exception as e:  # noqa: BLE001 - any failure is reported, then retried
                    err = f'{type(e).__name__}: {e}'
            results.append((name, err))
            if err and report:
                self.results.put(f'notification by {name} failed ({len(retries) + 1} attempts): {err}')
        return results

    def _message(self, batch):
        host, web = self.where()
        first = batch[0][2]
        subject = f'[{APP_NAME} {host}] ' + (first if len(batch) == 1 else f'{len(batch)} events: {first} \u2026')
        lines = [f'{t}  {text}' for t, _, text in batch]
        footer = [f'{APP_NAME} on {host}'] + ([f'web: {web}'] if web else [])
        return subject, lines, footer

    def _email(self, s, batch, timeout, password=None):
        subject, lines, footer = self._message(batch)
        msg = EmailMessage()
        msg['Subject'] = subject
        sender = s.email_from or s.smtp_user
        msg['From'] = sender
        msg['To'] = ', '.join(s.recipients())
        # Gmail / Google Workspace (and many spam filters) refuse mail without these;
        # behind a relay that has already said OK, the refusal only reaches the sender.
        msg['Date'] = formatdate(localtime=True)
        domain = parseaddr(sender)[1].rpartition('@')[2]   # From may be 'Name <addr>'
        msg['Message-ID'] = make_msgid(domain=domain or socket.getfqdn())
        msg.set_content('\n'.join(lines + [''] + footer) + '\n')
        password = password or smtp_password()
        if s.smtp_security == 'ssl':
            smtp = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=timeout, context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=timeout)
        with smtp:
            if s.smtp_security == 'starttls':
                smtp.starttls(context=ssl.create_default_context())
            if s.smtp_user and password:
                smtp.login(s.smtp_user, password)
            # Keep the server's answer to the message itself: it carries the server's
            # queue ID, the way to trace a message that was accepted but never arrived.
            data, replies = smtp.data, []
            smtp.data = lambda m: replies.append(data(m)) or replies[-1]
            smtp.send_message(msg)
            if replies:
                code, text = replies[-1]
                self.last_reply['email'] = f'{code} {text.decode(errors="replace")}'

    def _webhook(self, s, batch, timeout, password=None):
        subject, lines, footer = self._message(batch)
        text = '\n'.join([subject] + lines)
        host, web = self.where()
        if s.webhook_format == 'slack':
            payload = {'text': text}
        elif s.webhook_format == 'discord':
            payload = {'content': text[:1990]}
        elif s.webhook_format == 'teams':  # a Teams "workflow" incoming webhook: an Adaptive Card
            body = [{'type': 'TextBlock', 'text': subject, 'weight': 'Bolder', 'wrap': True}]
            body += [{'type': 'TextBlock', 'text': line, 'wrap': True, 'spacing': 'None'} for line in lines]
            payload = {'type': 'message', 'attachments': [{
                'contentType': 'application/vnd.microsoft.card.adaptive',
                'content': {'$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
                            'type': 'AdaptiveCard', 'version': '1.4', 'body': body}}]}
        else:
            payload = {'app': APP_NAME, 'host': host, 'web': web, 'summary': subject, 'text': text,
                       'events': [{'time': t, 'kind': k, 'text': x} for t, k, x in batch]}
        req = urllib.request.Request(s.webhook_url, data=json.dumps(payload).encode(), method='POST',
                                     headers={'Content-Type': 'application/json', 'User-Agent': APP_NAME})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()


def autostart_enabled():
    return os.path.exists(STARTUP_LNK)


def set_autostart(on, args_text=''):
    """Add or remove a shortcut in the Windows Startup folder (start FM-Modmon-ms at sign-in)."""
    if not on:
        if os.path.exists(STARTUP_LNK):
            os.remove(STARTUP_LNK)
        return
    pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    script = os.path.abspath(__file__)
    q = lambda v: v.replace("'", "''")  # noqa: E731 - PowerShell single-quote escaping
    ps = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{q(STARTUP_LNK)}'); "
          f"$s.TargetPath = '{q(pythonw if os.path.exists(pythonw) else sys.executable)}'; "
          f"$s.Arguments = '{q(subprocess.list2cmdline([script]) + (' ' + args_text if args_text else ''))}'; "
          f"$s.WorkingDirectory = '{q(os.path.dirname(script))}'; "
          f"$s.IconLocation = '{q(ICON_PATH)}'; $s.Description = 'FM-Modmon-ms FM monitor'; $s.Save()")
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], check=True, timeout=30,
                   capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def load_app(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return AppConfig.from_dict(json.load(fh).get('app'))
    except (OSError, ValueError, AttributeError):
        return AppConfig()


def load_notify(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return NotifySettings.from_dict(json.load(fh).get('notify'))
    except (OSError, ValueError, AttributeError):
        return NotifySettings()


def load_config(path):
    """Saved receivers as {slot: (freq_hz, ReceiverSettings)}; {} if none or unreadable."""
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        print(f'ignoring {path}: {e}')
        return {}
    out = {}
    for r in data.get('receivers', []):
        try:
            slot = int(r['receiver']) - 1
            freq = int(round(float(r['freq_mhz']) * 10)) * 100000
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= slot < MAX_RECEIVERS and 64e6 <= freq <= 108e6 and slot not in out:
            out[slot] = (freq, ReceiverSettings.from_dict(r.get('settings')))
    if out and not _fits([f for f, _ in out.values()]):
        first = min(out)
        print(f'{path}: saved receivers no longer fit one SDR window; opening receiver {first + 1} only')
        out = {first: out[first]}
    return out


def save_config(path, panels, notify=None, app=None):
    """Write the open receivers and their settings, the notification settings and
    the app settings (atomically); a part given as None keeps what the file has."""
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data['version'] = 1
    if panels is not None:
        data['receivers'] = [{'receiver': p.slot + 1, 'freq_mhz': p.station.freq_hz / 1e6,
                              'settings': p.settings.to_dict()} for p in panels]
    if notify is not None:
        data['notify'] = notify.to_dict()
    if app is not None:
        data['app'] = app.to_dict()
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except OSError as e:
        print(f'could not save {path}: {e}')


class _Finite(list):
    """A list of numbers already known to be finite: _finite passes it through."""


def _finite(obj):
    """obj with NaN/inf floats as None (JSON has no infinity)."""
    if isinstance(obj, _Finite):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    if isinstance(obj, np.generic):
        return _finite(obj.item())
    return obj


def _image_type(data):
    for magic, ctype in ((b'\x89PNG', 'image/png'), (b'\xff\xd8', 'image/jpeg'), (b'GIF8', 'image/gif'),
                         (b'<svg', 'image/svg+xml'), (b'<?xml', 'image/svg+xml')):
        if data.startswith(magic):
            return ctype
    if data[8:12] == b'WEBP':
        return 'image/webp'
    return None


WEB_HELP = """\
Anyone who can open this page can watch it and listen.

Listen (under each receiver) plays that receiver in this browser, a few
seconds behind the air, in the format chosen beside it: MP3 or AAC (any
browser), Opus (half the data for the same quality) or FLAC (lossless, about
1 Mbit/s); only formats this browser can play are listed, and the choice is
remembered. While it plays, the player beside it shows LIVE and how long, with
mute and volume (also remembered); Stop ends the stream. It plays the
receiver's audio source (analog FM or an SCA subcarrier; IBOC plays on the
FM-Modmon-ms PC only).

The controls (station, settings, remove, audio source, reset integrated, add
receiver, recalibrate gain) need signing in: click "View only" and enter the
password. The button turns green ("Controls on"); click it again to sign out.
Closing the tab also signs out; reloading the page doesn't. When no web
password is set, the controls work only in a browser on the FM-Modmon-ms PC
itself, and the button can't be clicked.

Everything shown is the app's own display, refreshed 10 times a second. The
guide below explains each measurement."""

_HELP_PATH = re.compile(r'(?:[A-Za-z]:\\|\.\.?[\\/])[^\s,;)\'"]*')


def help_sections(safe=False, session=None):
    """Help as [(title, kind, text)], kind 'text' or 'pre'. safe=True is for the
    web page: no session details, and local paths replaced with <path>."""
    out = []
    if session and not safe:
        out.append(('This session', 'pre', session))
    if safe:
        out.append(('Using this page', 'text', WEB_HELP))
    out.append(('Guide', 'pre', __doc__.strip()))
    out.append(('Command-line options', 'pre', build_parser().format_help()))
    if safe:
        out = [(title, kind, _HELP_PATH.sub('<path>', text)) for title, kind, text in out]
    return out


class HelpDialog(QtWidgets.QDialog):
    """The app's help: sections from help_sections() in one scrolling page."""

    def __init__(self, parent, sections):
        super().__init__(parent)
        self.setWindowTitle(f'{APP_NAME} help')
        self.resize(940, 760)
        view = QtWidgets.QTextBrowser()
        view.setOpenExternalLinks(False)
        css = ('h2 { color: #8ab4f8; font-size: 13pt; margin: 14px 0 6px; } '
               'pre { font-family: Consolas; font-size: 9pt; color: #d6d8dc; white-space: pre-wrap; } '
               'p { color: #d6d8dc; } a { color: #8ab4f8; }')
        toc = ' \u00b7 '.join(f'<a href="#s{i}">{_html(t)}</a>' for i, (t, _, _) in enumerate(sections))
        body = [f'<style>{css}</style><p>{toc}</p>']
        for i, (title, kind, text) in enumerate(sections):
            body.append(f'<h2><a name="s{i}"></a>{_html(title)}</h2>')
            if kind == 'pre':
                body.append(f'<pre>{_html(text)}</pre>')
            else:
                body.extend(f'<p>{_html(par)}</p>' for par in text.split('\n\n'))
        view.setHtml(''.join(body))
        view.anchorClicked.connect(lambda url: view.scrollToAnchor(url.fragment()))
        close = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        close.rejected.connect(self.close)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view)
        layout.addWidget(close)


class _WebServer(ThreadingHTTPServer):
    """On Windows, SO_REUSEADDR (http.server's default) lets a second process
    bind the same port without error, and the two then answer each other's
    requests. Bind it exclusively there, so a port in use fails to open."""
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class WebView:
    """The web version of the app: fm-modmon-ms-web.html draws the receiver panels
    from /state.json (rebuilt at UPDATE_HZ while anyone is watching), sends
    controls to /api/<action> (run on the GUI thread), and plays each
    receiver's audio as MP3 from /audio/<receiver>.mp3.

    Anyone who can reach the port can watch and listen. Controls need the
    password, or, with no password set, a browser on this PC itself
    (http://localhost:<port>/). Signing in returns a session token that the
    page keeps in the tab's sessionStorage and sends as X-FM-Modmon-Session:
    closing the tab ends the session (a reload keeps it), and a session not
    heard from for SESSION_IDLE_S is dropped. Control requests must carry an
    X-FM-Modmon header, which a page on another site can't send.
    """

    WEB_IDLE_S = 15
    SESSION_IDLE_S = 600

    def __init__(self, bind, port, password=None, password_hash=''):
        self.port = port
        self.password = password or None          # --web-password / FM_MODMON_WEB_PASSWORD
        self.password_hash = password_hash or ''  # from Setup (used when there is no password above)
        self.favicon = ico_bytes((16, 32, 48))
        self.touch_icon = _png(draw_icon(180))
        self.state = b'{"ready": false}'
        self.events = b'[]'
        self.help = json.dumps({'sections': help_sections(safe=True)}).encode()
        self.images = {}               # (receiver number, 'logo' | 'art') -> file path
        self.audio = {}                # receiver number -> WebAudio
        self.formats = []              # WEB_FORMATS keys offered (ffmpeg can encode them)
        self.commands = queue.Queue()  # (action, args, Future or None) for the GUI thread
        self.sessions = {}             # token -> last heard from (monotonic)
        self.last_hit = 0.0
        self.server = _WebServer((bind, port), self._handler())
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def wanted(self):
        return time.monotonic() - self.last_hit < self.WEB_IDLE_S

    def listeners(self):
        return sum(s.listeners for s in list(self.audio.values()))

    def note(self, text):
        """An event-log line, written by the GUI thread."""
        self.commands.put(('log', {'text': text}, None))

    def close_audio(self):
        for audio in list(self.audio.values()):
            audio.close_all()

    def locked(self):
        """Whether the controls need signing in (a password is set)."""
        return bool(self.password or self.password_hash)

    def check_password(self, given):
        if self.password:
            return hmac.compare_digest(given.encode(), self.password.encode())
        return bool(self.password_hash) and verify_password(given, self.password_hash)

    def set_password_hash(self, password_hash):
        """A new password from Setup: everyone signed in has to sign in again."""
        self.password_hash = password_hash or ''
        self.sessions.clear()

    def _session(self, handler):
        """The request's session token if it is signed in (and keep the session alive)."""
        token = handler.headers.get('X-FM-Modmon-Session') or ''
        now = time.monotonic()
        for old in [t for t, seen in list(self.sessions.items()) if now - seen > self.SESSION_IDLE_S]:
            self.sessions.pop(old, None)  # tabs closed without signing out
        if token in self.sessions:
            self.sessions[token] = now
            return token
        return None

    def can_control(self, handler):
        if self.locked():
            return self._session(handler) is not None
        # No password: only a browser on this PC, addressed as localhost (the
        # Host check stops another site reaching it through DNS rebinding).
        host = (handler.headers.get('Host') or '').lower()
        host = host[1:host.find(']')] if host.startswith('[') else host.split(':')[0]
        return handler.client_address[0] in ('127.0.0.1', '::1') and host in ('localhost', '127.0.0.1', '::1')

    def _handler(self):
        view = self

        class Handler(BaseHTTPRequestHandler):
            # A client that goes quiet (a browser's idle pre-connection, a stalled
            # audio listener) lets go of its thread, and its listener slot, after this.
            timeout = 60

            def _send(self, code, body, ctype, headers=()):
                self.send_response(code)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self._hardening()
                for k, v in headers:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _hardening(self):
                # No framing (clickjacking of the controls), no MIME sniffing,
                # and the page's URL isn't leaked to the sites its images come from.
                self.send_header('X-Frame-Options', 'DENY')
                self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')

            def _json(self, code, obj, headers=()):
                self._send(code, json.dumps(obj).encode(), 'application/json', headers)

            def do_GET(self):
                view.last_hit = time.monotonic()
                path = self.path.split('?', 1)[0]
                if path in ('/', '/index.html'):
                    try:
                        with open(WEB_HTML, 'rb') as fh:
                            body = fh.read()
                    except OSError as e:
                        self.send_error(500, f'cannot read {WEB_HTML}: {e}')
                        return
                    self._send(200, body, 'text/html; charset=utf-8')
                elif path in ('/state.json', '/status.json'):
                    access = json.dumps({'control': view.can_control(self), 'password': view.locked()})
                    self._send(200, b'{"access": ' + access.encode() + b', ' + view.state[1:], 'application/json')
                elif path == '/help.json':
                    self._send(200, view.help, 'application/json')
                elif path == '/events.json':
                    self._send(200, view.events, 'application/json')
                elif path == '/favicon.ico':
                    self._send(200, view.favicon, 'image/x-icon')
                elif path == '/icon.png':
                    self._send(200, view.touch_icon, 'image/png')
                elif m := re.fullmatch(r'/img/(\d)/(logo|art)', path):
                    try:
                        with open(view.images[(int(m[1]), m[2])], 'rb') as fh:
                            body = fh.read()
                    except (KeyError, OSError):
                        self.send_error(404)
                        return
                    ctype = _image_type(body)
                    if not ctype:
                        self.send_error(415)
                        return
                    self._send(200, body, ctype)
                elif m := re.fullmatch(r'/audio/(\d)\.(\w+)', path):
                    self._stream(int(m[1]), m[2])
                else:
                    self.send_error(404)

            def _stream(self, n, fmt):
                audio = view.audio.get(n)
                if not audio:
                    self.send_error(404, 'no such receiver, or no audio encoder (--ffmpeg)')
                    return
                if fmt not in view.formats:
                    self.send_error(404, f'formats: {", ".join(view.formats)}')
                    return
                if view.listeners() >= WEB_MAX_LISTENERS:
                    self.send_error(503, f'{WEB_MAX_LISTENERS} listeners already')
                    return
                enc = audio.open(fmt)
                who = self.client_address[0]
                view.note(f'web audio: {who} listening to receiver {n} ({WEB_FORMATS[fmt]["label"]})')
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', WEB_FORMATS[fmt]['mime'])
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('icy-name', f'{APP_NAME} receiver {n}')
                    self._hardening()
                    self.end_headers()
                    for chunk in enc.chunks():
                        self.wfile.write(chunk)
                except OSError:
                    pass
                finally:
                    audio.close(enc)
                    view.note(f'web audio: {who} stopped listening to receiver {n}')

            def do_POST(self):
                view.last_hit = time.monotonic()
                path = self.path.split('?', 1)[0]
                who = self.client_address[0]
                if self.headers.get('X-FM-Modmon') != '1':
                    self._json(403, {'error': 'missing X-FM-Modmon header'})
                    return
                try:
                    n = int(self.headers.get('Content-Length') or 0)
                    if n > 65536:
                        raise ValueError
                    args = json.loads(self.rfile.read(n) or b'{}')
                    if not isinstance(args, dict):
                        raise ValueError
                except ValueError:
                    self._json(400, {'error': 'bad request'})
                    return
                if path == '/api/login':
                    if not view.locked():
                        self._json(400, {'error': 'no web password is set (Settings > Run setup again)'})
                        return
                    if not view.check_password(str(args.get('password', ''))):
                        time.sleep(1)  # slows guessing
                        view.note(f'web: failed sign-in from {who}')
                        self._json(403, {'error': 'wrong password'})
                        return
                    token = secrets.token_urlsafe(24)
                    view.sessions[token] = time.monotonic()
                    view.note(f'web: {who} signed in to the controls')
                    self._json(200, {'ok': True, 'token': token})
                    return
                if path == '/api/logout':
                    token = view._session(self)
                    if token:
                        view.sessions.pop(token, None)
                        view.note(f'web: {who} signed out of the controls')
                    self._json(200, {'ok': True})
                    return
                if not path.startswith('/api/'):
                    self.send_error(404)
                    return
                if not view.can_control(self):
                    self._json(403, {'error': 'sign in to use the controls' if view.locked() else
                                     'controls work only from this PC (http://localhost:'
                                     f'{view.port}/) until a web password is set'})
                    return
                fut = concurrent.futures.Future()
                view.commands.put((path[len('/api/'):], args, fut))
                try:
                    try:
                        result = fut.result(timeout=20)
                    except concurrent.futures.TimeoutError:
                        if fut.cancel():  # not started: it won't run later, after the page was told it failed
                            self._json(504, {'error': 'the app did not answer'})
                            return
                        result = fut.result()  # it had just started: report how it went
                except ValueError as e:
                    self._json(400, {'error': str(e)})
                    return
                self._json(200, result or {'ok': True})

            def log_message(self, *args):
                pass

        return Handler


class DetailWindow(QtWidgets.QWidget):
    """A receiver's detail view popped out of the main window (so a wall display
    can show several side by side); closing it puts the detail back."""

    def __init__(self, main, panel, on_close):
        super().__init__(main, QtCore.Qt.Window)
        self.panel, self.on_close = panel, on_close
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(8, 8, 8, 8)
        box.addWidget(panel.detail)
        panel.detail.show()
        self.setWindowTitle(f'{panel.title} \u2013 {APP_NAME}')
        self.resize(max(panel.detail.sizeHint().width(), main.width(), 1500), panel.detail.sizeHint().height() + 16)

    def closeEvent(self, event):
        if self.on_close:
            self.on_close(self.panel)
        super().closeEvent(event)


class ChipRow(QtWidgets.QWidget):
    """The header's status chips. When the window is too narrow for them all, the least
    important (sample rate, SDR window, stations found) are hidden; the SDR and gain
    chips (which shows SDR LOST) always stay."""
    HIDE_FIRST = ('rate', 'window', 'found')

    def __init__(self, keys):
        super().__init__()
        self.box = QtWidgets.QHBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(6)
        self.chips = {}
        for key in keys:
            chip = self.chips[key] = QtWidgets.QLabel()
            chip.setObjectName('chip')
            self.box.addWidget(chip)
        self.box.addStretch(1)

    def sizeHint(self):
        hints = [chip.sizeHint() for chip in self.chips.values()]
        return QtCore.QSize(sum(h.width() for h in hints) + self.box.spacing() * (len(hints) - 1),
                            max(h.height() for h in hints))

    def minimumSizeHint(self):
        return QtCore.QSize(0, self.sizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def fit(self):
        """Show the chips that fit the row's width; call after changing their text."""
        spare = self.width() - self.sizeHint().width()
        for key in self.HIDE_FIRST:
            chip = self.chips[key]
            chip.setVisible(spare >= 0)
            if spare < 0:
                spare += chip.sizeHint().width() + self.box.spacing()


class ReceiverScroll(QtWidgets.QScrollArea):
    """The receiver panels, scrolling when the window is smaller than them (a receiver
    is taller than a laptop screen). Its size hint is the panels' own, so the window
    still opens at full size on a screen that has room."""

    def __init__(self, widget):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setWidget(widget)
        self.viewport().setAutoFillBackground(False)
        widget.setAutoFillBackground(False)

    def sizeHint(self):
        return self.widget().sizeHint()

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)


class MainWindow(QtWidgets.QWidget):
    def __init__(self, tb, stations, gain_info, iboc_scan=None, web=None, open_feed=None,
                 settings=None, config_path=None, nrsc5=None, radiodns=None, country='CA', ffmpeg=None):
        super().__init__()
        self.tb = tb
        self.ffmpeg = ffmpeg            # ffmpeg for browser audio, or None: none
        self.radiodns = radiodns        # RadioDns, or None: no lookups
        self.country = country
        self.nrsc5 = nrsc5              # path to nrsc5.exe, or None: no IBOC playout
        self.config_path = config_path  # None: don't save
        self.app_config = None          # AppConfig (set by main); None: the file's is kept
        self.stations = stations
        self.gain_info = gain_info
        self.iboc_scan = iboc_scan
        self.web = web
        self.open_feed = open_feed  # slot -> RdsGroupServer or None
        self.n_found = sum(1 for _, snr in stations if snr is not None)
        self.scanned = bool(self.n_found) or bool(iboc_scan)
        self.names = {}  # freq -> PS seen on air
        self.events = deque(maxlen=200)
        self.n_events = 0
        self._feed_clients = {}
        self.panels = []
        self.setWindowTitle(f'{APP_NAME} - RSP1A')
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(6)
        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QPixmap.fromImage(draw_icon(64)).scaled(
            30, 30, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        top.addWidget(logo)
        title = QtWidgets.QLabel(APP_NAME)
        title.setObjectName('appTitle')
        top.addWidget(title)
        self.chip_row = ChipRow(('sdr', 'window', 'rate', 'gain', 'found'))
        self.chips = self.chip_row.chips
        top.addWidget(self.chip_row, 1)
        self.help_btn = QtWidgets.QPushButton('?')
        self.help_btn.setObjectName('help')
        self.help_btn.setFixedSize(32, 32)
        self.help_btn.setToolTip('Help: this session, the guide and all command-line options')
        self.help_btn.clicked.connect(self._show_help)
        top.addWidget(self.help_btn)
        self.settings_btn = QtWidgets.QPushButton('\u2699  Settings')
        self.settings_btn.setMinimumHeight(32)
        self.settings_btn.setToolTip('Notifications (email, webhook) and starting with Windows')
        self.settings_btn.clicked.connect(self._app_settings)
        top.addWidget(self.settings_btn)
        self.notify_settings = NotifySettings()
        self.notifier = Notifier(self.notify_settings, self._where)
        self._recovery = None   # while the SDR is being reopened: {'since', 'attempt', 'error', 'done'}
        self._watch_from = None  # the SDR watchdog starts once the flowgraph does
        self.overload = AdcOverload()  # judged by the watchdog
        self.args = None   # the command line, set by main(), for the help
        self.cal_btn = QtWidgets.QPushButton('\u27f2  Recalibrate gain')
        self.cal_btn.setMinimumHeight(32)
        self.cal_btn.setToolTip('Set the RSP1A gain for the stations being received now (takes a few '
                                'seconds; the meters restart afterwards)')
        self.cal_btn.clicked.connect(self._recalibrate)
        top.addWidget(self.cal_btn)
        self._cal = None  # {'thread', 'result' | 'error', 'was'} while recalibrating
        self.add_btn = QtWidgets.QPushButton('+  Add receiver')
        self.add_btn.setObjectName('primary')
        self.add_btn.setMinimumHeight(32)
        self.add_btn.clicked.connect(self._add_receiver)
        top.addWidget(self.add_btn)
        layout.addLayout(top)
        self.header_text = ''
        receivers = QtWidgets.QWidget()
        box = QtWidgets.QVBoxLayout(receivers)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        box.addWidget(column_heads())
        self.rows_box = QtWidgets.QVBoxLayout()   # one StationRow per receiver
        self.rows_box.setSpacing(4)
        box.addLayout(self.rows_box)
        self.details = QtWidgets.QStackedWidget()  # the selected receiver's detail view
        box.addWidget(self.details)
        box.addStretch(1)
        self.selected = None
        self.scroll = ReceiverScroll(receivers)
        layout.addWidget(self.scroll, 1)   # spare height goes to the receivers, not the event log
        events, events_box = card()
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setFont(QtGui.QFont('Consolas', 9))
        self.alarm_table = AlarmTable()
        self.log_tabs = QtWidgets.QTabBar()
        self.log_tabs.setObjectName('detailTabs')
        self.log_tabs.setDrawBase(False)
        self.log_tabs.setExpanding(False)
        self.log_tabs.addTab('Alarms')
        self.log_tabs.addTab('Events')
        logs = QtWidgets.QStackedWidget()
        logs.addWidget(self.alarm_table)
        logs.addWidget(self.log_view)
        logs.setFixedHeight(104)
        self.log_tabs.currentChanged.connect(logs.setCurrentIndex)
        events_box.addWidget(self.log_tabs, 0, QtCore.Qt.AlignLeft)
        events_box.addWidget(logs)
        events.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        layout.addWidget(events)
        for slot, st in enumerate(tb.slots):
            if st:
                self._add_panel(slot, st, (settings or {}).get(slot))
        self._update_window()
        self.log('monitor started: ' + ', '.join(f'{p.station.freq_hz / 1e6:.1f}' for p in self.panels))

        poll = QtCore.QTimer(self)
        poll.timeout.connect(self._refresh)
        poll.start(1000 // UPDATE_HZ)
        if web:
            commands = QtCore.QTimer(self)
            commands.timeout.connect(self._web_commands)
            commands.start(50)

    def log(self, text):
        """Event log: window, web view and logs/fm-modmon-ms_events_YYYY-MM-DD.log."""
        line = f'{time.strftime("%Y-%m-%d %H:%M:%S")}  {text}'
        self.events.append(line)
        self.n_events += 1
        self.log_view.appendPlainText(line)
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, f'{APP_NAME.lower()}_events_{time.strftime("%Y-%m-%d")}.log'),
                      'a', encoding='utf-8') as fh:
                fh.write(line + '\n')
        except OSError as e:
            print(f'could not write event log: {e}')

    # ------------------------------------------------------------ receivers
    def _add_panel(self, slot, st, settings=None):
        panel = StationPanel(st, self.stations, self._on_play, self._on_select, self.iboc_scan,
                             self._remove_receiver, self._on_settings, self._on_source,
                             self.radiodns, self.country, on_focus=self.focus, on_pop=self.pop_out)
        panel.slot = slot
        panel.settings = settings or ReceiverSettings()
        panel.set_source(panel.settings.audio_source)
        st.audio_source = panel.settings.audio_source
        st.apply_settings(panel.settings)
        self._set_feed(panel, panel.settings.rds_feed)
        for freq, ps in self.names.items():
            panel.set_station_name(freq, ps)
        self.panels.append(panel)
        self.panels.sort(key=lambda p: p.slot)
        if self.web and self.ffmpeg and self.web.formats:
            self.web.audio[slot + 1] = WebAudio(self.ffmpeg, st.web_tap)
        self.rows_box.insertWidget(self.panels.index(panel), panel.row)
        self.details.addWidget(panel.detail)
        if self.selected is None:
            self.focus(panel)

    def focus(self, panel):
        """Select a receiver: its row is highlighted and its detail shown (or, when
        popped out, its window raised)."""
        self.selected = panel
        for p in self.panels:
            p.row.set_selected(p is panel)
        if panel is not None and panel.window:
            panel.window.raise_()
            panel.window.activateWindow()
        elif panel is not None:
            self.details.setCurrentWidget(panel.detail)
        self.details.setVisible(self.details.count() > 0)

    def pop_out(self, panel):
        """A receiver's detail in its own window, or (popped out already) back."""
        if panel.window:
            panel.window.close()
            return
        self.details.removeWidget(panel.detail)
        panel.window = DetailWindow(self, panel, self._pop_in)
        panel.pop_btn.setText('\u21a9  Dock')
        panel.pop_btn.setToolTip('Put this receiver back under the station rows')
        panel.window.show()
        docked = [p for p in self.panels if not p.window]
        self.focus(docked[0] if docked else panel)

    def _pop_in(self, panel):
        panel.window = None
        panel.pop_btn.setText('\u29c9  Pop out')
        panel.pop_btn.setToolTip('Show this receiver in its own window (double-clicking its row does the same)')
        self.details.addWidget(panel.detail)
        self.focus(panel)

    def _feed_port(self, panel):
        """The receiver's RDS feed port: its own setting, else --rds-port + receiver number - 1."""
        if not self.open_feed:
            return None
        return panel.settings.rds_port or self.open_feed.base_port + panel.slot

    def _set_feed(self, panel, on):
        """Open, move or close a receiver's RDS feed."""
        port = self._feed_port(panel)
        if panel.feed and (not on or panel.feed.port != port):
            panel.station.rds.group_sink = None
            panel.feed.close()
            panel.feed = None
        if on and not panel.feed and self.open_feed:
            panel.feed = self.open_feed(panel.slot, port)
            if panel.feed:
                panel.station.rds.group_sink = panel.feed.send_group
            else:
                self.log(f'receiver {panel.slot + 1}: RDS feed not started, TCP port {port} is in use')
        self._feed_clients[panel.slot] = 0

    def save(self):
        if self.config_path:
            save_config(self.config_path, self.panels, self.notify_settings, self.app_config)

    # ------------------------------------------------------------ notifications
    def _where(self):
        host = socket.gethostname()
        return host, (f'http://{host}:{self.web.port}/' if self.web else None)

    def set_notify(self, settings):
        self.notify_settings = self.notifier.settings = settings

    def _app_settings(self):
        dialog = AppSettingsDialog(self, self.notify_settings, self.notifier)
        result = dialog.exec_()
        if result == AppSettingsDialog.RUN_SETUP:
            self.run_setup()
            return
        if result != QtWidgets.QDialog.Accepted:
            return
        self._apply_notify(dialog.settings())
        self._apply_autostart(dialog.autostart.isChecked())

    def run_setup(self):
        """The setup wizard again, from Settings."""
        old = self.app_config or AppConfig(setup_done=True)
        wizard = SetupWizard(self, old, self.notify_settings, self.notifier, first_run=False)
        if wizard.exec_() != QtWidgets.QDialog.Accepted:
            return
        new = self.app_config = wizard.app_config()
        self._apply_notify(wizard.notify_settings())
        self._apply_autostart(wizard.autostart())
        if new.web_password_hash != old.web_password_hash:
            if self.web:
                self.web.set_password_hash(new.web_password_hash)
            self.log('web: password ' + ('set' if new.web_password_hash else 'removed')
                     + ('' if not self.web or not self.web.password else
                        ' (--web-password / FM_MODMON_WEB_PASSWORD is used while it is given)'))
        later = [what for what, changed in (
            ('the country', new.country != old.country),
            ('web access', (new.web_port, new.web_bind) != (old.web_port, old.web_bind))) if changed]
        if later:
            self.log('setup: ' + ' and '.join(later) + ' change at the next start')
        self.save()

    def _apply_notify(self, new):
        if new != self.notify_settings:
            self.set_notify(new)
            self.save()
            on = [n for n, v in (('email', new.email), ('webhook', new.webhook)) if v]
            self.log('notifications: ' + (' and '.join(on) if on else 'off'))

    def _apply_autostart(self, on):
        if on != autostart_enabled():
            try:
                set_autostart(on)
                self.log('start with Windows: ' + ('on' if on else 'off'))
            except (OSError, subprocess.SubprocessError) as e:
                self.log(f'start with Windows: could not change it: {e}')

    # ------------------------------------------------------------ SDR watchdog
    def start_watchdog(self):
        """Called once the flowgraph runs: from now on, no samples for SDR_STALL_S means the SDR is lost."""
        self._watch_from = time.monotonic()
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self._watch_sdr)
        timer.start(1000)

    def _last_samples(self):
        times = [st.meter.last_update for st in self.tb.stations if st.meter.last_update]
        return max(times + [self._watch_from or 0])

    def _watch_sdr(self):
        rec = self._recovery
        if rec:
            if rec.get('done'):
                self._sdr_recovered(rec)
            elif rec.get('error') and rec.get('error') != rec.get('logged'):
                rec['logged'] = rec['error']
                self.log(f'SDR: reopening attempt {rec["attempt"]} failed: {rec["error"]}')
                self._update_window()
            else:
                self._update_window()
            return
        silent = time.monotonic() - self._last_samples()
        if self._watch_from and silent > SDR_STALL_S:
            self._sdr_lost(silent)
            return
        self._watch_overload()

    def _watch_overload(self):
        """Once a second: warn when the wideband samples reach the ADC's full scale
        (not while calibrating: its gain steps overload on purpose)."""
        peak = self.tb.adc.take()
        if self._cal:
            return
        change = self.overload.update(peak)
        if change is None:
            return
        if change:
            text = (f'SDR overload: the RSP1A\'s wideband samples reach {_dbfs(peak):.1f} dBFS (clipping from '
                    f'{_dbfs(CAL_CLIP):.1f}): every receiver\'s readings may be false. Recalibrate gain, '
                    'or with --lna / --ifgr use less gain (higher values)')
        else:
            text = f'SDR overload cleared: no wideband peak at {_dbfs(CAL_CLIP):.1f} dBFS for {ADC_OVERLOAD_CLEAR_S} s'
        self.log(text)
        self.notifier.event('sdr', text)
        self._update_window()

    def _sdr_lost(self, silent):
        rec = self._recovery = {'since': time.time(), 'attempt': 0, 'error': None}
        text = f'SDR lost: no samples from the RSP1A for {silent:.0f} s; reopening it'
        self.log(text)
        self.notifier.event('sdr', text)
        for p in self.panels:
            p.alarms.hold()     # a silent SDR isn't the stations' fault
        threading.Thread(target=self._recover, args=(rec,), daemon=True).start()
        self._update_window()

    def _recover(self, rec):
        """Background: let go of the SDR, then reopen it until samples flow again."""
        try:
            self.tb.detach_sdr()
        except Exception as e:  # noqa: BLE001 - reported; reopening is tried anyway
            rec['error'] = f'letting go of it: {e}'
        while True:
            rec['attempt'] += 1
            try:
                self.tb.attach_sdr()
                t0 = time.monotonic()
                while time.monotonic() - t0 < 6:
                    time.sleep(0.25)
                    if self._last_samples() > t0:
                        rec['done'] = True
                        return
                rec['error'] = 'opened, but no samples came'
                self.tb.detach_sdr()
            except Exception as e:  # noqa: BLE001 - not there yet (unplugged, driver restarting): try again
                rec['error'] = str(e) or type(e).__name__
                try:
                    self.tb.detach_sdr()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(SDR_RETRY_S[min(rec['attempt'] - 1, len(SDR_RETRY_S) - 1)])

    def _sdr_recovered(self, rec):
        self._recovery = None
        text = (f'SDR recovered after {time.time() - rec["since"]:.0f} s '
                f'({rec["attempt"]} attempt{"" if rec["attempt"] == 1 else "s"})')
        self.log(text)
        self.notifier.event('sdr', text)
        for p in self.panels:  # the gap would otherwise sit in peak holds, counters and loudness
            p.station.meter.reset()
            p.station.audio_meter.reset()
            p.station.sca_meter.reset()
            p.alarms.hold()
        self._update_window()

    def _on_settings(self, panel):
        port = self._feed_port(panel)
        taken = {self._feed_port(p) for p in self.panels if p is not panel} | getattr(self.open_feed, 'reserved', set())
        dialog = ReceiverDialog(self, panel.slot, panel.settings, port,
                                self.open_feed.base_port + panel.slot if self.open_feed else None, taken,
                                self.country)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        new = dialog.settings()
        new.audio_source = panel.settings.audio_source  # set with the source control, not the dialog
        self._apply_settings(panel, new)

    def _apply_settings(self, panel, new):
        if new == panel.settings:
            return
        panel.settings = new
        panel.station.apply_settings(new)
        self._set_feed(panel, new.rds_feed)
        self.save()
        self.log(f'receiver {panel.slot + 1} settings changed')

    def fit_on_screen(self, centre=False):
        """Size the window to its contents (no larger than the screen) and keep
        it on screen; centre=True centres it on the main monitor."""
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        frame_extra = self.frameGeometry().size() - self.geometry().size()
        width, height = self.width(), self.height()
        max_width, max_height = screen.width() - frame_extra.width(), screen.height() - frame_extra.height()
        if height > max_height:   # the receivers will scroll: leave room for the scroll bar
            width += self.scroll.verticalScrollBar().sizeHint().width()
        self.resize(min(width, max_width), min(height, max_height))
        frame = self.frameGeometry()
        if centre:
            frame.moveCenter(screen.center())
        else:
            frame.moveLeft(max(screen.left(), min(frame.left(), screen.right() - frame.width() + 1)))
            frame.moveTop(max(screen.top(), min(frame.top(), screen.bottom() - frame.height() + 1)))
        self.move(frame.topLeft())

    def _candidate(self):
        """Strongest station not yet open that fits the SDR window with the others."""
        used = [p.station.freq_hz for p in self.panels]
        options = [(f, snr) for f, snr in self.stations if f not in used and _fits(used + [f])]
        if not options:
            return None
        return max(options, key=lambda s: -1 if s[1] is None else s[1])[0]

    def _show_help(self):
        dialog = getattr(self, '_help', None)
        if dialog is None:
            dialog = self._help = HelpDialog(self, help_sections(session=self._session_text()))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _session_text(self):
        """What this run of FM-Modmon-ms is using, for the help."""
        a, tb, c = self.args, self.tb, self.tb.center_hz
        lo, hi = tb.window_hz()
        rows = [('Start command', subprocess.list2cmdline([sys.executable] + sys.argv)),
                ('SDR', f'RSP1A centred on {c / 1e6:.2f} MHz, window {lo / 1e6:.1f}-'
                        f'{hi / 1e6:.1f} MHz, {SAMP_RATE / 1e6:.1f} MS/s'),
                ('Gain', self._gain_text() + ('' if tb.gain_auto else
                                              ' (set by --lna / --ifgr)' if a and a.gain_manual else
                                              ' (default, not calibrated)'))]
        for p in self.panels:
            feed = f'RDS feed TCP {p.feed.port}' if p.feed else 'no RDS feed'
            rows.append((f'Receiver {p.slot + 1}', f'{p.title}, {feed}'))
        if self.web:
            rows.append(('Web version', f'http://{socket.gethostname()}:{self.web.port}/ and '
                                        f'http://localhost:{self.web.port}/; controls '
                                        + ('with the password' if self.web.locked() else 'from this PC only')))
        else:
            rows.append(('Web version', 'off (--web-port 0)'))
        formats = ', '.join(WEB_FORMATS[f]['label'] for f in (self.web.formats if self.web else []))
        rows += [('Web audio', f'{formats}, by {self.ffmpeg}' if self.ffmpeg and formats else
                  'off: ffmpeg not found (--ffmpeg)' if not self.ffmpeg else 'off'),
                 ('IBOC playout', self.nrsc5 or 'off: nrsc5 not found (--nrsc5)'),
                 ('RadioDNS', 'off' if not self.radiodns else
                  f'on, country {self.country}, client identifier '
                  + ('set' if getattr(self.radiodns, 'client_id', None) else 'not set')),
                 ('Notifications', ', '.join(
                     ([f'email to {self.notify_settings.email_to} via {self.notify_settings.smtp_host}']
                      if self.notify_settings.email else []) +
                     ([f'webhook ({self.notify_settings.webhook_format})'] if self.notify_settings.webhook else []))
                  or 'off (Settings)'),
                 ('Start with Windows', 'on' if autostart_enabled() else 'off'),
                 ('Settings file', self.config_path or 'not saved'),
                 ('Event logs', LOG_DIR),
                 ('Image cache', cache_dir())]
        if a:
            rows.append(('RDS feed ports', f'from {a.rds_port} (receiver 1), bound to {a.rds_bind}'
                                           if a.rds_port else 'off (--rds-port 0)'))
        width = max(len(k) for k, _ in rows) + 2
        return '\n'.join(f'{k + ":":<{width}}{v}' for k, v in rows)

    def _gain_text(self):
        tb = self.tb
        if self._recovery:
            rec = self._recovery
            return f'SDR LOST \u2013 reopening (attempt {max(rec["attempt"], 1)}, {time.time() - rec["since"]:.0f} s)'
        if self._cal:
            return 'Gain: calibrating\u2026'
        text = f'LNA {tb.lna} \u00b7 IFGR {tb.ifgr} dB'
        if self.overload.active:
            return text + ' \u00b7 ADC OVERLOAD'
        if not tb.gain_auto:
            return text
        if tb.cal_center_hz != tb.center_hz:
            return text + ' (auto, for another window: recalibrate?)'
        return text + ' (auto)'

    def _recalibrate(self):
        """Run the gain calibration on the running receivers, off the GUI thread."""
        if self._cal or self._recovery:
            return
        cal = self._cal = {'was': f'LNA {self.tb.lna} \u00b7 IFGR {self.tb.ifgr} dB'}

        def run():
            try:
                cal['result'] = self.tb.recalibrate()
            except Exception as e:  # noqa: BLE001 - reported in the event log
                cal['error'] = e

        cal['thread'] = threading.Thread(target=run, daemon=True)
        cal['thread'].start()
        for p in self.panels:
            p.alarms.hold()    # the gain steps aren't the station's fault
        self.cal_btn.setEnabled(False)
        self.log('gain: recalibrating (the receivers hear gain steps for a few seconds)')
        self._update_window()

    def _recalibrate_done(self):
        cal = self._cal
        if not cal or cal['thread'].is_alive():
            return
        self._cal = None
        self.cal_btn.setEnabled(True)
        if 'error' in cal:
            self.log(f'gain: recalibration failed, kept {cal["was"]}: {cal["error"]}')
        else:
            self.log(f'gain: recalibrated, was {cal["was"]}; now {cal["result"]}')
        for p in self.panels:  # the gain steps would otherwise sit in peak holds, counters and loudness
            p.station.meter.reset()
            p.station.audio_meter.reset()
            p.station.sca_meter.reset()
            p.alarms.hold()
        self._update_window()

    def _add_receiver(self):
        freq = self._candidate()
        if freq is None or len(self.panels) >= MAX_RECEIVERS:
            return
        slot, st = self.tb.add_receiver(freq)
        self._add_panel(slot, st)
        self._update_window()
        QtCore.QTimer.singleShot(0, self.fit_on_screen)  # grow, staying on screen
        self.log(f'receiver {slot + 1} added on {freq / 1e6:.1f}')
        self.save()

    def _remove_receiver(self, panel):
        if len(self.panels) <= 1:
            return
        title = panel.title
        self._clear_alarms(panel, 'receiver removed')
        if panel.play.isChecked():
            panel.play.setChecked(False)
        self._set_feed(panel, False)
        audio = self.web.audio.pop(panel.slot + 1, None) if self.web else None
        if audio:
            audio.close_all()
        self.tb.remove_receiver(panel.slot)
        if panel.window:
            panel.window.on_close = None
            panel.window.close()
            panel.window = None
        self.panels.remove(panel)
        self.rows_box.removeWidget(panel.row)
        self.details.removeWidget(panel.detail)
        for w in (panel.row, panel.detail):
            w.deleteLater()
        panel.deleteLater()
        if self.selected is panel:
            self.selected = None
            self.focus(self.panels[0])
        self._feed_clients.pop(panel.slot, None)
        self._update_window()
        self.log(f'receiver {panel.slot + 1} removed ({title})')
        self.save()
        QtCore.QTimer.singleShot(0, self.fit_on_screen)  # shrink to the panels left

    def _update_window(self):
        c = self.tb.center_hz
        lo, hi = self.tb.window_hz()
        window = f'{lo / 1e6:.1f}\u2013{hi / 1e6:.1f} MHz'
        chips = {'sdr': f'RSP1A  {c / 1e6:.2f} MHz', 'window': f'Window {window}',
                 'rate': f'{SAMP_RATE / 1e6:.1f} MS/s', 'gain': self._gain_text(),
                 'found': f'{self.n_found} stations found' if self.scanned else 'no scan'}
        for key, text in chips.items():
            self.chips[key].setText(text)
        self.chip_row.updateGeometry()
        self.chip_row.fit()
        self.header_text = f'RSP1A centred on {c / 1e6:.2f} MHz (window {window})  \u00b7  ' + '  \u00b7  '.join(
            chips[k] for k in ('rate', 'gain', 'found'))
        for p in self.panels:
            p.set_fit([q.station.freq_hz for q in self.panels if q is not p])
            p.remove_btn.setEnabled(len(self.panels) > 1)
            if not p.set_sources(self.nrsc5) and p.source_key().startswith('iboc'):
                p.set_source('analog')  # this station has no IBOC to play
                p.settings.audio_source = 'analog'
                self._apply_audio(p)
        lost = bool(self._recovery)
        self.chips['gain'].setStyleSheet('background: #3a1d1f; color: #ff8a8a; border-color: #6b2a2e;'
                                         if lost or self.overload.active else '')
        self.cal_btn.setEnabled(not lost and not self._cal)
        for p in self.panels:
            p.combo.setEnabled(not lost)
            if lost:
                p.remove_btn.setEnabled(False)
        if lost:
            self.add_btn.setEnabled(False)
            self.add_btn.setToolTip('The SDR is being reopened')
        elif len(self.panels) >= MAX_RECEIVERS:
            self.add_btn.setEnabled(False)
            self.add_btn.setToolTip(f'{MAX_RECEIVERS} receivers is the most this app runs')
        elif self._candidate() is None:
            self.add_btn.setEnabled(False)
            self.add_btn.setToolTip('No other station found fits the SDR window with the open receivers')
        else:
            self.add_btn.setEnabled(True)
            self.add_btn.setToolTip(f'Open a receiver on {self._candidate() / 1e6:.1f} MHz')

    def _on_select(self, panel, freq):
        if freq == panel.station.freq_hz:
            return
        freqs = [freq if p is panel else p.station.freq_hz for p in self.panels]
        if not _fits(freqs):  # greyed-out entries can't normally be picked
            panel.combo.setCurrentIndex(panel.combo.findData(panel.station.freq_hz))
            return
        old = panel.title
        self._clear_alarms(panel, 'receiver retuned')
        self.tb.stop_iboc(panel.slot)       # nrsc5 follows one station; restarted below
        self.tb.set_freq(panel.slot, freq)  # SDR window follows the chosen stations
        panel.reset_display()
        self._update_window()
        self._apply_audio(panel)
        self.log(f'receiver {panel.slot + 1}: {old} -> {freq / 1e6:.1f}')
        if panel.settings.expected_pi or panel.settings.service_names:
            # they described the old station: kept, the PI alarm would call the new one wrong
            panel.settings.expected_pi = panel.settings.service_names = ''
            panel.station.apply_settings(panel.settings)
            self.log(f'receiver {panel.slot + 1}: expected PI and data service names cleared for the new station')
        self.save()

    def _on_play(self, panel, on):
        if on:  # one station at a time
            for p in self.panels:
                if p is not panel and p.play.isChecked():
                    p.play.setChecked(False)
        self._apply_audio(panel)
        panel.play.setText('\u25a0  Stop audio' if on else '\u25b6  Play audio')

    def _on_source(self, panel, key):
        if key == panel.settings.audio_source:
            return
        panel.set_source(key)
        panel.settings.audio_source = key
        self._apply_audio(panel)
        self.save()
        self.log(f'receiver {panel.slot + 1}: audio source {dict(AUDIO_SOURCES)[key]}')

    def _apply_audio(self, panel):
        """Make a receiver's playout match its Play button and audio source,
        starting or stopping nrsc5 for IBOC."""
        st, key, on = panel.station, panel.source_key(), panel.play.isChecked()
        program = int(key[4:]) if on and key.startswith('iboc') else None
        if st.iboc and st.iboc.program != program:
            self.tb.stop_iboc(panel.slot)
        if program is not None and not st.iboc:
            try:
                self.tb.start_iboc(panel.slot, program, self.nrsc5)
            except OSError as e:
                self.log(f'receiver {panel.slot + 1}: IBOC not started: {e}')
        st.set_audio(key, on)

    def _alarm_event(self, panel, desc, raised, detail=''):
        key = (panel.slot, panel.station.freq_hz)
        if raised:
            self.alarm_table.raised(key, panel.title, desc, detail)
        else:
            self.alarm_table.cleared(key, desc)
        self._alarm_tab()
        text = f'{panel.title}: {"ALARM" if raised else "cleared"} - {desc}' + (f': {detail}' if detail else '')
        self.log(text)
        if not self._recovery:
            self.notifier.event('raise' if raised else 'clear', text)

    def _clear_alarms(self, panel, why):
        """Send 'cleared' for a receiver's raised alarms before it stops judging
        them (retuned or removed), so email and webhooks see each one end."""
        for name, desc, _ in ALARM_DEFS:
            if name in panel.alarms.active:
                self._alarm_event(panel, desc, False, why)
        panel.alarms.active.clear()

    def _alarm_tab(self):
        n = self.alarm_table.raised_now()
        self.log_tabs.setTabText(0, f'Alarms \u00b7 {n} raised' if n else 'Alarms')
        self.log_tabs.setTabTextColor(0, QtGui.QColor(RED if n else '#9aa0a6'))

    def _refresh(self):
        self._ticks = getattr(self, '_ticks', 0) + 1
        if self._ticks % UPDATE_HZ == 0 and self.alarm_table.raised_now():
            self.alarm_table.redraw()   # the running durations
        for p in self.panels:
            if p.feed and p.feed.clients != self._feed_clients.get(p.slot, 0):
                n, was = p.feed.clients, self._feed_clients.get(p.slot, 0)
                self.log(f'RDS feed TCP {p.feed.port} (receiver {p.slot + 1}): '
                         f'{"client connected" if n > was else "client disconnected"}, {n} now')
                self._feed_clients[p.slot] = n
            for desc, raised, detail in p.refresh():
                self._alarm_event(p, desc, raised, detail)
            alert = p.station.iboc.status['alert'] if p.station.iboc else None
            if alert != getattr(p, 'last_alert', None):
                if alert:
                    self.log(f'{p.title}: IBOC alert text: {alert}')
                    self.notifier.event('raise', f'{p.title}: IBOC alert text: {alert}')
                p.last_alert = alert
            ps = p.static_ps()
            if ps is not None and self.names.get(p.station.freq_hz, '') != ps:
                self.names[p.station.freq_hz] = ps
                for q in self.panels:
                    q.set_station_name(p.station.freq_hz, ps)
        self._recalibrate_done()
        while True:
            try:
                self.log(self.notifier.results.get_nowait())
            except queue.Empty:
                break
        if self.web and self.web.wanted():
            self._publish()

    def _publish(self):
        """Hand the web view the current state (only while someone is watching)."""
        web = self.web
        state = {
            'ready': True, 'app': APP_NAME, 'time': time.strftime('%H:%M:%S'),
            'chips': [self.chips[k].text() for k in ('sdr', 'window', 'rate', 'gain', 'found')],
            'add': {'enabled': self.add_btn.isEnabled(), 'tip': self.add_btn.toolTip()},
            'calibrating': bool(self._cal),
            'audio_formats': [{'key': f, 'label': WEB_FORMATS[f]['label'], 'canplay': WEB_FORMATS[f]['canplay']}
                              for f in (web.formats if self.ffmpeg else [])],
            'listeners': web.listeners(), 'max_listeners': WEB_MAX_LISTENERS,
            'alarm_defs': [[name, desc, Annunciator.SHORT[name]] for name, desc, _ in ALARM_DEFS],
            'alarm_means': Annunciator.MEANS,
            'alarm_episodes': [{k: e[k] for k in ('station', 'desc', 'start', 'end', 'detail')}
                               for e in self.alarm_table.episodes[-100:]],
            'now': time.time(),
            'peak_hist': [PeakHistogram.LO, PeakHistogram.HI, PeakHistogram.STEP],
            'trend_span_s': TREND_SPAN_S, 'clean': [PEAK_AM_PCT, CLEAN_AM_PCT],
            'rules': {'presets': {k: v['limits'] for k, v in RULES.items()},
                      'by_country': 'ised' if self.country == 'CA' else 'fcc',
                      'limits': [list(x) for x in LIMITS]},
            'events_seq': self.n_events,
            'receivers': [p.web_state(self._feed_port(p),
                                      self.open_feed.base_port + p.slot if self.open_feed else None,
                                      web.audio[p.slot + 1].listeners if p.slot + 1 in web.audio else 0)
                          for p in self.panels],
        }
        web.images = {(p.slot + 1, kind): label.path for p in self.panels
                      for kind, label in (('logo', p.logo_img), ('art', p.art_img))
                      if label.path and not label.isHidden()}
        web.state = json.dumps(_finite(state)).encode()
        web.events = json.dumps(list(self.events)[-100:]).encode()

    def _web_commands(self):
        """Run the web page's control requests, here on the GUI thread."""
        while True:
            try:
                action, args, fut = self.web.commands.get_nowait()
            except queue.Empty:
                return
            if fut is None:  # WebView.note(), not a page request (the page can post /api/log too)
                self.log(args['text'])
                continue
            if not fut.set_running_or_notify_cancel():
                continue
            try:
                fut.set_result(self._web_command(action, args))
            except ValueError as e:
                fut.set_exception(e)
            except Exception as e:  # noqa: BLE001 - reported to the page, the app carries on
                fut.set_exception(ValueError(f'{type(e).__name__}: {e}'))
            self._publish()

    def _web_command(self, action, args):
        """One control from the web page, done as the matching control in the window would."""
        if self._recovery and action in ('add', 'remove', 'select', 'recalibrate'):
            raise ValueError('the SDR is being reopened; try again when it is back')
        if action == 'recalibrate':
            if self._cal:
                raise ValueError('the gain is being calibrated already')
            self._recalibrate()
            return None
        if action == 'add':
            if len(self.panels) >= MAX_RECEIVERS or self._candidate() is None:
                raise ValueError(self.add_btn.toolTip() or 'no receiver can be added')
            self._add_receiver()
            return None
        panel = next((p for p in self.panels if p.slot + 1 == args.get('receiver')), None)
        if panel is None:
            raise ValueError('no such receiver')
        if action == 'select':
            i = panel.combo.findData(args.get('freq'))
            if i < 0 or not panel.combo.model().item(i).isEnabled():
                raise ValueError('that station does not fit the SDR window with the other receivers')
            panel.combo.setCurrentIndex(i)
            self._on_select(panel, panel.combo.itemData(i))
        elif action == 'remove':
            if len(self.panels) <= 1:
                raise ValueError('the last receiver cannot be removed')
            self._remove_receiver(panel)
        elif action == 'source':
            i = panel.source.findData(args.get('source'))
            if i < 0 or not panel.source.model().item(i).isEnabled():
                raise ValueError('that audio source is not available on this receiver')
            self._on_source(panel, panel.source.itemData(i))
        elif action == 'reset_integrated':
            panel.station.audio_meter.reset_integrated()
        elif action == 'settings':
            got = args.get('settings')
            if not isinstance(got, dict):
                raise ValueError('no settings')
            pi = str(got.get('expected_pi', '')).strip()
            if pi and not re.fullmatch(r'[0-9A-Fa-f]{4}', pi):
                raise ValueError('Expected PI is four hex digits (such as C6B2), or empty.')
            merged = panel.settings.to_dict() | got
            merged['audio_source'] = panel.settings.audio_source  # set with the source control
            default = self.open_feed.base_port + panel.slot if self.open_feed else None
            port = int(merged.get('rds_port') or 0) or default
            if self.open_feed and merged.get('rds_feed'):
                if not 1024 <= port <= 65535:
                    raise ValueError('The RDS feed port must be 1024-65535.')
                taken = ({self._feed_port(p) for p in self.panels if p is not panel}
                         | getattr(self.open_feed, 'reserved', set()))
                if port in taken:
                    raise ValueError(f'TCP port {port} is already used by another receiver or the web view.')
            merged['rds_port'] = 0 if port == default else port
            self._apply_settings(panel, ReceiverSettings.from_dict(merged))
        else:
            raise ValueError(f'unknown action {action!r}')
        return None


def build_parser(width=100):
    ap = argparse.ArgumentParser(prog='fm-modmon-ms.py', description=__doc__.split('\n\n')[1],
                                 formatter_class=lambda prog: argparse.HelpFormatter(prog, width=width,
                                                                                     max_help_position=32))
    ap.add_argument('--freqs', type=float, nargs='+', metavar='MHZ',
                    help=f'start with receivers on these stations (1-{MAX_RECEIVERS}) instead of '
                         'the saved receivers, or one on the strongest station found')
    ap.add_argument('--nrsc5', default=os.path.normpath(NRSC5_PATH),
                    help='nrsc5 executable for IBOC playout (default: %(default)s)')
    ap.add_argument('--no-radiodns', action='store_true', help='no RadioDNS lookups')
    ap.add_argument('--radiodns-client-id', default=os.environ.get('RADIODNS_CLIENT_ID'),
                    help='RadioDNS client identifier for providers that need one '
                         '(default: the RADIODNS_CLIENT_ID environment variable)')
    ap.add_argument('--country', type=str.upper,
                    help='ISO country of this receiver: the alarm rules (ISED for CA, else FCC) and '
                         'RadioDNS when a station sends no ECC (default: as set in Setup, else CA)')
    ap.add_argument('--config', default=CONFIG_PATH,
                    help='where receivers and their settings are saved (default: %(default)s)')
    ap.add_argument('--setup', action='store_true',
                    help='open the setup (as at the first start) before starting')
    ap.add_argument('--no-scan', action='store_true',
                    help='skip the band scan; dropdowns then list every channel')
    ap.add_argument('--lna', type=int, help='RSP1A LNA state 0-9, higher = less gain (default: calibrated at '
                                            f'start-up; {CAL_DEFAULT[0]} if only --ifgr is given)')
    ap.add_argument('--ifgr', type=int, help='IF gain reduction 20-59 dB (default: calibrated at start-up; '
                                             f'{CAL_DEFAULT[1]} if only --lna is given)')
    ap.add_argument('--web-port', type=int,
                    help=f'port for the web version (0 = off; default: as set in Setup, else {WEB_PORT})')
    ap.add_argument('--web-bind',
                    help='address the web version listens on (0.0.0.0 = all, 127.0.0.1 = this PC only; '
                         'default: as set in Setup, else all)')
    ap.add_argument('--web-password', default=os.environ.get('FM_MODMON_WEB_PASSWORD'),
                    help='password for the web controls from other computers, instead of the one set in '
                         'Setup (default: the FM_MODMON_WEB_PASSWORD environment variable; with no '
                         'password at all, the controls work only in a browser on this PC)')
    ap.add_argument('--ffmpeg', default=None,
                    help='ffmpeg for the web audio (default: ffmpeg on the PATH, the installer\'s, '
                         'or a WinGet install)')
    ap.add_argument('--web-audio', default=','.join(WEB_FORMATS), metavar='FORMATS',
                    help='web audio formats to offer, the first being the page default '
                         '(default: %(default)s; those ffmpeg can encode)')
    ap.add_argument('--rds-port', type=int, default=RDS_TCP_PORT,
                    help='first TCP port of the raw RDS group feeds, one per receiver '
                         '(default %(default)s, so 7711-7714; 0 = off)')
    ap.add_argument('--rds-bind', default='0.0.0.0',
                    help='address the RDS feeds listen on (default all; 127.0.0.1 = this PC only)')
    return ap


def parse_args(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    args.gain_manual = args.lna is not None or args.ifgr is not None
    args.lna = CAL_DEFAULT[0] if args.lna is None else args.lna
    args.ifgr = CAL_DEFAULT[1] if args.ifgr is None else args.ifgr
    if args.freqs and len(args.freqs) > MAX_RECEIVERS:
        ap.error(f'at most {MAX_RECEIVERS} receivers')
    if args.freqs and round(max(args.freqs) - min(args.freqs), 6) > MAX_SPAN / 1e6:
        ap.error(f'stations must lie within {MAX_SPAN / 1e6:.1f} MHz of each other')
    return args


def choose_stations(args, saved=None):
    """Scan (unless told not to) and return (dropdown list, {slot: freq} to open, IBOC scan info).

    Receivers open from --freqs, else the saved ones, else one on the
    strongest station the scan found."""
    if args.no_scan:
        found, iboc_scan = [], {}
        stations = [(ch * 100000, None) for ch in CHANNELS_MHZ10]
    else:
        print('Scanning the FM band...', flush=True)
        found, iboc_scan = band_scan(args.lna, args.ifgr)
        print('Found:', ', '.join(f'{f / 1e6:.1f} ({snr:.0f} dB{", IBOC" if isinstance(iboc_scan.get(f), float) else ""})'
                                  for f, snr in found) or 'nothing')
        stations = list(found)
    if args.freqs:
        receivers = {i: int(round(f * 10)) * 100000 for i, f in enumerate(args.freqs)}
    elif saved:
        receivers = {slot: freq for slot, (freq, _) in saved.items()}
    else:
        receivers = {0: (pick_initial(found, n=1) or [int(round(DEFAULT_FREQS_MHZ[0] * 10)) * 100000])[0]}
    known = {f for f, _ in stations}
    stations += [(f, None) for f in set(receivers.values()) if f not in known]
    return sorted(stations), receivers, iboc_scan


def resolve_args(args, app):
    """Fill in what the command line left to the app settings (AppConfig)."""
    args.country = args.country or app.country
    args.web_port = app.web_port if args.web_port is None else args.web_port
    args.web_bind = args.web_bind or app.web_bind
    args.web_password_hash = app.web_password_hash
    return args


def first_run_setup(args):
    """The setup wizard at the first start (or with --setup); returns the AppConfig."""
    app_cfg = load_app(args.config)
    if app_cfg.setup_done and not args.setup:
        return app_cfg
    notify = load_notify(args.config)
    wizard = SetupWizard(None, app_cfg, notify, Notifier(notify, lambda: (socket.gethostname(), None)),
                         first_run=not app_cfg.setup_done)
    if wizard.exec_() == QtWidgets.QDialog.Accepted:
        app_cfg, notify = wizard.app_config(), wizard.notify_settings()
        try:
            if wizard.autostart() != autostart_enabled():
                set_autostart(wizard.autostart())
        except (OSError, subprocess.SubprocessError) as e:
            print(f'start with Windows: could not change it: {e}')
    app_cfg.setup_done = True     # cancelled: the defaults, and no setup at the next start
    save_config(args.config, None, notify, app_cfg)
    return app_cfg


def start_web(args):
    if not args.web_port:
        return None
    try:
        web = WebView(args.web_bind, args.web_port, args.web_password, getattr(args, 'web_password_hash', ''))
    except OSError as e:
        print(f'web version not started (port {args.web_port}): {e}')
        return None
    host = socket.gethostname() if args.web_bind == '0.0.0.0' else args.web_bind
    print(f'Web version: http://{host}:{args.web_port}/  (also http://localhost:{args.web_port}/); controls '
          + ('with the password' if web.locked() else 'from this PC only (no web password)'))
    args.ffmpeg = args.ffmpeg or find_ffmpeg()
    web.formats = ffmpeg_formats(args.ffmpeg, [f.strip() for f in args.web_audio.split(',') if f.strip()])
    if not args.ffmpeg:
        print('ffmpeg not found: the web version has no audio (see --ffmpeg)')
    elif not web.formats:
        print(f'{args.ffmpeg} can encode none of {args.web_audio}: the web version has no audio')
    else:
        print('Web audio:', ', '.join(WEB_FORMATS[f]['label'] for f in web.formats))
    return web


def feed_opener(args):
    """(slot, port) -> RdsGroupServer (None if the port is taken); None if feeds are off."""
    if not args.rds_port:
        return None

    def open_feed(slot, port):
        try:
            feed = RdsGroupServer(args.rds_bind, port)
        except OSError as e:
            print(f'RDS feed for receiver {slot + 1} not started (port {port}): {e}')
            return None
        print(f'RDS groups, receiver {slot + 1}: tcp://{socket.gethostname()}:{port}')
        return feed

    open_feed.base_port = args.rds_port
    open_feed.reserved = {args.web_port} if args.web_port else set()
    return open_feed


def main():
    args = parse_args()
    clear_cache(stale=True)  # caches left by a session that didn't close cleanly
    app = QtWidgets.QApplication(sys.argv)
    install_icon(app)
    apply_dark_theme(app)
    app_cfg = first_run_setup(args)
    resolve_args(args, app_cfg)
    # Started from the shortcut there is no console, so show progress and errors in windows.
    splash = QtWidgets.QSplashScreen(splash_pixmap(app.primaryScreen().logicalDotsPerInch() / 96))
    splash.setFont(QtGui.QFont('Segoe UI', 10))
    splash.show()
    app.processEvents()
    try:
        saved = {} if args.freqs else load_config(args.config)
        if not args.no_scan:
            splash.showMessage('Scanning the FM band…\n', QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter,
                               QtGui.QColor('#9aa0a6'))
            app.processEvents()
        stations, receivers, iboc_scan = choose_stations(args, saved)
        cal_report = None
        if not args.gain_manual:
            def step(text):
                splash.showMessage(f'Setting the gain\u2026\n{text}', QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter,
                                   QtGui.QColor('#9aa0a6'))
                app.processEvents()

            step('')
            args.lna, args.ifgr, cal_report = calibrate_startup(receivers.values(), args.lna, args.ifgr, step)
            print('Gain calibrated:', cal_report)
        tb = FmMonitor(receivers, args.lna, args.ifgr)
        if cal_report:
            tb.gain_auto, tb.cal_center_hz = True, tb.center_hz
        web = start_web(args)
        win = MainWindow(tb, stations, f'LNA {args.lna} · IFGR {args.ifgr} dB', iboc_scan, web,
                         feed_opener(args), {slot: cfg for slot, (_, cfg) in saved.items()}, args.config,
                         args.nrsc5 if os.path.isfile(args.nrsc5) else None,
                         None if args.no_radiodns else RadioDns(args.radiodns_client_id), args.country,
                         args.ffmpeg if web and web.formats else None)
    except Exception as e:  # noqa: BLE001 - anything that stops start-up is shown, then the app exits
        splash.close()
        hint = ('\n\nIs the RSP1A plugged in, and is no other program (such as SDRconnect) using it?'
                if 'RSP' in str(e) or 'sdrplay' in str(e).lower() else '')
        QtWidgets.QMessageBox.critical(None, APP_NAME, f'{APP_NAME} could not start:\n\n{e}{hint}')
        sys.exit(1)
    if cal_report:
        win.log(f'gain: calibrated at start-up, {cal_report}')
    win.args = args
    win.app_config = app_cfg
    win.set_notify(load_notify(args.config))
    win.save()
    # Windows only knows the frame size once the window exists, so open it
    # invisible, centre it, then reveal it: it never appears anywhere else.
    win.setWindowOpacity(0.0)
    win.show()

    def reveal():
        win.fit_on_screen(centre=True)
        win.setWindowOpacity(1.0)
        splash.finish(win)

    QtCore.QTimer.singleShot(0, reveal)

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keepalive = QtCore.QTimer()
    keepalive.timeout.connect(lambda: None)  # lets Python see Ctrl+C
    keepalive.start(250)

    tb.start()
    win.start_watchdog()
    win.notifier.event('startstop', 'FM-Modmon-ms started: ' + ', '.join(p.title for p in win.panels))
    app.aboutToQuit.connect(lambda: (win.log('monitor stopped'), web and web.close_audio(), tb.stop_all_iboc(),
                                     tb.stop(), tb.wait(), clear_cache(),
                                     win.notifier.send_now('startstop', 'FM-Modmon-ms stopped')))
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
