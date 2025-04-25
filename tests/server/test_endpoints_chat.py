"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.
"""
# spell-checker: disable
# pylint: disable=import-error

from typing import Any, Dict
from unittest.mock import patch, MagicMock
import pytest
import requests
from conftest import TEST_HEADERS, TEST_BAD_HEADERS
from langchain_core.messages import ChatMessage
from common.schema import ChatRequest


#############################################################################
# Test AuthN required and Valid
#############################################################################
class TestNoAuthEndpoints:
    """Test endpoints without AuthN"""

    test_cases = [
        pytest.param(
            {"endpoint": "/v1/chat/completions", "method": "post"},
            id="chat_post",
        ),
        pytest.param(
            {"endpoint": "/v1/chat/streams", "method": "post"},
            id="chat_stream",
        ),
        pytest.param(
            {"endpoint": "/v1/chat/history", "method": "get"},
            id="chat_history",
        ),
    ]

    @pytest.mark.parametrize("test_case", test_cases)
    def test_no_auth(self, client: requests.Session, test_case: Dict[str, Any]) -> None:
        """Testing for required AuthN"""
        response = client.request(test_case["method"], test_case["endpoint"])
        assert response.status_code == 403
        response = client.request(test_case["method"], test_case["endpoint"], headers=TEST_BAD_HEADERS)
        assert response.status_code == 401


#############################################################################
# Test Chat Completions
#############################################################################
class TestChatCompletions:
    """Test chat completion endpoints"""

    def test_chat_completion_no_model(self, client: requests.Session):
        """Test no model chat completion request"""
        request = ChatRequest(
            messages=[ChatMessage(content="Hello", role="user")],
            model="test-model",
            temperature=1.0,
            max_completion_tokens=256,
        )

        response = client.post("/v1/chat/completions", headers=TEST_HEADERS, json=request.model_dump())
        assert response.status_code == 200
        assert "choices" in response.json()
        assert (
            response.json()["choices"][0]["message"]["content"]
            == "I'm sorry, I'm unable to initialise the Language Model. Please refresh the application."
        )

    def test_chat_completion_valid_mock(self, client: requests.Session):
        """Test valid chat completion request"""
        # Create the mock response
        mock_response = {
            "id": "test-id",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Test response"},
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "created": 1234567890,
            "model": "test-model",
            "object": "chat.completion",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        # Mock the requests.post call
        with patch.object(client, "post") as mock_post:
            # Configure the mock response
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_post.return_value = mock_response_obj

            request = ChatRequest(
                messages=[ChatMessage(content="Hello", role="user")],
                model="test-model",
                temperature=1.0,
                max_completion_tokens=256,
            )

            response = client.post("/v1/chat/completions", headers=TEST_HEADERS, json=request.model_dump())
            assert response.status_code == 200
            assert "choices" in response.json()
            assert response.json()["choices"][0]["message"]["content"] == "Test response"


#############################################################################
# Test Chat Streaming
#############################################################################
class TestChatStreaming:
    """Test chat streaming endpoints"""

    def test_chat_stream_valid_mock(self, client: requests.Session):
        """Test valid chat stream request"""
        # Create the mock streaming response
        mock_streaming_response = MagicMock()
        mock_streaming_response.status_code = 200
        mock_streaming_response.iter_bytes.return_value = [b"Test streaming", b" response"]

        # Mock the requests.post call
        with patch.object(client, "post") as mock_post:
            mock_post.return_value = mock_streaming_response

            request = ChatRequest(
                messages=[ChatMessage(content="Hello", role="user")],
                model="test-model",
                temperature=1.0,
                max_completion_tokens=256,
                streaming=True,
            )

            response = client.post("/v1/chat/streams", headers=TEST_HEADERS, json=request.model_dump())
            assert response.status_code == 200
            content = b"".join(response.iter_bytes())
            assert b"Test streaming response" in content


#############################################################################
# Test Chat History
#############################################################################
class TestChatHistory:
    """Test chat history endpoints"""

    def test_chat_history_empty(self, client: requests.Session):
        """Test no model chat completion request"""
        response = client.get("/v1/chat/history", headers=TEST_HEADERS)
        assert response.status_code == 200
        history = response.json()
        assert history[0]["role"] == "system"
        assert history[0]["content"] == "I'm sorry, I have no history of this conversation"

    def test_chat_history_valid_mock(self, client: requests.Session):
        """Test valid chat history request"""
        # Create the mock history response
        mock_history = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]

        # Mock the requests.get call
        with patch.object(client, "get") as mock_get:
            # Configure the mock response
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_history
            mock_get.return_value = mock_response_obj

            response = client.get("/v1/chat/history", headers=TEST_HEADERS)
            assert response.status_code == 200
            history = response.json()
            assert len(history) == 2
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "Hello"
