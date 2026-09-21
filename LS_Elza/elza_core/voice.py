"""Host-neutral voice lifecycle contract."""

from enum import Enum


class VoiceState(str, Enum):
    OFF = "OFF"
    IDLE = "IDLE"
    RECORDING = "RECORDING"
    TRANSCRIBING = "TRANSCRIBING"
    GENERATING = "GENERATING"
    SYNTHESIZING = "SYNTHESIZING"
    SPEAKING = "SPEAKING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


_ALLOWED = {
    VoiceState.OFF: {VoiceState.IDLE},
    VoiceState.IDLE: {VoiceState.OFF, VoiceState.RECORDING, VoiceState.ERROR},
    VoiceState.RECORDING: {VoiceState.TRANSCRIBING, VoiceState.STOPPING, VoiceState.ERROR},
    VoiceState.TRANSCRIBING: {VoiceState.GENERATING, VoiceState.STOPPING, VoiceState.ERROR},
    VoiceState.GENERATING: {VoiceState.SYNTHESIZING, VoiceState.STOPPING, VoiceState.ERROR},
    VoiceState.SYNTHESIZING: {VoiceState.SPEAKING, VoiceState.STOPPING, VoiceState.ERROR},
    VoiceState.SPEAKING: {VoiceState.IDLE, VoiceState.STOPPING, VoiceState.ERROR},
    VoiceState.STOPPING: {VoiceState.IDLE, VoiceState.OFF, VoiceState.ERROR},
    VoiceState.ERROR: {VoiceState.IDLE, VoiceState.OFF},
}


class VoiceSession:
    def __init__(self):
        self.state = VoiceState.OFF

    def transition(self, next_state: VoiceState) -> None:
        next_state = VoiceState(next_state)
        if next_state not in _ALLOWED[self.state]:
            raise ValueError(f"Invalid voice transition: {self.state} -> {next_state}")
        self.state = next_state

    @property
    def can_submit(self) -> bool:
        return self.state in {VoiceState.OFF, VoiceState.IDLE}


# Compatibility-safe semantic helpers used by host adapters.
def _voice_set_enabled(self, enabled: bool) -> None:
    enabled = bool(enabled)
    if enabled and self.state == VoiceState.OFF:
        self.transition(VoiceState.IDLE)
    elif not enabled and self.state == VoiceState.IDLE:
        self.transition(VoiceState.OFF)
    elif not enabled and self.state != VoiceState.OFF:
        raise ValueError("Voice can be disabled only from IDLE or OFF.")


def _voice_stop(self) -> None:
    if self.state == VoiceState.OFF:
        return
    if self.state == VoiceState.IDLE:
        return
    if VoiceState.STOPPING in _ALLOWED[self.state]:
        self.transition(VoiceState.STOPPING)
        self.transition(VoiceState.IDLE)
        return
    raise ValueError(f"Voice stop is not valid from {self.state}.")


VoiceSession.set_enabled = _voice_set_enabled
VoiceSession.stop_voice = _voice_stop
