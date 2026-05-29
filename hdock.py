import subprocess
import time
import logging
from pathlib import Path
from typing import List, Tuple
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("HDOCK")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class HDOCKEvaluator:
    def __init__(
        self,
        docker_image: str = "hdock",
        n_models: int = 100,
    ):
        self.docker_image = docker_image
        self.n_models = n_models
        logger.info(
            f"Initialized HDOCKEvaluator with image='{docker_image}' | n_models={n_models}"
        )

    def _run_single_dock(
        self,
        receptor_file: str,
        ligand_file: str,
        output_file: str,
        idx: int,
    ) -> Tuple[int, str, str, bool]:

        start_time = time.time()

        receptor_path = Path(receptor_file).resolve()
        ligand_path = Path(ligand_file).resolve()
        output_path = Path(output_file).resolve()

        logger.info(f"[{idx}] Starting docking | ligand={ligand_path.name}")

        if not receptor_path.exists():
            logger.error(f"[{idx}] Receptor not found: {receptor_path}")
            raise FileNotFoundError(receptor_path)

        if not ligand_path.exists():
            logger.error(f"[{idx}] Ligand not found: {ligand_path}")
            raise FileNotFoundError(ligand_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # HDOCKlite produces two outputs:
        #   - Hdock.out  : raw docking solutions file
        #   - top<N>.pdb : complex models (if create_models=True)
        # We treat the Hdock.out path as output_file; the .pdb lives alongside it.
        hdock_out_name = "Hdock.out"
        models_name = f"top{self.n_models}.pdb"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            shutil.copy2(receptor_path, temp_path / receptor_path.name)
            shutil.copy2(ligand_path, temp_path / ligand_path.name)

            cmd = [
                "docker", "run", "--rm",
                "-v", f"{temp_path}:/docking",
                self.docker_image,
                f"""
                set -e &&
                cd /docking &&
                hdock {receptor_path.name} {ligand_path.name} -out {hdock_out_name} &&
                createpl {hdock_out_name} {models_name} -nmax {self.n_models} -complex -models
                """
            ]

            logger.debug(f"[{idx}] Docker command:\n{' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            elapsed = time.time() - start_time

            # Allow the filesystem to flush
            time.sleep(0.2)

            temp_hdock_out = temp_path / hdock_out_name
            temp_models = temp_path / models_name

            if not temp_hdock_out.exists():
                logger.warning(
                    f"[{idx}] Dock completed but Hdock.out missing ({elapsed:.2f}s) | "
                    f"stderr: {result.stderr.strip()}"
                )
                return (idx, ligand_file, str(output_path), False)

            # Copy Hdock.out to the caller-specified output path
            shutil.copy2(temp_hdock_out, output_path)

            # Copy the PDB models next to the output file if they were produced
            if temp_models.exists():
                models_dest = output_path.parent / models_name
                shutil.copy2(temp_models, models_dest)
                logger.info(
                    f"[{idx}] Models written → {models_dest}"
                )
            else:
                logger.warning(
                    f"[{idx}] createpl did not produce {models_name}"
                )

            logger.info(
                f"[{idx}] Dock SUCCESS ({elapsed:.2f}s) → {output_path}"
            )

            return (idx, ligand_file, str(output_path), True)

    def dock(
        self,
        receptor_file: str,
        ligand_file: str,
        output_file: str,
    ) -> bool:
        """Run a single docking job. Returns True on success."""
        _, _, _, success = self._run_single_dock(
            receptor_file,
            ligand_file,
            output_file,
            idx=0,
        )
        return success

    def dock_multiple(
        self,
        receptor_files: List[str],
        ligand_files: List[str],
        output_files: List[str],
        workers: int = 4,
    ) -> List[Tuple[str, str, bool]]:
        """
        Run multiple docking jobs in parallel.

        Returns a list of (ligand_file, output_file, success) tuples in the
        same order as the input lists.
        """
        if not (len(receptor_files) == len(ligand_files) == len(output_files)):
            raise ValueError(
                "receptor_files, ligand_files, and output_files must be the same length"
            )

        num_jobs = len(ligand_files)

        logger.info(
            f"Starting batch docking | jobs={num_jobs} | workers={workers}"
        )

        results: List[Tuple[int, str, str, bool]] = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_idx = {
                executor.submit(
                    self._run_single_dock,
                    receptor_files[idx],
                    ligand_files[idx],
                    output_files[idx],
                    idx,
                ): idx
                for idx in range(num_jobs)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results.append(future.result())
                except Exception:
                    logger.exception(f"[{idx}] Unhandled exception during docking")
                    results.append(
                        (idx, ligand_files[idx], output_files[idx], False)
                    )

        # Restore original order
        results.sort(key=lambda x: x[0])

        success_count = sum(success for _, _, _, success in results)

        logger.info(
            f"Batch complete | success={success_count}/{num_jobs}"
        )

        # Drop internal index before returning
        return [
            (ligand, output, success)
            for _, ligand, output, success in results
        ]