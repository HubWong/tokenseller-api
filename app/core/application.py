from fastapi import FastAPI
from app.back_jobs.schedule import lifespanJob


fapp = FastAPI(
    title=" Token Maker API",
    description="API for purchasing and managing AI tokens from Chinese providers",
    version="2.0.0",
    lifespan=lifespanJob
)
