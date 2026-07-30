from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "online",
        "application": "pMoni",
        "version": "0.1.0"
    }