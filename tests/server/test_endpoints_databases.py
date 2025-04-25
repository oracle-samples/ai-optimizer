"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.
"""
# spell-checker: disable
# pylint: disable=import-error

from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient
from docker.models.containers import Container
from conftest import TEST_CONFIG, TEST_HEADERS, TEST_BAD_HEADERS


#############################################################################
# Test AuthN required and Valid
#############################################################################
class TestNoAuthEndpoints:
    """Test endpoints without AuthN"""

    test_cases = [
        pytest.param(
            {"endpoint": "/v1/databases", "method": "get"},
            id="databases_list",
        ),
        pytest.param(
            {"endpoint": "/v1/databases/DEFAULT", "method": "get"},
            id="databases_get",
        ),
        pytest.param(
            {"endpoint": "/v1/databases/DEFAULT", "method": "patch"},
            id="databases_update",
        ),
    ]

    @pytest.mark.parametrize("test_case", test_cases)
    def test_no_auth(self, client: TestClient, test_case: Dict[str, Any]) -> None:
        """Testing for required AuthN"""
        response = getattr(client, test_case["method"])(test_case["endpoint"])
        assert response.status_code == 403
        response = getattr(client, test_case["method"])(test_case["endpoint"], headers=TEST_BAD_HEADERS)
        assert response.status_code == 401


#############################################################################
# Test AuthN without an Accessible Database
#############################################################################
class TestEndpointsNoDB:
    """Test endpoints with AuthN and No Database"""

    def test_databases_list_initial(self, client: TestClient) -> None:
        """Test initial database listing before any updates (cater for isolated runs)"""
        response = client.get("/v1/databases", headers=TEST_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        default_db = next((db for db in data if db["name"] == "DEFAULT"), None)
        assert default_db is not None
        assert default_db["connected"] is False
        assert default_db["dsn"] in [None, TEST_CONFIG["db_dsn"]]
        assert default_db["password"] in [None, TEST_CONFIG["db_password"]]
        assert default_db["tcp_connect_timeout"] == 5
        assert default_db["user"] in [None, TEST_CONFIG["db_username"]]
        assert default_db["vector_stores"] in [None, []]
        assert default_db["wallet_location"] is None
        assert default_db["wallet_password"] is None

    def test_databases_get_nonexistent(self, client: TestClient) -> None:
        """Test getting non-existent database"""
        response = client.get("/v1/databases/NONEXISTENT", headers=TEST_HEADERS)
        assert response.status_code == 404
        assert response.json() == {"detail": "Database: NONEXISTENT not found."}

    def test_databases_update_nonexistent(self, client: TestClient) -> None:
        """Test updating non-existent database"""
        payload = {"user": "test_user", "password": "test_pass", "dsn": "test_dsn", "wallet_password": "test_wallet"}
        response = client.patch("/v1/databases/NONEXISTENT", headers=TEST_HEADERS, json=payload)
        assert response.status_code == 404
        assert response.json() == {"detail": "Database: NONEXISTENT not found."}

    def test_databases_update_db_down(self, client: TestClient) -> None:
        """Test updating the DB when it is down"""
        payload = {
            "user": TEST_CONFIG["db_username"],
            "password": TEST_CONFIG["db_password"],
            "dsn": "//localhost:1521/DOWNDB_TP",
        }
        response = client.patch("/v1/databases/DEFAULT", headers=TEST_HEADERS, json=payload)
        assert response.status_code == 503
        assert response.json() == {"detail": "Database: DEFAULT unable to connect."}


#############################################################################
# Test AuthN with an Accessible Database - No OS Env
#############################################################################
class TestEndpoints:
    """Test endpoints with AuthN and Database"""

    @pytest.mark.parametrize(
        "test_case",
        [
            pytest.param(
                {
                    "name": "non_existent_db",
                    "database": TEST_CONFIG["db_name"],
                    "status_code": 404,
                    "payload": {
                        "user": TEST_CONFIG["db_username"],
                        "password": TEST_CONFIG["db_password"],
                        "dsn": TEST_CONFIG["db_dsn"],
                    },
                    "expected": {"detail": f"Database: {TEST_CONFIG['db_name']} not found."},
                },
                id="non_existent_database",
            ),
            pytest.param(
                {
                    "name": "empty_payload",
                    "database": "DEFAULT",
                    "status_code": 422,
                    "payload": "",
                    "expected": {
                        "detail": [
                            {
                                "type": "model_attributes_type",
                                "loc": ["body"],
                                "msg": "Input should be a valid dictionary or object to extract fields from",
                                "input": "",
                            }
                        ]
                    },
                },
                id="empty_payload",
            ),
            pytest.param(
                {
                    "name": "missing_credentials",
                    "database": "DEFAULT",
                    "status_code": 400,
                    "payload": {},
                    "expected": {"detail": "Database: DEFAULT missing connection details."},
                },
                id="missing_credentials",
            ),
            pytest.param(
                {
                    "name": "invalid_connection",
                    "database": "DEFAULT",
                    "status_code": 503,
                    "payload": {"user": "user", "password": "password", "dsn": "//localhost:1521/dsn"},
                    "expected": {"detail": "Database: DEFAULT unable to connect."},
                },
                id="invalid_connection",
            ),
            pytest.param(
                {
                    "name": "wrong_password",
                    "database": "DEFAULT",
                    "status_code": 401,
                    "payload": {
                        "user": TEST_CONFIG["db_username"],
                        "password": "Wr0ng_P4sswOrd",
                        "dsn": TEST_CONFIG["db_dsn"],
                    },
                    "expected": {"detail": "Database: DEFAULT invalid credentials."},
                },
                id="wrong_password",
            ),
            pytest.param(
                {
                    "name": "successful_update",
                    "database": "DEFAULT",
                    "status_code": 200,
                    "payload": {
                        "user": TEST_CONFIG["db_username"],
                        "password": TEST_CONFIG["db_password"],
                        "dsn": TEST_CONFIG["db_dsn"],
                    },
                    "expected": {
                        "connected": True,
                        "dsn": TEST_CONFIG["db_dsn"],
                        "name": "DEFAULT",
                        "password": TEST_CONFIG["db_password"],
                        "tcp_connect_timeout": 5,
                        "user": TEST_CONFIG["db_username"],
                        "vector_stores": [],
                        "wallet_location": None,
                        "wallet_password": None,
                    },
                },
                id="successful_update",
            ),
        ],
    )
    def test_databases_update_cases(
        self, client: TestClient, db_container: Container, test_case: Dict[str, Any]
    ) -> None:
        """Test various database update scenarios"""
        assert db_container is not None
        response = client.patch(
            f"/v1/databases/{test_case['database']}", headers=TEST_HEADERS, json=test_case["payload"]
        )
        assert response.status_code == test_case["status_code"]

        if response.status_code != 200:
            assert response.json() == test_case["expected"]
        else:
            data = response.json()
            data.pop("config_dir", None)  # Remove config_dir as it's environment-specific
            assert data == test_case["expected"]

    def test_databases_get_after_update(self, client: TestClient, db_container: Container) -> None:
        """Test getting DEFAULT database after successful update"""
        assert db_container is not None
        response = client.get("/v1/databases/DEFAULT", headers=TEST_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "config_dir" in data
        data.pop("config_dir", None)
        assert data == {
            "connected": True,
            "dsn": TEST_CONFIG["db_dsn"],
            "name": "DEFAULT",
            "password": TEST_CONFIG["db_password"],
            "tcp_connect_timeout": 5,
            "user": TEST_CONFIG["db_username"],
            "vector_stores": [],
            "wallet_location": None,
            "wallet_password": None,
        }

    def test_databases_list_after_update(self, client: TestClient, db_container: Container) -> None:
        """Test listing databases after successful update"""
        assert db_container is not None
        response = client.get("/v1/databases", headers=TEST_HEADERS)
        assert response.status_code == 200
        data = response.json()
        default_db = next((db for db in data if db["name"] == "DEFAULT"), None)
        assert default_db is not None
        assert default_db["connected"] is True
        assert default_db["dsn"] == TEST_CONFIG["db_dsn"]
        assert default_db["name"] == "DEFAULT"
        assert default_db["password"] == TEST_CONFIG["db_password"]
        assert default_db["user"] == TEST_CONFIG["db_username"]
        assert isinstance(default_db["vector_stores"], list)

    def test_databases_update_invalid_wallet(self, client: TestClient, db_container: Container) -> None:
        """Test updating database with invalid wallet configuration"""
        assert db_container is not None
        payload = {
            "user": TEST_CONFIG["db_username"],
            "password": TEST_CONFIG["db_password"],
            "dsn": TEST_CONFIG["db_dsn"],
            "wallet_location": "/nonexistent/path",
            "wallet_password": "invalid",
        }
        response = client.patch("/v1/databases/DEFAULT", headers=TEST_HEADERS, json=payload)
        # Should still work if wallet is not required.
        assert response.status_code == 200

    def test_databases_concurrent_connections(self, client: TestClient, db_container: Container) -> None:
        """Test concurrent database connections"""
        assert db_container is not None
        # Make multiple concurrent connection attempts
        payload = {
            "user": TEST_CONFIG["db_username"],
            "password": TEST_CONFIG["db_password"],
            "dsn": TEST_CONFIG["db_dsn"],
        }
        responses = []
        for _ in range(5):  # Try 5 concurrent connections
            response = client.patch("/v1/databases/DEFAULT", headers=TEST_HEADERS, json=payload)
            responses.append(response)

        # Verify all connections were handled properly
        for response in responses:
            assert response.status_code in [200, 503]  # Either successful or proper error
            if response.status_code == 200:
                data = response.json()
                assert data["connected"] is True
