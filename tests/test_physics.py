import math
import pytest

from lab.engine import simulate
from lab.models import Circuit, Device, Experiment


def test_low_frequency_gain_and_spectral_purity():
    r=simulate(Circuit(), Experiment(frequency_hz=1000, amplitude_v=.02))
    assert r['passed']
    assert r['measured_gain'] == pytest.approx(10, rel=.002)
    assert r['distortion'] < .001


def test_bandwidth_matches_independent_dominant_pole_prediction():
    # Closed-loop bandwidth approximately GBW / noise gain. Evaluate in a
    # small-signal region where the slew limiter and rail clamp are inactive.
    c=Circuit()
    f=c.device.gbw_hz/c.gain
    r=simulate(c, Experiment(frequency_hz=f, amplitude_v=.002))
    assert r['measured_gain'] == pytest.approx(c.gain/math.sqrt(2), rel=.015)
    assert r['phase_deg'] == pytest.approx(-45, abs=1.5)
    assert r['distortion'] < .002


def test_slew_limited_case_has_distortion_without_clipping():
    r=simulate(Circuit(), Experiment(frequency_hz=50000, amplitude_v=.2))
    assert not r['passed']
    assert r['distortion'] > .04
    assert r['rail_occupancy'] < .01
    assert .94 < r['slew_utilization'] < 1.06


def test_saturation_is_not_misreported_as_a_valid_design():
    r=simulate(Circuit(), Experiment(frequency_hz=500, amplitude_v=.8))
    assert not r['passed']
    assert r['rail_occupancy'] > .1
    assert r['output_peak_v'] <= 4.01


def test_refined_time_step_preserves_measurements():
    c=Circuit(); e=Experiment(frequency_hz=50000, amplitude_v=.2)
    coarse=simulate(c,e); fine=simulate(c,e,refinement=2)
    assert coarse['measured_gain'] == pytest.approx(fine['measured_gain'], rel=.005)
    assert coarse['distortion'] == pytest.approx(fine['distortion'], abs=.002)


def test_lowpass_intended_rolloff_is_not_a_failure():
    c=Circuit(kind='lowpass', gain=2, cutoff_hz=2000,
              device=Device(gbw_hz=20000000,slew_v_us=20))
    r=simulate(c,Experiment(frequency_hz=2000,amplitude_v=.02))
    assert r['passed']
    assert r['measured_gain'] == pytest.approx(math.sqrt(2), rel=.01)


def test_upgrade_recovers_high_frequency_without_changing_target():
    c=Circuit(); e=Experiment(frequency_hz=100000,amplitude_v=.05)
    before=simulate(c,e)
    upgraded=c.model_copy(update={'device': Device(name='BL-02',gbw_hz=8000000,slew_v_us=8)})
    after=simulate(upgraded,e)
    assert not before['passed'] and after['passed']


def test_json_roundtrip_preserves_experiment_identity():
    c=Circuit();e=Experiment(frequency_hz=1000,amplitude_v=.02)
    a=simulate(c,e)
    b=simulate(Circuit.model_validate_json(c.model_dump_json()),e)
    assert a['id']==b['id']
    assert a['measured_gain']==b['measured_gain']


def test_concurrent_identical_experiments_do_not_corrupt_raw_data():
    from concurrent.futures import ThreadPoolExecutor
    c=Circuit();e=Experiment(frequency_hz=12345,amplitude_v=.017)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda _:simulate(c,e,use_cache=False),range(4)))
    assert len({r['id'] for r in rows})==1
    assert all(r['samples']>2000 and r['passed'] for r in rows)
    assert max(r['measured_gain'] for r in rows)-min(r['measured_gain'] for r in rows)<1e-9
