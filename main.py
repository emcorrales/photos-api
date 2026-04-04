import os
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE_NAME", "photos")

s3 = boto3.client("s3", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)

def _handle_client_error(e: ClientError):
    code = e.response["Error"]["Code"]
    if code == "AccessDenied" or code == "AccessDeniedException":
        raise HTTPException(status_code=403, detail="Access denied to AWS resource")
    raise HTTPException(status_code=500, detail="An internal error occurred")


app = FastAPI(title="Photos API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload", status_code=201)
async def upload_photo(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    photo_id = str(uuid4())
    key = f"{photo_id}/{file.filename}"
    content = await file.read()
    size = len(content)

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=content,
            ContentType=file.content_type,
        )
    except ClientError as e:
        _handle_client_error(e)

    uploaded_at = datetime.now(timezone.utc).isoformat()
    try:
        table.put_item(
            Item={
                "id": photo_id,
                "key": key,
                "filename": file.filename,
                "size": size,
                "content_type": file.content_type,
                "uploaded_at": uploaded_at,
            }
        )
    except ClientError as e:
        _handle_client_error(e)

    return {
        "id": photo_id,
        "key": key,
        "url": f"https://{S3_BUCKET}.s3.amazonaws.com/{key}",
    }


@app.get("/photos")
def list_photos(
    limit: int = 20,
    offset: int = 0,
    sort_by: Literal["date", "name", "size"] = "date",
    order: Literal["asc", "desc"] = "desc",
):
    try:
        response = table.scan()
    except ClientError as e:
        _handle_client_error(e)
    items = response.get("Items", [])

    sort_key = {"date": "uploaded_at", "name": "filename", "size": "size"}[sort_by]
    items.sort(key=lambda x: x[sort_key], reverse=(order == "desc"))

    total = len(items)
    page = items[offset : offset + limit]

    return {
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@app.get("/photos/{photo_id}")
def get_photo(photo_id: str):
    try:
        response = table.get_item(Key={"id": photo_id})
    except ClientError as e:
        _handle_client_error(e)
    item = response.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Photo not found")

    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": item["key"]},
            ExpiresIn=3600,
        )
    except ClientError as e:
        _handle_client_error(e)

    return {"url": url, "metadata": item}
