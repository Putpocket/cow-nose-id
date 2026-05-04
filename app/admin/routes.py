from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/")
async def health_check():
    return {"message": "auth side is alive"}