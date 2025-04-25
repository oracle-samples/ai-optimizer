"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.
"""
# spell-checker: disable
# pylint: disable=import-error
# pylint: disable=import-outside-toplevel

import os
import time
import subprocess
import socket
from typing import Generator
from unittest.mock import patch, MagicMock
import shutil
from pathlib import Path
from streamlit.testing.v1 import AppTest
import docker
from docker.errors import DockerException
from docker.models.containers import Container
import requests
import pytest
from fastapi.testclient import TestClient


# This contains all the environment variables we consume on startup (add as required)
# Used to clear testing environment
API_VARS = [
    "API_SERVER_KEY",
    "API_SERVER_URL",
    "API_SERVER_PORT",
]
DB_VARS = [
    "DB_USERNAME",
    "DB_PASSWORD",
    "DB_DSN",
    "DB_WALLET_PASSWORD",
    "TNS_ADMIN",
]
MODEL_VARS = [
    "ON_PREM_OLLAMA_URL",
    "ON_PREM_HF_URL",
    "OPENAI_API_KEY",
    "PPLX_API_KEY",
    "COHERE_API_KEY",
]
OCI_VARS = [
    "OCI_CLI_CONFIG_FILE",
    "OCI_CLI_TENANCY",
    "OCI_CLI_REGION",
    "OCI_CLI_USER",
    "OCI_CLI_FINGERPRINT",
    "OCI_CLI_KEY_FILE",
    "OCI_CLI_SECURITY_TOKEN_FILE",
    "OCI_GENAI_SERVICE_ENDPOINT",
    "OCI_GENAI_COMPARTMENT_ID",
]
for env_var in [*DB_VARS, *MODEL_VARS, *OCI_VARS]:
    os.environ.pop(env_var, None)

# Setup API Server Defaults
os.environ["API_SERVER_KEY"] = "testing-token"
os.environ["API_SERVER_URL"] = "http://localhost"
os.environ["API_SERVER_PORT"] = "8012"

# Test constants
TEST_CONFIG = {
    # Database configuration
    "db_username": "PYTEST",
    "db_password": "OrA_41_3xPl0d3r",
    "db_name": "FREEPDB1",
    "db_port": "1525",
    "db_dsn": "//localhost:1525/FREEPDB1",
    # Test client configuration
    "test_client": "test_client",
}
TEST_HEADERS = {"Authorization": f"Bearer {os.getenv('API_SERVER_KEY')}", "client": TEST_CONFIG["test_client"]}
TEST_BAD_HEADERS = {"Authorization": "Bearer bad-testing-token", "client": TEST_CONFIG["test_client"]}

# Constants for helper processes/container
TIMEOUT = 300  # 5 minutes timeout
CHECK_DELAY = 10  # 10 seconds between checks


#####################################################
# Helpers
#####################################################
def wait_for_container_ready(container, ready_output, since=None):
    """Helper function to wait for container to be ready"""
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        try:
            # Get logs, optionally only those since a specific timestamp
            logs = container.logs(tail=100, since=since).decode("utf-8")
            if ready_output in logs:
                return
        except DockerException as e:
            container.remove(force=True)
            raise DockerException(f"Failed to get container logs: {str(e)}") from e
        time.sleep(CHECK_DELAY)

    if container:
        container.remove(force=True)
    raise TimeoutError(f"Container did not become ready within {TIMEOUT} seconds")


#####################################################
# Mocks
#####################################################
@pytest.fixture(name="mock_get_namespace")
def _mock_get_namespace():
    """Mock server_oci.get_namespace"""
    with patch("server.utils.oci.get_namespace", return_value="test_namespace") as mock:
        yield mock


@pytest.fixture(name="mock_init_client")
def _mock_init_client():
    """Mock init_client to return a fake OCI client"""
    mock_client = MagicMock()
    mock_client.get_namespace.return_value.data = "test_namespace"
    mock_client.get_object.return_value.data.raw.stream.return_value = [b"fake-data"]

    with patch("server.utils.oci.init_client", return_value=mock_client):
        yield mock_client


#####################################################
# Fixtures
#####################################################
def get_base_url() -> str:
    """Get the base URL for the server"""
    base_url = f"{os.environ['API_SERVER_URL']}:{os.environ['API_SERVER_PORT']}"
    if not base_url.startswith(("http://", "https://")):
        base_url = f"http://{base_url}"
    return base_url


@pytest.fixture(scope="session", name="client")
def _client() -> Generator[requests.Session, None, None]:
    """Create test client that connects to the running FastAPI server"""
    # Prevent picking up default OCI config file
    os.environ["OCI_CLI_CONFIG_FILE"] = "/non/existant/path"

    # Wait for server to be ready
    wait_for_server()

    # Create a session for making requests
    session = requests.Session()

    # Store the original request method
    original_request = session.request

    # Add a simple method to make requests with the base URL
    def make_request(method, url, **kwargs):
        if not url.startswith(("http://", "https://")):
            url = f"{get_base_url()}{url}"
        return original_request(method, url, **kwargs)

    # Add the method to the session
    session.request = make_request

    yield session


@pytest.fixture(scope="session")
def db_container() -> Generator[Container, None, None]:
    """
    This fixture creates and manages an Oracle database container for testing.
    The container is created at the start of the test session and removed after all tests complete.
    """
    db_client = docker.from_env()
    container = None
    temp_dir = Path("tests/db_startup_temp")

    try:
        # Create a temporary directory for our generated SQL files
        temp_dir.mkdir(exist_ok=True)

        # Generate the SQL file with values from TEST_CONFIG
        sql_content = f"""
        alter system set vector_memory_size=512M scope=spfile;

        alter session set container=FREEPDB1;
        CREATE TABLESPACE IF NOT EXISTS USERS DATAFILE '/opt/oracle/oradata/FREE/FREEPDB1/users_01.dbf' SIZE 100M;
        CREATE USER IF NOT EXISTS "{TEST_CONFIG["db_username"]}" IDENTIFIED BY {TEST_CONFIG["db_password"]}
            DEFAULT TABLESPACE "USERS"
            TEMPORARY TABLESPACE "TEMP";
        GRANT "DB_DEVELOPER_ROLE" TO "{TEST_CONFIG["db_username"]}";
        ALTER USER "{TEST_CONFIG["db_username"]}" DEFAULT ROLE ALL;
        ALTER USER "{TEST_CONFIG["db_username"]}" QUOTA UNLIMITED ON USERS;

        EXIT;
        """

        # Write the SQL file
        temp_sql_file = temp_dir / "01_db_user.sql"
        with open(temp_sql_file, "w", encoding="UTF-8") as f:
            f.write(sql_content)

        # Start the container with volume mount
        container = db_client.containers.run(
            "container-registry.oracle.com/database/free:latest-lite",
            environment={
                "ORACLE_PWD": TEST_CONFIG["db_password"],
                "ORACLE_PDB": TEST_CONFIG["db_name"],
            },
            ports={"1521/tcp": int(TEST_CONFIG["db_port"])},
            volumes={str(temp_dir.absolute()): {"bind": "/opt/oracle/scripts/startup", "mode": "ro"}},
            detach=True,
        )

        # Wait for database to be ready
        wait_for_container_ready(container, "DATABASE IS READY TO USE!")

        # Restart the container to apply the vector_memory_size
        container.restart()
        restart_time = int(time.time())

        # Wait for database to be ready again after restart
        wait_for_container_ready(container, "DATABASE IS READY TO USE!", since=restart_time)

        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"Removed temporary directory: {temp_dir}")
        yield container

    except DockerException as e:
        if container:
            container.remove(force=True)
        raise DockerException(f"Docker operation failed: {str(e)}") from e

    finally:
        # Cleanup: After session
        if container:
            try:
                container.stop(timeout=30)  # Give 30 seconds for graceful shutdown
                container.remove()
            except DockerException as e:
                # Log error but don't fail tests if cleanup has issues
                print(f"Warning: Failed to cleanup database container: {str(e)}")


@pytest.fixture(scope="session")
def embedding_container() -> Generator[Container, None, None]:
    """
    This fixture creates and manages an Ollama container for embedding model testing.
    The container is created at the start of the test session and removed after all tests complete.
    """
    docker_client = docker.from_env()
    container = None

    try:
        # Start the Ollama container
        container = docker_client.containers.run(
            "ollama/ollama:latest",
            ports={"11434/tcp": 11434},
            detach=True,
        )

        # Wait for Ollama to be ready
        start_time = time.time()
        while time.time() - start_time < TIMEOUT:
            try:
                # Try to connect to Ollama API
                response = requests.get("http://localhost:11434/api/version", timeout=120)
                if response.status_code == 200:
                    # Pull the embedding model
                    subprocess.run(["ollama", "pull", "nomic-embed-text"], check=True)
                    break
            except (requests.exceptions.ConnectionError, subprocess.CalledProcessError):
                time.sleep(CHECK_DELAY)
        else:
            if container:
                container.remove(force=True)
            raise TimeoutError(f"Embedding model did not become ready within {TIMEOUT} seconds")

        yield container

    except DockerException as e:
        if container:
            container.remove(force=True)
        raise DockerException(f"Docker operation failed: {str(e)}") from e

    finally:
        # Cleanup: After session
        if container:
            try:
                container.stop(timeout=30)  # Give 30 seconds for graceful shutdown
                container.remove()
            except DockerException as e:
                # Log error but don't fail tests if cleanup has issues
                print(f"Warning: Failed to cleanup embedding container: {str(e)}")


@pytest.fixture
def mock_embedding_model():
    """
    This fixture provides a mock embedding model for testing.
    It returns a function that simulates embedding generation by returning random vectors.
    """

    def mock_embed_documents(texts: list[str]) -> list[list[float]]:
        """Mock function that returns random embeddings for testing"""
        import numpy as np

        return [np.random.rand(384).tolist() for _ in texts]  # 384 is a common embedding dimension

    return mock_embed_documents


def wait_for_server():
    """Wait until the server to be accessible"""
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        try:
            # Try to establish a socket connection to the host and port
            with socket.create_connection(("127.0.0.1", os.environ.get("API_SERVER_PORT")), timeout=CHECK_DELAY):
                return True  # Port is accessible
        except (socket.timeout, socket.error):
            print("Server not accessible. Retrying...")
            time.sleep(CHECK_DELAY)  # Wait before retrying

    raise TimeoutError("Server is not accessible within the timeout period.")


@pytest.fixture
def app_test():
    """Establish Streamlit State for Client to Operate"""

    def _app_test(page):
        at = AppTest.from_file(page)
        at.session_state.server = {
            "key": os.environ.get("API_SERVER_KEY"),
            "url": os.environ.get("API_SERVER_URL"),
            "port": os.environ.get("API_SERVER_PORT"),
        }
        wait_for_server()
        response = requests.get(
            url=f"{at.session_state.server['url']}:{at.session_state.server['port']}/v1/settings",
            headers=TEST_HEADERS,
            params={"client": TEST_CONFIG["test_client"]},
            timeout=120,
        )
        if response.status_code == 404:
            response = requests.post(
                url=f"{at.session_state.server['url']}:{at.session_state.server['port']}/v1/settings",
                headers=TEST_HEADERS,
                params={"client": TEST_CONFIG["test_client"]},
                timeout=120,
            )
        at.session_state.user_settings = response.json()

        return at

    return _app_test


@pytest.fixture(scope="session", autouse=True)
def start_fastapi_server():
    """Start the FastAPI server for Streamlit"""

    # Prevent picking up default OCI config file
    os.environ["OCI_CLI_CONFIG_FILE"] = "/non/existant/path"

    server_process = subprocess.Popen(["python", "launch_server.py"], cwd="src")
    wait_for_server()

    # Bootstrap Settings
    response = requests.post(
        f"{get_base_url()}/v1/settings", headers=TEST_HEADERS, params={"client": TEST_CONFIG["test_client"]}
    )
    assert response.status_code == 200, "Failed to bootstrap settings"

    yield

    # Terminate the server after tests
    server_process.terminate()
    server_process.wait()
