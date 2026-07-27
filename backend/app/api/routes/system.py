from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "online",
        "application": "Monikraft",
        "version": "0.1.0"
    }