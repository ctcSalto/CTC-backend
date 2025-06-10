from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from routes import example, auth
from html.welcome import html
import os
from database.database import create_db_and_tables

app = FastAPI(
    title="Backend CTC",
    description="Backend para la aplicación CTC",
    version="0.0.1",
)

@app.get("/" , response_class=HTMLResponse)
def root():
    return html

app.include_router(example.router)
app.include_router(auth.router)

if __name__ == "__main__":
    if not os.path.exists("test.db"):
        create_db_and_tables()
    import uvicorn
    uvicorn.run("main:app", reload=True)
