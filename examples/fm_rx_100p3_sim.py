#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNU Radio Python Flow Graph
# Title: WBFM Receiver 100.3 MHz (Simulation)
# Description: Baseline simulated broadcast WBFM receiver, 100.3 MHz
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
from gnuradio import audio
from gnuradio import blocks
from gnuradio import channels
from gnuradio.filter import firdes
from gnuradio import filter
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import sip
import threading



class fm_rx_100p3_sim(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "WBFM Receiver 100.3 MHz (Simulation)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("WBFM Receiver 100.3 MHz (Simulation)")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "fm_rx_100p3_sim")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.volume = volume = 0.5
        self.samp_rate = samp_rate = 1200000
        self.quad_rate = quad_rate = 240000
        self.noise_voltage = noise_voltage = 0.05
        self.freq_offset = freq_offset = 0
        self.center_freq = center_freq = 94.5e6
        self.audio_rate = audio_rate = 48000

        ##################################################
        # Blocks
        ##################################################

        self._volume_range = qtgui.Range(0, 2, 0.05, 0.5, 200)
        self._volume_win = qtgui.RangeWidget(self._volume_range, self.set_volume, "Volume", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._volume_win, 0, 2, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._noise_voltage_range = qtgui.Range(0, 1, 0.01, 0.05, 200)
        self._noise_voltage_win = qtgui.RangeWidget(self._noise_voltage_range, self.set_noise_voltage, "Noise Voltage", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._noise_voltage_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._freq_offset_range = qtgui.Range(-50000, 50000, 500, 0, 200)
        self._freq_offset_win = qtgui.RangeWidget(self._freq_offset_range, self.set_freq_offset, "Freq Offset (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._freq_offset_win, 0, 1, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.volume_ctl = blocks.multiply_const_ff(volume)
        self.tx_upsample = filter.rational_resampler_ccc(
                interpolation=5,
                decimation=1,
                taps=[],
                fractional_bw=0)
        self.tone_right = analog.sig_source_f(audio_rate, analog.GR_SIN_WAVE, 3000, 0.3, 0, 0)
        self.tone_left = analog.sig_source_f(audio_rate, analog.GR_SIN_WAVE, 1000, 0.4, 0, 0)
        self.throttle = blocks.throttle(gr.sizeof_gr_complex*1, samp_rate,True)
        self.rf_spectrum = qtgui.freq_sink_c(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            center_freq, #fc
            samp_rate, #bw
            "RF Spectrum (100.3 MHz)", #name
            1,
            None # parent
        )
        self.rf_spectrum.set_update_time(0.10)
        self.rf_spectrum.set_y_axis((-140), 10)
        self.rf_spectrum.set_y_label('Relative Gain', 'dB')
        self.rf_spectrum.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.rf_spectrum.enable_autoscale(False)
        self.rf_spectrum.enable_grid(True)
        self.rf_spectrum.set_fft_average(0.2)
        self.rf_spectrum.enable_axis_labels(True)
        self.rf_spectrum.enable_control_panel(False)
        self.rf_spectrum.set_fft_window_normalized(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.rf_spectrum.set_line_label(i, "Data {0}".format(i))
            else:
                self.rf_spectrum.set_line_label(i, labels[i])
            self.rf_spectrum.set_line_width(i, widths[i])
            self.rf_spectrum.set_line_color(i, colors[i])
            self.rf_spectrum.set_line_alpha(i, alphas[i])

        self._rf_spectrum_win = sip.wrapinstance(self.rf_spectrum.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._rf_spectrum_win, 1, 0, 3, 3)
        for r in range(1, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.fm_mod = analog.wfm_tx(
        	audio_rate=audio_rate,
        	quad_rate=quad_rate,
        	tau=(75e-6),
        	max_dev=75e3,
        	fh=(-1.0),
        )
        self.fm_demod = analog.wfm_rcv(
        	quad_rate=quad_rate,
        	audio_decimation=5,
        )
        self.channel_filter = filter.fir_filter_ccf(
            5,
            firdes.low_pass(
                1,
                samp_rate,
                100e3,
                50e3,
                window.WIN_HAMMING,
                6.76))
        self.channel = channels.channel_model(
            noise_voltage=noise_voltage,
            frequency_offset=(freq_offset / samp_rate),
            epsilon=1.0,
            taps=[1.0],
            noise_seed=0,
            block_tags=False)
        self.audio_spectrum = qtgui.freq_sink_f(
            2048, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            audio_rate, #bw
            "Demodulated Audio", #name
            1,
            None # parent
        )
        self.audio_spectrum.set_update_time(0.10)
        self.audio_spectrum.set_y_axis((-120), 10)
        self.audio_spectrum.set_y_label('Relative Gain', 'dB')
        self.audio_spectrum.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.audio_spectrum.enable_autoscale(False)
        self.audio_spectrum.enable_grid(True)
        self.audio_spectrum.set_fft_average(0.2)
        self.audio_spectrum.enable_axis_labels(True)
        self.audio_spectrum.enable_control_panel(False)
        self.audio_spectrum.set_fft_window_normalized(False)


        self.audio_spectrum.set_plot_pos_half(not True)

        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["dark green", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.audio_spectrum.set_line_label(i, "Data {0}".format(i))
            else:
                self.audio_spectrum.set_line_label(i, labels[i])
            self.audio_spectrum.set_line_width(i, widths[i])
            self.audio_spectrum.set_line_color(i, colors[i])
            self.audio_spectrum.set_line_alpha(i, alphas[i])

        self._audio_spectrum_win = sip.wrapinstance(self.audio_spectrum.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._audio_spectrum_win, 4, 0, 3, 3)
        for r in range(4, 7):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.audio_scope = qtgui.time_sink_f(
            1024, #size
            audio_rate, #samp_rate
            "Demodulated Audio (time)", #name
            1, #number of inputs
            None # parent
        )
        self.audio_scope.set_update_time(0.10)
        self.audio_scope.set_y_axis(-1, 1)

        self.audio_scope.set_y_label('Amplitude', "")

        self.audio_scope.enable_tags(True)
        self.audio_scope.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.audio_scope.enable_autoscale(False)
        self.audio_scope.enable_grid(True)
        self.audio_scope.enable_axis_labels(True)
        self.audio_scope.enable_control_panel(False)
        self.audio_scope.enable_stem_plot(False)


        labels = ['Audio', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.audio_scope.set_line_label(i, "Data {0}".format(i))
            else:
                self.audio_scope.set_line_label(i, labels[i])
            self.audio_scope.set_line_width(i, widths[i])
            self.audio_scope.set_line_color(i, colors[i])
            self.audio_scope.set_line_style(i, styles[i])
            self.audio_scope.set_line_marker(i, markers[i])
            self.audio_scope.set_line_alpha(i, alphas[i])

        self._audio_scope_win = sip.wrapinstance(self.audio_scope.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._audio_scope_win, 7, 0, 3, 3)
        for r in range(7, 10):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.audio_out = audio.sink(audio_rate, '', True)
        self.audio_mix = blocks.add_vff(1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.audio_mix, 0), (self.fm_mod, 0))
        self.connect((self.channel, 0), (self.throttle, 0))
        self.connect((self.channel_filter, 0), (self.fm_demod, 0))
        self.connect((self.fm_demod, 0), (self.audio_scope, 0))
        self.connect((self.fm_demod, 0), (self.audio_spectrum, 0))
        self.connect((self.fm_demod, 0), (self.volume_ctl, 0))
        self.connect((self.fm_mod, 0), (self.tx_upsample, 0))
        self.connect((self.throttle, 0), (self.channel_filter, 0))
        self.connect((self.throttle, 0), (self.rf_spectrum, 0))
        self.connect((self.tone_left, 0), (self.audio_mix, 0))
        self.connect((self.tone_right, 0), (self.audio_mix, 1))
        self.connect((self.tx_upsample, 0), (self.channel, 0))
        self.connect((self.volume_ctl, 0), (self.audio_out, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "fm_rx_100p3_sim")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_volume(self):
        return self.volume

    def set_volume(self, volume):
        self.volume = volume
        self.volume_ctl.set_k(self.volume)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.channel.set_frequency_offset((self.freq_offset / self.samp_rate))
        self.channel_filter.set_taps(firdes.low_pass(1, self.samp_rate, 100e3, 50e3, window.WIN_HAMMING, 6.76))
        self.rf_spectrum.set_frequency_range(self.center_freq, self.samp_rate)
        self.throttle.set_sample_rate(self.samp_rate)

    def get_quad_rate(self):
        return self.quad_rate

    def set_quad_rate(self, quad_rate):
        self.quad_rate = quad_rate

    def get_noise_voltage(self):
        return self.noise_voltage

    def set_noise_voltage(self, noise_voltage):
        self.noise_voltage = noise_voltage
        self.channel.set_noise_voltage(self.noise_voltage)

    def get_freq_offset(self):
        return self.freq_offset

    def set_freq_offset(self, freq_offset):
        self.freq_offset = freq_offset
        self.channel.set_frequency_offset((self.freq_offset / self.samp_rate))

    def get_center_freq(self):
        return self.center_freq

    def set_center_freq(self, center_freq):
        self.center_freq = center_freq
        self.rf_spectrum.set_frequency_range(self.center_freq, self.samp_rate)

    def get_audio_rate(self):
        return self.audio_rate

    def set_audio_rate(self, audio_rate):
        self.audio_rate = audio_rate
        self.audio_scope.set_samp_rate(self.audio_rate)
        self.audio_spectrum.set_frequency_range(0, self.audio_rate)
        self.tone_left.set_sampling_freq(self.audio_rate)
        self.tone_right.set_sampling_freq(self.audio_rate)




def main(top_block_cls=fm_rx_100p3_sim, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
