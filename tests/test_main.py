from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from main import app


def _make_client_error(code="AccessDenied"):
    return ClientError(
        {"Error": {"Code": code, "Message": "test error"}},
        "TestOperation",
    )

client = TestClient(app)

MOCK_ITEMS = [
    {
        "photos-dev-partition": "aaa",
        "key": "aaa/photo_a.jpg",
        "filename": "photo_a.jpg",
        "size": 300,
        "content_type": "image/jpeg",
        "uploaded_at": "2024-01-03T00:00:00+00:00",
    },
    {
        "photos-dev-partition": "bbb",
        "key": "bbb/photo_b.jpg",
        "filename": "photo_b.jpg",
        "size": 100,
        "content_type": "image/jpeg",
        "uploaded_at": "2024-01-01T00:00:00+00:00",
    },
    {
        "photos-dev-partition": "ccc",
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
    assert items[0]["photos-dev-partition"] == "aaa"
    assert items[1]["photos-dev-partition"] == "ccc"
    assert items[2]["photos-dev-partition"] == "bbb"


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
    mock_table.query.return_value = {"Items": [MOCK_ITEMS[0]]}
    mock_s3.generate_presigned_url.return_value = "https://presigned.url/photo"

    response = client.get("/photos/aaa")

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://presigned.url/photo"
    assert data["metadata"]["photos-dev-partition"] == "aaa"


@patch("main.table")
def test_get_photo_not_found(mock_table):
    mock_table.query.return_value = {"Items": []}

    response = client.get("/photos/nonexistent")

    assert response.status_code == 404


# --- Access Denied tests ---


@patch("main.table")
@patch("main.s3")
def test_upload_s3_access_denied(mock_s3, mock_table):
    mock_s3.put_object.side_effect = _make_client_error("AccessDenied")

    response = client.post(
        "/upload",
        files={"file": ("test.jpg", BytesIO(b"fake image data"), "image/jpeg")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied to AWS resource"


@patch("main.table")
@patch("main.s3")
def test_upload_dynamodb_access_denied(mock_s3, mock_table):
    mock_s3.put_object.return_value = {}
    mock_table.put_item.side_effect = _make_client_error("AccessDeniedException")

    response = client.post(
        "/upload",
        files={"file": ("test.jpg", BytesIO(b"fake image data"), "image/jpeg")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied to AWS resource"


@patch("main.table")
def test_list_photos_access_denied(mock_table):
    mock_table.scan.side_effect = _make_client_error("AccessDenied")

    response = client.get("/photos")

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied to AWS resource"


@patch("main.table")
def test_get_photo_dynamodb_access_denied(mock_table):
    mock_table.query.side_effect = _make_client_error("AccessDeniedException")

    response = client.get("/photos/aaa")

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied to AWS resource"


@patch("main.table")
@patch("main.s3")
def test_get_photo_s3_access_denied(mock_s3, mock_table):
    mock_table.query.return_value = {"Items": [MOCK_ITEMS[0]]}
    mock_s3.generate_presigned_url.side_effect = _make_client_error("AccessDenied")

    response = client.get("/photos/aaa")

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied to AWS resource"


# --- Generic ClientError (500) tests ---


@patch("main.table")
@patch("main.s3")
def test_upload_s3_generic_error(mock_s3, mock_table):
    mock_s3.put_object.side_effect = _make_client_error("InternalError")

    response = client.post(
        "/upload",
        files={"file": ("test.jpg", BytesIO(b"fake image data"), "image/jpeg")},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "An internal error occurred"


@patch("main.table")
def test_list_photos_generic_error(mock_table):
    mock_table.scan.side_effect = _make_client_error("InternalError")

    response = client.get("/photos")

    assert response.status_code == 500
    assert response.json()["detail"] == "An internal error occurred"


@patch("main.table")
def test_get_photo_generic_error(mock_table):
    mock_table.query.side_effect = _make_client_error("InternalError")

    response = client.get("/photos/aaa")

    assert response.status_code == 500
    assert response.json()["detail"] == "An internal error occurred"
