from fastapi import APIRouter

router = APIRouter()


@router.get("/",
    summary="Health check endpoint",
    description="This endpoint is used to check the health status of the API service"
)
def health_check() -> str:
    return "Ok"