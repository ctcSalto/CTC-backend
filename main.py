from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from routes import example, auth
from routes.moodle import moodle_user, moodle_category, moodle_course, moodle_enrolment
from routes.mercadopago import mercadopago

from pages.welcome import html
from database.database import reset_database

import os
from dotenv import load_dotenv
load_dotenv()

from routes.test import test_filters

app = FastAPI(
    title="Backend CTC",
    description="Backend para la aplicación CTC",
    version="0.0.1",
)

@app.get("/" , response_class=HTMLResponse)
def root():
    return html

@app.get("/generate-permanent-token")
def generate_permanent_token():
    return ""

app.include_router(auth.router)
app.include_router(example.router)
app.include_router(moodle_user.router)
app.include_router(moodle_category.router)
app.include_router(moodle_course.router)
app.include_router(moodle_enrolment.router)
app.include_router(mercadopago.router)


app.include_router(test_filters.router)

if __name__ == "__main__":
    # python main.py
    #reset_database()
    import uvicorn
    port = os.getenv("PORT", 8000)
    uvicorn.run("main:app", reload=True, port=port)
