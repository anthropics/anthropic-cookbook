# Avian magnetoreception on a real quantum computer

Claude acts as a co-scientist for a quantum-biology experiment: the radical-pair
mechanism that lets migratory birds read Earth's magnetic field.

In `avian_magnetoreception.ipynb`, Claude designs a quantum circuit for the electron-spin
dynamics, we run it on a simulator and on IBM's real superconducting hardware, Claude
interprets the results, and then Claude answers the question most quantum demos skip:
does this problem actually need a quantum computer at all? The honest answer here is no,
and working out why is the most useful part of the notebook.

## What it covers

- Modeling the radical-pair "chemical compass" as a three-qubit spin Hamiltonian.
- Using Claude to design the singlet preparation, the Trotterized time evolution, and the
  readout basis.
- A field-angle sweep shown three ways on one plot: exact theory, simulator, and a real
  `ibm_kingston` hardware run of the same circuits (mean absolute error about 0.015).
- A more realistic error-mitigated flavin model (spin-1 nitrogen) on real hardware, showing
  the compass switch on at Earth's field and off at a weak paleomagnetic field.
- Claude's critical verdict on quantum advantage: for the singlet-yield observable, a
  laptop typicality estimator stays accurate as the nuclear bath grows, so quantum hardware
  is not needed for the headline number.

## Running it

Everything runs on a laptop. The hardware results are pre-recorded in `data/`, so no IBM
account or queue is needed to reproduce the plots.

```bash
pip install "qiskit>=1.0" "qiskit-aer>=0.14" "qiskit-ibm-runtime>=0.20" "anthropic>=0.30" matplotlib scipy
export ANTHROPIC_API_KEY=sk-ant-...
jupyter notebook avian_magnetoreception.ipynb   # Run All
```

To submit the sweep to real hardware yourself, set up an IBM Quantum account once and flip
`RUN_ON_HARDWARE = True` in the notebook.

## Bundled data

- `data/hardware_sweep.json`: the single-nucleus sweep on `ibm_kingston`, job
  `d94n6clgc6cc73ffas6g` (10 field angles, 1024 shots each).
- `data/compass_ladder_result_v2.json`: the error-mitigated spin-1 flavin compass, job
  `d94t21cql68s73c9uod0` (8192 shots, dynamical decoupling plus twirling).
- `data/frontier_benchmark.json`: the classical exact-vs-typicality benchmark versus bath
  size, with a fixed sample count so the accuracy comparison is clean.
