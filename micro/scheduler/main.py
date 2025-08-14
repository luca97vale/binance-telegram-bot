# main.py
import logging
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from scheduler_service import PortfolioScheduler
from database import DatabaseManager
from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler instance
portfolio_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global portfolio_scheduler

    # Startup
    logger.info("🚀 Starting Crypto Portfolio Scheduler Microservice")

    try:
        # Initialize database
        db_manager = DatabaseManager()
        db_manager.init_hypertable()

        # Start scheduler
        portfolio_scheduler = PortfolioScheduler()
        portfolio_scheduler.start()

        logger.info("✅ Microservice started successfully")
        yield

    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise

    # Shutdown
    logger.info("🛑 Shutting down microservice")
    if portfolio_scheduler:
        portfolio_scheduler.stop()
        await portfolio_scheduler.cleanup()
    logger.info("✅ Microservice shutdown complete")


# FastAPI app
app = FastAPI(
    title="Crypto Portfolio Scheduler",
    description="Microservice for scheduling daily crypto portfolio snapshots",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "crypto-portfolio-scheduler"}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    global portfolio_scheduler

    is_scheduler_running = portfolio_scheduler and portfolio_scheduler.running

    return {
        "status": "healthy" if is_scheduler_running else "degraded",
        "scheduler_running": is_scheduler_running,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/snapshot/manual")
async def manual_snapshot():
    """Trigger manual snapshot"""
    global portfolio_scheduler

    if not portfolio_scheduler or not portfolio_scheduler.running:
        raise HTTPException(status_code=503, detail="Scheduler not running")

    try:
        success = await portfolio_scheduler.manual_snapshot()

        if success:
            return {"status": "success", "message": "Manual snapshot completed"}
        else:
            raise HTTPException(status_code=500, detail="Snapshot failed")

    except Exception as e:
        logger.error(f"Manual snapshot error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_history(days: int = 7):
    """Get recent portfolio history"""
    try:
        db_manager = DatabaseManager()
        history = db_manager.get_recent_values(days)

        # Convert to JSON-serializable format
        result = []
        for record in history:
            result.append({
                "date": record['time'].isoformat(),
                "total_usd": float(record['total_usd'])
            })

        return {"history": result}

    except Exception as e:
        logger.error(f"History query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler status"""
    global portfolio_scheduler

    if not portfolio_scheduler:
        return {"running": False, "jobs": []}

    jobs = []
    for job in portfolio_scheduler.scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })

    return {
        "running": portfolio_scheduler.running,
        "jobs": jobs
    }


# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}")
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    import uvicorn

    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8001,
            reload=False,
            log_level=settings.log_level.lower()
        )
    except KeyboardInterrupt:
        logger.info("👋 Microservice stopped by user")
