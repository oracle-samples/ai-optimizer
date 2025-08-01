"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.

Session States Set:
- user_client: Stores the Client
"""

# spell-checker:ignore streamlit, oraclevs, selectai
import asyncio
import inspect
import json
import base64

import streamlit as st
from streamlit import session_state as state

from client.content.config.models import get_models

import client.utils.st_common as st_common
import client.utils.api_call as api_call

from client.utils.st_footer import render_chat_footer
import client.utils.client as client
import common.logging_config as logging_config

logger = logging_config.logging.getLogger("client.content.chatbot")


#############################################################################
# Functions
#############################################################################
def show_vector_search_refs(context):
    """When Vector Search Content Found, show the references"""
    st.markdown("**References:**")
    ref_src = set()
    ref_cols = st.columns([3, 3, 3])
    # Create a button in each column
    for i, (ref_col, chunk) in enumerate(zip(ref_cols, context[0])):
        with ref_col.popover(f"Reference: {i + 1}"):
            chunk = context[0][i]
            logger.debug("Chunk Content: %s", chunk)
            st.subheader("Reference Text", divider="red")
            st.markdown(chunk["page_content"])
            try:
                ref_src.add(chunk["metadata"]["filename"])
                st.subheader("Metadata", divider="red")
                st.markdown(f"File:  {chunk['metadata']['source']}")
                st.markdown(f"Chunk: {chunk['metadata']['page']}")
            except KeyError:
                logger.error("Chunk Metadata NOT FOUND!!")

    for link in ref_src:
        st.markdown("- " + link)
    st.markdown(f"**Notes:** Vector Search Query - {context[1]}")


#############################################################################
# MAIN
#############################################################################
async def main() -> None:
    """Streamlit GUI"""
    try:
        get_models()
    except api_call.ApiError:
        st.stop()
    #########################################################################
    # Sidebar Settings
    #########################################################################
    # Get a list of available language models, if none, then stop
    ll_models_enabled = st_common.enabled_models_lookup("ll")
    if not ll_models_enabled:
        st.error("No language models are configured and/or enabled. Disabling Client.", icon="🛑")
        st.stop()
    # the sidebars will set this to False if not everything is configured.
    state.enable_client = True
    st_common.tools_sidebar()
    st_common.history_sidebar()
    st_common.ll_sidebar()
    st_common.selectai_sidebar()
    st_common.vector_search_sidebar()
    # Stop when sidebar configurations not set
    if not state.enable_client:
        st.stop()

    #########################################################################
    # Chatty-Bot Centre
    #########################################################################
    # Establish the Client
    if "user_client" not in state:
        state.user_client = client.Client(
            server=state.server,
            settings=state.client_settings,
            timeout=1200,
        )
    user_client: client.Client = state.user_client

    history = await user_client.get_history()
    st.chat_message("ai").write("Hello, how can I help you?")
    vector_search_refs = []
    for message in history or []:
        if not message["content"]:
            continue
        if message["role"] == "tool" and message["name"] == "oraclevs_tool":
            vector_search_refs = json.loads(message["content"])
        if message["role"] in ("ai", "assistant"):
            with st.chat_message("ai"):
                st.markdown(message["content"])
                if vector_search_refs:
                    show_vector_search_refs(vector_search_refs)
                    vector_search_refs = []
        elif message["role"] in ("human", "user"):
            with st.chat_message("human"):
                content = message["content"]
                if isinstance(content, list):
                    for part in content:
                        if part["type"] == "text":
                            st.write(part["text"])
                        elif part["type"] == "image_url" and part["image_url"]["url"].startswith("data:image"):
                            st.image(part["image_url"]["url"])
                else:
                    st.write(content)

    sys_prompt = state.client_settings["prompts"]["sys"]
    render_chat_footer()
    if human_request := st.chat_input(
        f"Ask your question here... (current prompt: {sys_prompt})",
        accept_file=True,
        file_type=["jpg", "jpeg", "png"],
    ):
        st.chat_message("human").write(human_request.text)
        file_b64 = None
        if human_request["files"]:
            file = human_request["files"][0]
            file_bytes = file.read()
            file_b64 = base64.b64encode(file_bytes).decode("utf-8")
        try:
            message_placeholder = st.chat_message("ai").empty()
            full_answer = ""
            async for chunk in user_client.stream(message=human_request.text, image_b64=file_b64):
                full_answer += chunk
                message_placeholder.markdown(full_answer)
            # Stream until we hit the end then refresh to replace with history
            st.rerun()
        except Exception:
            logger.error("Exception:", exc_info=1)
            st.chat_message("ai").write(
                """
                I'm sorry, something's gone wrong.  Please try again.
                If the problem persists, please raise an issue.
                """
            )
            if st.button("Retry", key="reload_chatbot"):
                st_common.clear_state_key("user_client")
                st.rerun()


if __name__ == "__main__" or "page.py" in inspect.stack()[1].filename:
    try:
        asyncio.run(main())
    except ValueError as ex:
        logger.exception("Bug detected: %s", ex)
        st.error("It looks like you found a bug; please open an issue", icon="🛑")
        st.stop()
    except IndexError as ex:
        logger.exception("Unable to contact the server: %s", ex)
        st.error("Unable to contact the server, is it running?", icon="🚨")
        if st.button("Retry", key="reload_chatbot"):
            st_common.clear_state_key("user_client")
            st.rerun()
