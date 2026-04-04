from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

MOCK_ITEMS = [
    {
        "id": "aaa",
        "key": "aaa/photo_a.jpg",
        "filename": "photo_a.jpg",
        "size": 300,
        "content_type": "image/jpeg",
        "uploaded_at": "2024-01-03T00:00:00+00:00",
    },
    {
        "id": "bbb",
        "key": "bbb/photo_b.jpg",
        "filename": "photo_b.jpg",
        "size": 100,
        "content_type": "image/jpeg",
        "uploaded_at": "2024-01-01T00:00:00+00:00",
    },
    {
        "id": "ccc",
        "key": "ccc/photo_c.jpg",
        "filename": "photo_c.jpg",
        "size": 200,
        "content_type": "image/jpeg",
        "uploaded_at": "2024-01-02T00:00:00+00:00",
    },
]


@patch("main.table")
@patch("main.s3")
def test_upload_success(mock_s3, mock_table):
    mock_s3.put_object.return_value = {}
    mock_table.put_item.return_value = {}

    response = client.post(
        "/upload",
        files={"file": ("test.jpg", BytesIO(b"fake image data"), "image/jpeg")},
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "key" in data
    assert "url" in data
    assert data["key"].endswith("/test.jpg")
    mock_s3.put_object.assert_called_once()
    mock_table.put_item.assert_called_once()


@patch("main.table")
@patch("main.s3")
def test_upload_invalid_type(mock_s3, mock_table):
    response = client.post(
        "/upload",
        files={"file": ("doc.pdf", BytesIO(b"pdf content"), "application/pdf")},
    )

    assert response.status_code == 400
    mock_s3.put_object.assert_not_called()
    mock_table.put_item.assert_not_called()


@patch("main.table")
def test_list_photos(mock_table):
    mock_table.scan.return_value = {"Items": MOCK_ITEMS}

    response = client.get("/photos")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["offset"] == 0
    assert data["limit"] == 20


@patch("main.table")
def test_list_photos_empty(mock_table):
    mock_table.scan.return_value = {"Items": []}

    response = client.get("/photos")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@patch("main.table")
def test_list_photos_pagination(mock_table):
    mock_table.scan.return_value = {"Items": MOCK_ITEMS}

    response = client.get("/photos?limit=2&offset=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["offset"] == 1
    assert data["limit"] == 2


@patch("main.table")
def test_list_photos_sort_by_date_desc(mock_table):
    mock_table.scan.return_value = {"Items": MOCK_ITEMS}

    response = client.get("/photos?sort_by=date&order=desc")

    items = response.json()["items"]
    assert items[0]["id"] == "aaa"
    assert items[1]["id"] == "ccc"
    assert items[2]["id"] == "bbb"


@patch("main.table")
def test_list_photos_sort_by_name_asc(mock_table):
    mock_table.scan.return_value = {"Items": MOCK_ITEMS}

    response = client.get("/photos?sort_by=name&order=asc")

    items = response.json()["items"]
    assert items[0]["filename"] == "photo_a.jpg"
    assert items[1]["filename"] == "photo_b.jpg"
    assert items[2]["filename"] == "photo_c.jpg"


@patch("main.table")
def test_list_photos_sort_by_size_desc(mock_table):
    mock_table.scan.return_value = {"Items": MOCK_ITEMS}

    response = client.get("/photos?sort_by=size&order=desc")

    items = response.json()["items"]
    assert items[0]["size"] == 300
    assert items[1]["size"] == 200
    assert items[2]["size"] == 100


@patch("main.table")
@patch("main.s3")
def test_get_photo_success(mock_s3, mock_table):
    mock_table.get_item.return_value = {"Item": MOCK_ITEMS[0]}
    mock_s3.generate_presigned_url.return_value = "https://presigned.url/photo"

    response = client.get("/photos/aaa")

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://presigned.url/photo"
    assert data["metadata"]["id"] == "aaa"


@patch("main.table")
def test_get_photo_not_found(mock_table):
    mock_table.get_item.return_value = {}

    response = client.get("/photos/nonexistent")

    assert response.status_code == 404
