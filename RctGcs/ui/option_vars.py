'''GCS Option Vars
'''
from dataclasses import dataclass, field
from typing import Callable, Dict, List, NewType, Tuple, Type, TypeVar

from PyQt5 import QtCore, QtWidgets

from RctGcs.rctCore import ENG_OPTIONS, MAVModel, NoActiveModel, Options
from RctGcs.ui.widgets import IntArrayEdit

T = TypeVar('T')
V = TypeVar('V')
Widget = NewType('Widget', QtWidgets.QWidget)
@dataclass
class OptionVar:
    """GCS Option Variable Table Entries

    `set_fn` and `get_fn` shall take in an object with type `widget_class`
    """
    widget_class: Type[Widget]
    set_fn: Callable[[Widget, T], None]
    get_fn: Callable[[Widget], T]
    label: str
    modified_signal: str
    tf_fns: Tuple[Callable[[V], T], Callable[[T], V]] = None
    widgets: List[Widget] = field(default_factory=list)
    changed: bool = False

    def make_label(self, parent: QtWidgets.QWidget) -> QtWidgets.QLabel:
        """Convenience function to create a label widget

        Args:
            parent (QtWidgets.QWidget): Parent widget

        Returns:
            QtWidgets.QLabel: Label widget
        """
        new_widget = QtWidgets.QLabel(self.label, parent)
        return new_widget

    def make_widget(self, parent: QtWidgets.QWidget) -> Widget:
        """Convenience function to create a new widget

        Args:
            parent (QtWidgets.QWidget): Parent widget

        Returns:
            Widget: Option edit widget
        """
        new_widget = self.widget_class(parent)
        modified_signal: QtCore.pyqtBoundSignal = getattr(new_widget, self.modified_signal)
        modified_signal.connect(self.set_modified)
        self.widgets.append(new_widget)
        return new_widget

    def make_pair(self, parent: QtWidgets.QWidget) -> Tuple[QtWidgets.QLabel, Widget]:
        """Convenience function to create a label and widget pair

        Args:
            parent (QtWidgets.QWidget): Parent widget

        Returns:
            Tuple[QtWidgets.QLabel, Widget]: Label and entry
        """
        return (self.make_label(parent), self.make_widget(parent))

    def set_all(self, value: V) -> None:
        """Convenience function to populate all widget intances

        Args:
            value (V): Value to set
        """
        if self.tf_fns:
            value = self.tf_fns[0](value)
        for widget in self.widgets:
            self.set_fn(widget, value)
            widget.repaint()
            widget.setEnabled(True)
        self.changed = False

    def set_modified(self, *args) -> None:
        self.changed = True


option_var_table: Dict[Options, OptionVar] = {
    Options.DSP_PING_WIDTH: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Expected Ping Width (ms)',
        tf_fns=(str, float),
    ),
    Options.DSP_PING_SNR: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Min Ping SNR (dB)',
        tf_fns=(str, float),
    ),
    Options.DSP_PING_MAX: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Max Width Multiplier',
        tf_fns=(str, float),
    ),
    Options.DSP_PING_MIN: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Min Width Multiplier',
        tf_fns=(str, float),
    ),
    Options.GCS_SPEC: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Payload\'s Interface Specifier',
    ),
    Options.GPS_BAUD: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='GPS Baud Rate',
        tf_fns=(str, int),
    ),
    Options.GPS_DEVICE: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='GPS Port',
    ),
    Options.GPS_MODE: OptionVar(
        widget_class=QtWidgets.QCheckBox,
        set_fn=QtWidgets.QCheckBox.setChecked,
        get_fn=QtWidgets.QCheckBox.isChecked,
        modified_signal='stateChanged',
        label='GPS Test Mode',
    ),
    Options.SDR_SAMPLING_FREQ: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Sampling Frequency (Hz)',
        tf_fns=(str, int),
    ),
    Options.SDR_CENTER_FREQ: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Center Frequency (Hz)',
        tf_fns=(str, int),
    ),
    Options.SDR_GAIN: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='SDR Gain (dB)',
        tf_fns=(str, float)
    ),
    Options.SYS_AUTOSTART: OptionVar(
        widget_class=QtWidgets.QCheckBox,
        set_fn=QtWidgets.QCheckBox.setChecked,
        get_fn=QtWidgets.QCheckBox.isChecked,
        modified_signal='stateChanged',
        label='Autostart Enabled'
    ),
    Options.SYS_OUTPUT_DIR: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Payload Output Directory',
    ),
    Options.SYS_NETWORK: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='WiFi Network (to monitor)',
    ),
    Options.SYS_WIFI_MONITOR_INTERVAL: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='WiFi Network Monitor Interval (s)',
        tf_fns=(str, int),
    ),
    Options.SYS_HEARTBEAT_PERIOD: OptionVar(
        widget_class=QtWidgets.QLineEdit,
        set_fn=QtWidgets.QLineEdit.setText,
        get_fn=QtWidgets.QLineEdit.text,
        modified_signal='textChanged',
        label='Payload Heartbeat Interval (s)',
        tf_fns=(str, int),
    ),
    Options.TGT_FREQUENCIES: OptionVar(
        widget_class=IntArrayEdit,
        set_fn=IntArrayEdit.set_values,
        get_fn=IntArrayEdit.get_values,
        modified_signal='onModified',
        label='Target Frequencies (Hz)'
    )
}

def update_option_var_widgets(model_idx: int = None):
    """Overwrites all widget values with values from the specified MAVModel

    Args:
        model_idx (int, optional): MAVModel index. Defaults to the current active MAVModel.
    """
    try:
        model = MAVModel.get_model(idx=model_idx)
    except NoActiveModel:
        for option, params in option_var_table.items():
            for widget in params.widgets:
                widget.setEnabled(False)
                widget.repaint()
        return

    option_values = model.get_options(scope=ENG_OPTIONS, timeout=1)
    for option, value in option_values.items():
        widget_params = option_var_table[option]
        widget_params.set_all(value)

    target_freqs = model.get_frequencies(timeout=1)
    option_var_table[Options.TGT_FREQUENCIES].set_all(target_freqs)
            