from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.users import router as user_router
from app.api.review import router as review_router
from app.api.validation import (router as validation_router)
from app.api.admin import (
    router as admin_router,
)


app = FastAPI(
    title="Legal Invoice Tracking API"
)


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(review_router)
app.include_router(
    validation_router
)

app.include_router(admin_router)


from app.api.users import router as user_router

@app.get("/")
def root():
    return {
        "message": "API Running Successfully"
    }
    

    