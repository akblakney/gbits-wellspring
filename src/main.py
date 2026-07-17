"""
Wellspring entrypoint.

Wires together the repository/service/core layers, starts the
background generator, and launches the FastAPI app.

Run from inside src/: `python main.py`
"""

import argparse

import uvicorn

from repository.pool_repository import PoolRepository
from repository.archive_repository import ArchiveRepository
from repository.metrics_repository import MetricsRepository
from repository.stats_repository import StatsRepository
from repository.beacon_repository import BeaconRepository

from service.archive_service import ArchiveService
from service.generation_service import GenerationService
from service.serve_service import ServeService
from service.pool_service import PoolService
from service.metrics_service import MetricsService
from service.stats_service import StatsService
from service.daily_stats_service import DailyStatsService
from service.beacon_service import BeaconService

from core.generator import Generator
from core.beacon_scheduler import BeaconScheduler
from controller.controller import create_app
from config import config
from config.logging_config import configure_logging
from entropy.microphone import MicrophoneSource
from extract.von_neumann import VonNeumannExtractor


def parse_args():
    parser = argparse.ArgumentParser(description="Wellspring server")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Shortcut for --log-level=DEBUG",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging level (DEBUG, INFO, WARNING, ERROR). "
             "Overrides WELLSPRING_LOG_LEVEL env var if set.",
    )
    return parser.parse_args()


def build_repositories() -> dict:
    return {
        "pool": PoolRepository(),
        "archive": ArchiveRepository(),
        "metrics": MetricsRepository(),
        "stats": StatsRepository(config.ARCHIVE_ROOT_PATH),
        "beacon": BeaconRepository(config.BEACON_ROOT_PATH),
    }


def build_services(repos: dict) -> dict:
    metrics_service = MetricsService(repos["metrics"])

    archive_service = ArchiveService(
        repos["pool"], metrics_service, repos["archive"]
    )

    generation_service = GenerationService(repos["pool"], archive_service)

    serve_service = ServeService(repos["pool"], archive_service, metrics_service)

    pool_service = PoolService(repos["pool"])

    stats_service = StatsService(repos["stats"])

    daily_stats_service = DailyStatsService(stats_service, repos["stats"])

    beacon_service = BeaconService(repos["pool"], archive_service, repos["beacon"])

    return {
        "metrics": metrics_service,
        "archive": archive_service,
        "generation": generation_service,
        "serve": serve_service,
        "pool": pool_service,
        "stats": stats_service,
        "daily_stats": daily_stats_service,
        "beacon": beacon_service
    }


def start_generator(services: dict) -> Generator:
    generator = Generator(
        services["generation"], MicrophoneSource(), VonNeumannExtractor()
    )
    generator.start()
    return generator

def start_beacon_scheduler(services: dict) -> BeaconScheduler:
    scheduler = BeaconScheduler(services["beacon"])
    scheduler.start()
    return scheduler


def build_app():
    repos = build_repositories()
    services = build_services(repos)
    start_generator(services) 
    start_beacon_scheduler(services)

    return create_app(
        services["serve"],
        services["pool"],
        services["stats"],
        services["daily_stats"],
        services["metrics"],
        services['beacon']
    )


if __name__ == "__main__":
    args = parse_args()
    configure_logging(level="DEBUG" if args.debug else args.log_level)
    app = build_app()
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT, log_config=None)
else:
    # Imported (e.g. by uvicorn --reload, or tests) rather than run directly:
    # fall back to env var / default since there's no CLI to parse.
    configure_logging()
    app = build_app()