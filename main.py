from fastapi import FastAPI
from routers import standard, plus, premium

app = FastAPI(title="Unified Budget Agent API", version="1.0")

app.include_router(standard.router, prefix="/standard", tags=["Standard"])
app.include_router(plus.router, prefix="/plus", tags=["Plus"])
app.include_router(premium.router, prefix="/premium", tags=["Premium"])

@app.get("/")
def root():
    return {"message": "Welcome to AI Budget API with Standard, Plus, Premium"}
