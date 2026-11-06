from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from .models import Circuit, Contract, Experiment

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "artifacts" / "runs"
MODEL_VERSION = "bl-opamp-1.1"


def find_ngspice() -> str:
    candidates = [os.getenv("NGSPICE_PATH"), shutil.which("ngspice"),
                  str(ROOT / "vendor" / "Spice64" / "bin" / "ngspice_con.exe")]
    for p in candidates:
        if p and Path(p).is_file():
            return str(Path(p).resolve())
    raise RuntimeError("找不到 ngspice。请运行安装脚本或配置 NGSPICE_PATH。")


def expected_gain(circuit: Circuit, frequency: float) -> float:
    if circuit.kind == "lowpass":
        return circuit.gain / math.sqrt(1 + (frequency / circuit.cutoff_hz) ** 2)
    return circuit.gain


def netlist(circuit: Circuit, experiment: Experiment, refinement: int = 1) -> str:
    """Generic dominant-pole opamp with current-limited integrator and output rails.

    gm/C = 2*pi*GBW; Rdom*gm = A0; Imax/C = SR. This is a transparent
    behavioral model, NOT a foundry model or a particular commercial part.
    """
    d = circuit.device
    cdom = 1e-9
    gm = cdom * 2 * math.pi * d.gbw_hz
    rdom = d.open_loop_gain / gm
    imax = d.slew_v_us * 1e6 * cdom
    f = experiment.frequency_hz
    lines = [
        "BoundaryLab generic nonideal opamp / " + MODEL_VERSION,
        ".options reltol=1e-5 abstol=1e-12 vntol=1e-7",
        f"Vin in 0 SIN(0 {experiment.amplitude_v:.12g} {f:.12g})",
        f"Bgm 0 dom I=max(-{imax:.12g}, min({imax:.12g}, {gm:.12g}*(v(in)-v(fb))))",
        f"Rdom dom 0 {rdom:.12g}",
        f"Cdom dom 0 {cdom:.12g} IC=0",
        f"Baw dom 0 I=0.01*(max(0,v(dom)-{d.swing_v:.12g})+min(0,v(dom)+{d.swing_v:.12g}))",
        f"Brail drive 0 V=max(-{d.swing_v:.12g}, min({d.swing_v:.12g}, v(dom)))",
        f"Rout drive out {d.output_resistance_ohm:.12g}",
        f"Rload out 0 {circuit.load_ohm:.12g}",
        "Cload out 0 10p",
        f"Rf out fb {(circuit.gain-1)*1000:.12g}",
        "Rg fb 0 1000",
    ]
    if circuit.kind == "lowpass":
        # Input RC establishes intended response; follower-style opamp feedback
        # is otherwise identical. Source node renamed to preserve raw input.
        lines[2] = f"Vin source 0 SIN(0 {experiment.amplitude_v:.12g} {f:.12g})"
        lines += ["Rfilter source in 1000", f"Cfilter in 0 {1/(2*math.pi*1000*circuit.cutoff_hz):.12g}"]
    input_node = "source" if circuit.kind == "lowpass" else "in"
    step = 1 / (f * 220 * refinement)
    lines += [
        ".control", "set noaskquit", "set wr_vecnames", "set wr_singlescale",
        f"tran {step:.12g} {14/f:.12g} 0 {step:.12g}",
        f"wrdata samples.tsv v({input_node}) v(out) v(dom)", "quit", ".endc", ".end",
    ]
    return "\n".join(lines) + "\n"


def _measure(raw: np.ndarray, circuit: Circuit, experiment: Experiment) -> dict:
    f = experiment.frequency_hz
    # Uniform resampling over the final four full cycles avoids bias from the
    # adaptive SPICE integration grid. Fit DC, sine and cosine by least squares.
    t = np.linspace(10/f, 14/f, 4*512, endpoint=False)
    vin = np.interp(t, raw[:, 0], raw[:, 1])
    out = np.interp(t, raw[:, 0], raw[:, 2])
    dom = np.interp(t, raw[:, 0], raw[:, 3])
    basis = np.column_stack([np.ones_like(t), np.sin(2*np.pi*f*t), np.cos(2*np.pi*f*t)])
    coeff = np.linalg.lstsq(basis, out, rcond=None)[0]
    amp = float(np.hypot(coeff[1], coeff[2]))
    residual = out - basis @ coeff
    fundamental_rms = amp / math.sqrt(2)
    distortion = float(np.sqrt(np.mean(residual**2)) / max(fundamental_rms, 1e-12))
    target = expected_gain(circuit, f)
    measured = amp / experiment.amplitude_v
    rail_loaded = circuit.device.swing_v * circuit.load_ohm / (circuit.load_ohm + circuit.device.output_resistance_ohm)
    max_slope = float(np.quantile(np.abs(np.gradient(dom, t)), 0.98) / 1e6)
    return {
        "expected_gain": target, "measured_gain": measured,
        "gain_error": abs(measured / target - 1), "distortion": distortion,
        "phase_deg": float(np.degrees(np.arctan2(coeff[2], coeff[1]))),
        "output_peak_v": float(np.max(np.abs(out))),
        "rail_occupancy": float(np.mean(np.abs(out) >= 0.985 * rail_loaded)),
        "slew_observed_v_us": max_slope,
        "slew_utilization": max_slope / circuit.device.slew_v_us,
        "dc_offset_v": float(coeff[0]),
        "waveform": {"time_us": ((t[-1024:]-t[-1024])*1e6).round(6).tolist(),
                     "input_v": vin[-1024:].round(7).tolist(),
                     "output_v": out[-1024:].round(7).tolist(),
                     "ideal_v": (vin[-1024:]*circuit.gain).round(7).tolist() if circuit.kind == "amplifier" else None},
    }


def simulate(circuit: Circuit, experiment: Experiment, contract: Contract | None = None,
             refinement: int = 1, use_cache: bool = True) -> dict:
    contract = contract or Contract()
    identity = {"circuit": circuit.model_dump(), "experiment": {
        "frequency_hz": experiment.frequency_hz, "amplitude_v": experiment.amplitude_v},
        "refinement": refinement, "model_version": MODEL_VERSION}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    folder = RUNS / key
    folder.mkdir(parents=True, exist_ok=True)
    result_path = folder / "measurement.json"
    cached = result_path.exists() and use_cache
    if cached:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        source = netlist(circuit, experiment, refinement)
        (folder / "circuit.cir").write_text(source, encoding="ascii")
        started = time.perf_counter()
        # No shell; user input cannot inject directives into the fixed template.
        proc = subprocess.run([find_ngspice(), "-b", "circuit.cir"], cwd=folder,
                              capture_output=True, timeout=20, creationflags=0x08000000 if os.name == "nt" else 0)
        elapsed = time.perf_counter() - started
        log = proc.stdout.decode("utf-8", errors="replace") + proc.stderr.decode("utf-8", errors="replace")
        (folder / "simulator.log").write_text(log, encoding="utf-8")
        data_path = folder / "samples.tsv"
        if proc.returncode != 0 or not data_path.exists():
            raise RuntimeError(f"ngspice 运行失败（{key}），请检查对应 simulator.log")
        raw = np.loadtxt(data_path, skiprows=1)
        if raw.ndim != 2 or raw.shape[1] != 4 or not np.isfinite(raw).all():
            raise RuntimeError(f"无效仿真数据（{key}）")
        result = {"id": key, "engine": "ngspice-47", "model_version": MODEL_VERSION,
                  "circuit": circuit.model_dump(), "experiment": identity["experiment"],
                  "elapsed_s": round(elapsed, 4), "samples": len(raw), **_measure(raw, circuit, experiment)}
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "config.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    result = dict(result)
    result["cached"] = cached
    result["purpose"] = experiment.purpose
    result["passed"] = bool(result["gain_error"] <= contract.gain_error_limit and result["distortion"] <= contract.distortion_limit)
    result["margin"] = min(1-result["gain_error"]/contract.gain_error_limit,
                           1-result["distortion"]/contract.distortion_limit)
    result["contract"] = contract.model_dump()
    return result


def brief(result: dict) -> dict:
    """Small, credential-free observation sent to the decision model."""
    fields = ["id", "experiment", "purpose", "expected_gain", "measured_gain", "gain_error", "distortion",
              "phase_deg", "output_peak_v", "rail_occupancy", "slew_utilization", "passed", "margin"]
    return {k: result[k] for k in fields if k in result}
