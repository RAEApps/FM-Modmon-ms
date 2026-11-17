"""Installer check: is an SDRplay RSP visible through SoapySDR?

Run by the installer with radioconda's python:  python check_rsp.py <SoapySDRPlay3 module dir>
Prints the first device's label and exits 0, or exits 1 when no RSP is found.
"""
import os
import sys

SDRPLAY_API_DIR = r'C:\Program Files\SDRplay\API\x64'

os.environ['SOAPY_SDR_PLUGIN_PATH'] = sys.argv[1]
os.environ['PATH'] = os.pathsep.join([SDRPLAY_API_DIR, os.path.join(sys.prefix, 'Library', 'bin'),
                                      os.environ.get('PATH', '')])

import SoapySDR  # noqa: E402 - needs the environment above

SoapySDR.setLogLevel(SoapySDR.SOAPY_SDR_ERROR)
found = SoapySDR.Device.enumerate('driver=sdrplay')
if not found:
    sys.exit(1)
print(found[0]['label'] if 'label' in found[0] else 'SDRplay RSP')
