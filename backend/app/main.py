from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load variables from .env into the process environment before anything else
# imports settings or instantiates SDK clients that read os.environ directly.
load_dotenv()

from .api.routers import auth, plans, users

app = FastAPI(title="AI Study Planner", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(plans.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
