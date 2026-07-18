import base64
import logging

from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.responses import JSONResponse

from service.serve_service import ServeService, InsufficientPoolDataError
from service.pool_service import PoolService
from service.metrics_service import MetricsService
from service.beacon_service import BeaconService
from model.response.bits_response import BitsResponse
from util.audio_plot import render_audio_plot_base64

from service.stats_service import StatsService, NoArchivedDataError
from service.daily_stats_service import DailyStatsService

from datetime import datetime, timezone

from config import config

logger = logging.getLogger(__name__)

def verify_shared_secret(authorization: str | None = Header(None)) -> None:
    if not config.WELLSPRING_SHARED_SECRET:
        raise HTTPException(status_code=500, detail="Server misconfigured: no auth secret set")

    if authorization != f"Bearer {config.WELLSPRING_SHARED_SECRET}":
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")


def create_app(serve_service: ServeService, pool_service: PoolService, stats_service: StatsService, daily_stats_service: DailyStatsService, metrics_service : MetricsService, beacon_service: BeaconService) -> FastAPI:
    app = FastAPI(title="Wellspring", dependencies=[Depends(verify_shared_secret)])

    @app.get("/bits")
    def handle_get_bits(num_bytes: int = Query(64, gt=0, description="number of bytes to request"), plot: bool = False):
        logger.info('Entered into /bits with num_bytes {} plot {}'.format(num_bytes, plot))
        try:
            bits_response: BitsResponse = serve_service.serve_bits(num_bytes)
        except InsufficientPoolDataError as e:
            logger.warning("Serve request failed: %s", e)
            raise HTTPException(status_code=503, detail="Not enough entropy available, try again shortly")
        except ValueError as e:
            logger.error('Serve request failed: %s, throwing 400', e)
            raise HTTPException(status_code=400, detail=str(e))

        plot_base64 = render_audio_plot_base64(bits_response.audio_samples) if plot else None

        logger.info('Exiting /bits')

        return JSONResponse({
            "num_bytes": num_bytes,
            "bytes": bits_response.data.hex(),
            "audio_plot_png_base64": plot_base64,
            "pairs_discarded": bits_response.pairs_discarded,
            "pairs_kept": bits_response.pairs_kept,
            "total_chunks": bits_response.total_chunks
        })

    @app.get("/stats/hour")
    def handle_get_latest_stats():
        logger.info('Entered into /stats/hour')
        try:
            return stats_service.get_latest_completed_hour_summary()
        except NoArchivedDataError as e:
            logger.warning("Stats request failed: %s", e)
            raise HTTPException(status_code=404, detail='No hourly data available')

    @app.get("/health")
    def handle_health():
        logger.info('Entered into /health')
        return {
            "status": "ok",
            "pool_chunks": pool_service.num_chunks(),
            "pool_bytes": pool_service.num_bytes(),
        }
    @app.get("/stats/day")
    def handle_get_daily_stats():
        logger.info('Entered into /stats/day')
        return daily_stats_service.get_latest_completed_day_summary()

    @app.get("/metrics")
    def handle_get_metrics():
        return metrics_service.get_summary()


    # BEACON
    @app.get("/beacon/latest")
    def handle_get_latest_pulse():
        pulse = beacon_service.get_latest()
        if pulse is None:
            raise HTTPException(status_code=404, detail="No pulses generated yet")
        return pulse

    @app.get("/beacon/pulse/{pulse_index}")
    def handle_get_pulse_by_index(pulse_index: int):
        pulse = beacon_service.get_by_index(pulse_index)
        if pulse is None:
            raise HTTPException(status_code=404, detail="No pulse at that index")
        return pulse

    @app.get("/beacon/at")
    def handle_get_pulse_by_timestamp(timestamp: datetime = Query(...)):
        now = datetime.now(timezone.utc)
        if timestamp > now:
            raise HTTPException(status_code=400, detail="Timestamp is in the future")
        pulse = beacon_service.get_by_timestamp(timestamp)
        if pulse is None:
            raise HTTPException(status_code=404, detail="No pulse found for that timestamp")
        return pulse

    return app