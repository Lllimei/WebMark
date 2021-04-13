from celery import Celery
from glob import glob
import os
import requests
import json

app = Celery('benchmark', broker=os.getenv("BROKER_URL", 'pyamqp://guest@localhost//'))


@app.task(ignore_result=True)
def benchmark_task(metrics_id, molecule, circuit, optimizer_module, optimizer_method):
    if not molecule["transformation"]:
        molecule["transformation"] = None

    # workaround for a Libmark bug
    molecule["structure"] = molecule["structure"].replace("\r", "")
    molecule["active_orbitals"] = molecule["active_orbitals"].replace("\r", "")

    result = run_benchmark(molecule, circuit, optimizer_module, optimizer_method)
    print(result)
    if result is None:
        data = {"error": "error occurred in analysis", "metrics_id": metrics_id}
    else:
        data = {
            "data": json.dumps({
                "metrics_id": metrics_id,
                "average_history": result.average_history,
                "accuracy_history": result.accuracy_history,
                "qubit_count": result.qubit_count,
                "gate_depth": result.gate_depth,
                "average_iterations": result.average_iterations,
                "success_rate": result.success_rate})
        }

    requests.post(
        os.getenv("DJANGO_API_URL", "http://localhost:8000/handleResult"),
        data=data
    )
    remove_output_files()


def remove_output_files():
    """
    Remove output files generated by LibMark
    """

    files_to_remove = glob("*.out") + glob("*.clean") + glob("*.hdf5")

    for file in files_to_remove:
        try:
            os.remove(file)
        except IOError:
            print("Could not remove file:", file)


def run_benchmark(molecule, circuit, optimizer_module, optimizer_method):
    """
    Generate metrics
    """

    # having this import at the top level makes everything explode
    import quantmark as qm

    try:
        optimizer = qm.QMOptimizer(module=optimizer_module, method=optimizer_method)
        backend = qm.QMBackend(backend='qulacs')
        circuit = qm.circuit.circuit_from_string(circuit)
        molecule = qm.molecule.create(
            geometry=molecule["structure"],
            basis_set=molecule["basis_set"],
            active_orbitals=molecule["active_orbitals"],
            transformation=molecule["transformation"]
        )

        return qm.vqe_benchmark(
            molecule=molecule,
            circuit=circuit,
            optimizer=optimizer,
            backend=backend,
            repetitions=100
        )
    except Exception:
        return None
