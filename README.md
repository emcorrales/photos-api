# Photos API

A REST API for uploading and managing photos, built with FastAPI, AWS S3, and DynamoDB.

## Requirements

- Python 3.14+
- [Poetry](https://python-poetry.org/)
- AWS account with S3 bucket and DynamoDB table

## Setup

1. Install dependencies:

```bash
poetry install
```

2. Create a `.env` file in the project root:

```env
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-s3-bucket-name
DYNAMODB_TABLE_NAME=photos
```

3. Run the server:

```bash
poetry run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## AWS Resources

### S3 Bucket

Used to store uploaded image files. Each photo is stored under a UUID-prefixed key:

```
{photo_id}/{original_filename}
```

### DynamoDB Table

Used to store photo metadata. The table must have `id` (String) as the partition key.

Each item contains:

| Field          | Type   | Description                        |
|----------------|--------|------------------------------------|
| `id`           | String | UUID, partition key                |
| `key`          | String | S3 object key                      |
| `filename`     | String | Original filename                  |
| `size`         | Number | File size in bytes                 |
| `content_type` | String | MIME type (e.g. `image/jpeg`)      |
| `uploaded_at`  | String | ISO 8601 timestamp (UTC)           |

## API Reference

### Upload a photo

```
POST /upload
```

Uploads an image file to S3 and stores its metadata in DynamoDB.

**Request**

Multipart form data:

| Field  | Type | Description              |
|--------|------|--------------------------|
| `file` | File | Image file to upload     |

Only files with an `image/*` content type are accepted.

**Response** `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "550e8400-e29b-41d4-a716-446655440000/photo.jpg",
  "url": "https://your-bucket.s3.amazonaws.com/550e8400-e29b-41d4-a716-446655440000/photo.jpg"
}
```

**Errors**

| Status | Description                        |
|--------|------------------------------------|
| `400`  | File is not an image               |
| `500`  | S3 upload failed                   |

---

### List photos

```
GET /photos
```

Returns a paginated, sorted list of all uploaded photos.

**Query parameters**

| Parameter | Type   | Default | Description                              |
|-----------|--------|---------|------------------------------------------|
| `limit`   | int    | `20`    | Number of items to return                |
| `offset`  | int    | `0`     | Number of items to skip                  |
| `sort_by` | string | `date`  | Sort field: `date`, `name`, or `size`    |
| `order`   | string | `desc`  | Sort direction: `asc` or `desc`          |

**Response** `200 OK`

```json
{
  "items": [
    {
      "id": "aaa",
      "key": "aaa/photo_a.jpg",
      "filename": "photo_a.jpg",
      "size": 300,
      "content_type": "image/jpeg",
      "uploaded_at": "2024-01-03T00:00:00+00:00"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 20
}
```

---

### Get a photo

```
GET /photos/{photo_id}
```

Returns metadata and a presigned S3 URL for a single photo. The presigned URL expires after **1 hour**.

**Path parameters**

| Parameter  | Description     |
|------------|-----------------|
| `photo_id` | Photo UUID      |

**Response** `200 OK`

```json
{
  "url": "https://presigned-url...",
  "metadata": {
    "id": "aaa",
    "key": "aaa/photo_a.jpg",
    "filename": "photo_a.jpg",
    "size": 300,
    "content_type": "image/jpeg",
    "uploaded_at": "2024-01-03T00:00:00+00:00"
  }
}
```

**Errors**

| Status | Description      |
|--------|------------------|
| `404`  | Photo not found  |

## Running Tests

```bash
poetry run pytest
```

Tests mock all AWS calls (S3 and DynamoDB) and do not require real AWS credentials.

## CORS

The API allows cross-origin requests from `http://localhost:5173` (default Vite dev server).
