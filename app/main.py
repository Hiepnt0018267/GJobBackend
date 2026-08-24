from fastapi import FastAPI

app = FastAPI(title="GJob API")


@app.get("/")
def root():
    return {"message": "GJob API is running!"}