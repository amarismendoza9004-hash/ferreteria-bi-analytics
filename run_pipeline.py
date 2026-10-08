"""
Ejecuta todo el proyecto de punta a punta:
    datos simulados -> ETL (scraping + API + limpieza + SQLite) -> análisis y reportes

Uso:
    python run_pipeline.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import analisis       # noqa: E402
import etl            # noqa: E402
import generate_data  # noqa: E402

if __name__ == "__main__":
    t0 = time.time()
    print("=" * 60, "\nPASO 1 · Generando datos simulados\n" + "=" * 60)
    generate_data.main()
    print("\n" + "=" * 60, "\nPASO 2 · ETL\n" + "=" * 60)
    etl.main()
    print("\n" + "=" * 60, "\nPASO 3 · Análisis y reportes\n" + "=" * 60)
    analisis.main()
    print(f"\nPipeline completo en {time.time() - t0:.0f} s")
