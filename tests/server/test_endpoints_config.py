"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.
"""
# spell-checker: disable

import pytest
import unittest.mock as mock
from common.schema import Settings, LargeLanguageSettings, PromptSettings, RagSettings, OciSettings
from server.bootstrap.settings_def import SETTINGS_PATH

@pytest.fixture
def valid_server_config() -> str:
    return """{
  "user_settings": {
    "client": "server",
    "ll_model": {
      "context_length": null,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 256,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "model": null,
      "chat_history": true
    },
    "prompts": {
      "ctx": "Basic Example",
      "sys": "Basic Example"
    },
    "rag": {
      "database": "DEFAULT",
      "vector_store": null,
      "alias": null,
      "model": null,
      "chunk_size": null,
      "chunk_overlap": null,
      "distance_metric": null,
      "index_type": null,
      "rag_enabled": false,
      "grading": true,
      "search_type": "Similarity",
      "top_k": 4,
      "score_threshold": 0.0,
      "fetch_k": 20,
      "lambda_mult": 0.5
    },
    "oci": {
      "auth_profile": "DEFAULT"
    }
  },
  "database_config": [
    {
      "user": null,
      "password": null,
      "dsn": null,
      "wallet_password": null,
      "wallet_location": null,
      "config_dir": "/Users/jorge/Developer/Python/ai-optimizer/src/tns_admin",
      "tcp_connect_timeout": 5
    }
  ],
  "oci_config": [
    {
      "auth_profile": "DEFAULT",
      "namespace": null,
      "user": null,
      "security_token_file": null,
      "authentication": "api_key",
      "tenancy": null,
      "region": null,
      "fingerprint": null,
      "key_file": null,
      "compartment_id": "",
      "service_endpoint": "",
      "log_requests": false,
      "additional_user_agent": "",
      "pass_phrase": null
    }
  ],
  "prompts_config": [
    {
      "prompt": "You are a friendly, helpful assistant.",
      "name": "Basic Example",
      "category": "sys"
    },
    {
      "prompt": "You are an assistant for question-answering tasks, be concise.  Use the retrieved DOCUMENTS to answer the user input as accurately as possible. Keep your answer grounded in the facts of the DOCUMENTS and reference the DOCUMENTS where possible. If there ARE DOCUMENTS, you should be able to answer.  If there are NO DOCUMENTS, respond only with \'I am sorry, but cannot find relevant sources.\'",
      "name": "RAG Example",
      "category": "sys"
    },
    {
      "prompt": "You are an assistant for question-answering tasks.  Use the retrieved DOCUMENTS and history to answer the question.  If there are no DOCUMENTS or the DOCUMENTS do not contain the specific information, do your best to still answer.",
      "name": "Custom",
      "category": "sys"
    },
    {
      "prompt": "Rephrase the latest user input into a standalone search query optimized for vector retrieval. Use only the user\'s prior inputs for context, ignoring system responses. Remove conversational elements like confirmations or clarifications, focusing solely on the core topic and keywords.",
      "name": "Basic Example",
      "category": "ctx"
    },
    {
      "prompt": "Ignore chat history and context and do not reformulate the question. DO NOT answer the question. Simply return the original query AS-IS.",
      "name": "Custom",
      "category": "ctx"
    }
  ],
  "ll_model_config": [
    {
      "max_chunk_size": null,
      "context_length": 127072,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 4096,
      "presence_penalty": 0.0,
      "temperature": 0.3,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "https://api.cohere.ai",
      "api_key": "",
      "name": "command-r",
      "type": "ll",
      "api": "Cohere",
      "openai_compat": false,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": null,
      "context_length": 127072,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 4096,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "https://api.openai.com",
      "api_key": "",
      "name": "gpt-4o-mini",
      "type": "ll",
      "api": "OpenAI",
      "openai_compat": true,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": null,
      "context_length": 127072,
      "frequency_penalty": 1.0,
      "max_completion_tokens": 28000,
      "presence_penalty": 0.0,
      "temperature": 0.2,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "https://api.perplexity.ai",
      "api_key": "",
      "name": "sonar",
      "type": "ll",
      "api": "Perplexity",
      "openai_compat": true,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": null,
      "context_length": 131072,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 4096,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "http://localhost:1234/v1",
      "api_key": "",
      "name": "phi-4",
      "type": "ll",
      "api": "CompatOpenAI",
      "openai_compat": true,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": null,
      "context_length": 131072,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 4000,
      "presence_penalty": 0.0,
      "temperature": 0.3,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": null,
      "api_key": "",
      "name": "cohere.command-r-plus-08-2024",
      "type": "ll",
      "api": "ChatOCIGenAI",
      "openai_compat": false,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": null,
      "context_length": 131072,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 2048,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "http://127.0.0.1:11434",
      "api_key": "",
      "name": "llama3.1",
      "type": "ll",
      "api": "ChatOllama",
      "openai_compat": true,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": 512,
      "context_length": null,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 256,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "http://127.0.0.1:8080",
      "api_key": "",
      "name": "thenlper/gte-base",
      "type": "embed",
      "api": "HuggingFaceEndpointEmbeddings",
      "openai_compat": true,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": 8191,
      "context_length": null,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 256,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "https://api.openai.com",
      "api_key": "",
      "name": "text-embedding-3-small",
      "type": "embed",
      "api": "OpenAIEmbeddings",
      "openai_compat": true,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": 512,
      "context_length": null,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 256,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "https://api.cohere.ai",
      "api_key": "",
      "name": "embed-english-light-v3.0",
      "type": "embed",
      "api": "CohereEmbeddings",
      "openai_compat": false,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": 4096,
      "context_length": null,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 256,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": null,
      "api_key": "",
      "name": "cohere.embed-multilingual-v3.0",
      "type": "embed",
      "api": "OCIGenAIEmbeddings",
      "openai_compat": false,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": 8192,
      "context_length": null,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 256,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "http://localhost:1234/v1",
      "api_key": "",
      "name": "text-embedding-nomic-embed-text-v1.5",
      "type": "embed",
      "api": "CompatOpenAIEmbeddings",
      "openai_compat": true,
      "status": "UNVERIFIED"
    },
    {
      "max_chunk_size": 512,
      "context_length": null,
      "frequency_penalty": 0.0,
      "max_completion_tokens": 256,
      "presence_penalty": 0.0,
      "temperature": 1.0,
      "top_p": 1.0,
      "streaming": false,
      "enabled": false,
      "url": "http://127.0.0.1:11434",
      "api_key": "",
      "name": "mxbai-embed-large",
      "type": "embed",
      "api": "OllamaEmbeddings",
      "openai_compat": true,
      "status": "UNVERIFIED"
    }
  ]
}"""

#############################################################################
# Test AuthN required and Valid
#############################################################################
class TestInvalidAuthEndpoints:
    """Test endpoints without Headers and Invalid AuthN"""

    @pytest.mark.parametrize(
        "auth_type, status_code",
        [
            pytest.param("no_auth", 403, id="no_auth"),
            pytest.param("invalid_auth", 401, id="invalid_auth"),
        ],
    )
    def test_endpoints(self, client, auth_headers, auth_type, status_code):
        """Test endpoints require valide authentication."""
        response = client.post("/v1/config", headers=auth_headers[auth_type])
        assert response.status_code == status_code


#############################################################################
# Endpoints Test
#############################################################################
class TestEndpoints:
    """Test Endpoints"""

    def test_config_create(self, client, auth_headers, valid_server_config):
        """Test saving full server configuration"""
        path = SETTINGS_PATH
        mocked_open = mock.mock_open()
        with mock.patch("builtins.open", mocked_open, create=True) as mock_open:
            response = client.post("/v1/config", headers=auth_headers["valid_auth"])
            assert response.status_code == 200

        mocked_open.assert_called_with(path, "w", encoding="UTF-8")
        # mocked_open.return_value.write.assert_called_once()
        mocked_open.return_value.write.assert_called_once_with(valid_server_config)

