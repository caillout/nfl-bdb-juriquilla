"""Configuración común de las pruebas del backend."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from backend.tests.sinteticos import ESPERADO, construir_data_sintetica  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "datos_reales: pruebas que leen los datos reales de data/ (lentas, ~30 s)",
    )


@pytest.fixture(scope="session")
def data_sintetica(tmp_path_factory) -> Path:
    """Carpeta temporal con plays.csv, pffScoutingData.csv, players.csv y tracking/."""
    return construir_data_sintetica(tmp_path_factory.mktemp("data_sintetica"))


@pytest.fixture(scope="session")
def esperado_sintetico() -> dict:
    """Resultados conocidos del conjunto sintético."""
    return ESPERADO


@pytest.fixture(scope="session")
def resultado_sintetico(data_sintetica) -> dict:
    """calcular_todo sobre el conjunto sintético (una vez por sesión)."""
    from backend.offside_service import calcular_todo, cargar_datos

    return calcular_todo(cargar_datos(data_sintetica))


@pytest.fixture(scope="session")
def data_control_perfil(tmp_path_factory) -> Path:
    """Segundo conjunto fijo: escenarios de jugada control y jugadores con >= 100 snaps."""
    from backend.tests.sinteticos import construir_data_control_perfil

    return construir_data_control_perfil(tmp_path_factory.mktemp("data_control_perfil"))


@pytest.fixture(scope="session")
def esperado_cp() -> dict:
    """Resultados conocidos del segundo conjunto fijo."""
    from backend.tests.sinteticos import ESPERADO_CP

    return ESPERADO_CP


@pytest.fixture(scope="session")
def resultado_cp(data_control_perfil) -> dict:
    """calcular_todo sobre el segundo conjunto fijo (una vez por sesión)."""
    from backend.offside_service import calcular_todo, cargar_datos

    return calcular_todo(cargar_datos(data_control_perfil))
