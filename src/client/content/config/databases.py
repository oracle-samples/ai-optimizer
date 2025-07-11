"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.

This script initializes a web interface for database configuration using Streamlit (`st`).
It includes a form to input and test database connection settings.
"""
# spell-checker:ignore streamlit, selectbox, selectai

import inspect
import time
import json
import pandas as pd

import streamlit as st
from streamlit import session_state as state

import client.utils.api_call as api_call
import client.utils.st_common as st_common
import common.logging_config as logging_config
from common.schema import SelectAIProfileType
from client.utils.st_footer import remove_footer

logger = logging_config.logging.getLogger("client.content.config.database")


#####################################################
# Functions
#####################################################
def get_databases(force: bool = False) -> None:
    """Get a dictionary of all Databases and Store Vector Store Tables"""
    if "database_config" not in state or state.database_config == {} or force:
        try:
            response = api_call.get(endpoint="v1/databases")
            state.database_config = {
                item["name"]: {k: v for k, v in item.items() if k != "name"} for item in response
            }
            logger.info("State created: state['database_config']")
        except api_call.ApiError as ex:
            logger.error("Unable to retrieve databases: %s", ex)
            state.database_config = {}


def patch_database(name: str, user: str, password: str, dsn: str, wallet_password: str) -> None:
    """Update Database"""
    get_databases()
    # Check if the database configuration is changed, or if not CONNECTED
    if (
        state.database_config[name]["user"] != user
        or state.database_config[name]["password"] != password
        or state.database_config[name]["dsn"] != dsn
        or state.database_config[name]["wallet_password"] != wallet_password
        or not state.database_config[name]["connected"]
    ):
        try:
            _ = api_call.patch(
                endpoint=f"v1/databases/{name}",
                payload={
                    "json": {
                        "user": user,
                        "password": password,
                        "dsn": dsn,
                        "wallet_password": wallet_password,
                    }
                },
            )
            logger.info("Database updated: %s", name)
            state.database_config[name]["connected"] = True
            get_databases(force=True)
        except api_call.ApiError as ex:
            logger.error("Database not updated: %s (%s)", name, ex)
            state.database_config[name]["connected"] = False
            state.database_error = str(ex)
    else:
        st.info(f"{name} Database Configuration - No Changes Detected.", icon="ℹ️")
        time.sleep(2)


def drop_vs(vs: dict) -> None:
    """Drop a Vector Storage Table"""
    api_call.delete(endpoint=f"v1/embed/{vs['vector_store']}")
    get_databases(force=True)

def select_ai_profile() -> None:
    """Update the chosen SelectAI Profile"""
    st_common.update_user_settings("selectai")
    st_common.patch_settings()
    selectai_df.clear()

@st.cache_data
def selectai_df(profile):
    """Get SelectAI Object List and produce Dataframe"""
    logger.info("Retrieving objects from SelectAI Profile: %s", profile)
    st_common.patch_settings()
    selectai_objects = api_call.get(endpoint="v1/selectai/objects")
    df = pd.DataFrame(selectai_objects, columns=["owner", "name", "enabled"])
    df.columns = ["Owner", "Name", "Enabled"]
    return df


def update_selectai(sai_new_df: pd.DataFrame, sai_old_df: pd.DataFrame) -> None:
    """Update SelectAI Object List"""
    changes = sai_new_df[sai_new_df["Enabled"] != sai_old_df["Enabled"]]
    if changes.empty:
        st.toast("No changes detected.", icon="ℹ️")
    else:
        enabled_objects = sai_new_df[sai_new_df["Enabled"]].drop(columns=["Enabled"])
        enabled_objects.columns = enabled_objects.columns.str.lower()
        try:
            _ = api_call.patch(
                endpoint="v1/selectai/objects", payload={"json": json.loads(enabled_objects.to_json(orient="records"))}
            )
            logger.info("SelectAI Updated. Clearing Cache.")
            selectai_df.clear()
        except api_call.ApiError as ex:
            logger.error("SelectAI not updated: %s", ex)


#####################################################
# MAIN
#####################################################
def main() -> None:
    """Streamlit GUI"""
    remove_footer()
    st.header("Database", divider="red")
    st.write("Configure the database used for Vector Storage and SelectAI.")
    try:
        get_databases()  # Create/Rebuild state
    except api_call.ApiError:
        st.stop()

    # TODO(gotsysdba) Add select for databases
    name = "DEFAULT"
    st.subheader("Configuration")
    with st.form("update_database_config"):
        user = st.text_input(
            "Database User:",
            value=state.database_config[name]["user"],
            key="database_user",
        )
        password = st.text_input(
            "Database Password:",
            value=state.database_config[name]["password"],
            key="database_password",
            type="password",
        )
        dsn = st.text_input(
            "Database Connect String:",
            value=state.database_config[name]["dsn"],
            key="database_dsn",
        )
        wallet_password = st.text_input(
            "Wallet Password (Optional):",
            value=state.database_config[name]["wallet_password"],
            key="database_wallet_password",
            type="password",
        )
        if state.database_config[name]["connected"]:
            st.success("Current Status: Connected")
        else:
            st.error("Current Status: Disconnected")
            if "database_error" in state:
                st.error(f"Update Failed - {state.database_error}", icon="🚨")

        if st.form_submit_button("Save"):
            patch_database(name, user, password, dsn, wallet_password)
            st.rerun()

    if state.database_config[name]["connected"]:
        # Vector Stores
        #############################################
        st.subheader("Database Vector Storage", divider="red")
        st.write("Existing Vector Storage Tables in Database.")
        with st.container(border=True):
            if state.database_config[name]["vector_stores"]:
                vs_col_format = st.columns([2, 5, 10, 3, 3, 5, 3])
                headers = ["\u200b", "Alias", "Model", "Chunk", "Overlap", "Dist. Metric", "Index"]

                # Header row
                for col, header in zip(vs_col_format, headers):
                    col.markdown(f"**<u>{header}</u>**", unsafe_allow_html=True)

                # Vector store rows
                for vs in state.database_config[name]["vector_stores"]:
                    vector_store = vs["vector_store"].lower()
                    fields = ["alias", "model", "chunk_size", "chunk_overlap", "distance_metric", "index_type"]
                    # Delete Button in Column1
                    vs_col_format[0].button(
                        "",
                        icon="🗑️",
                        key=f"vector_stores_{vector_store}",
                        on_click=drop_vs,
                        args=[vs],
                        help="Drop Vector Storage Table",
                    )
                    for col, field in zip(vs_col_format[1:], fields):  # Starting from col2
                        col.text_input(
                            field.capitalize(),
                            value=vs[field],
                            label_visibility="collapsed",
                            key=f"vector_stores_{vector_store}_{field}",
                            disabled=True,
                        )
            else:
                st.write("No Vector Stores Found")

        # Select AI
        #############################################
        st.subheader("SelectAI", divider="red")
        selectai_profiles = state.database_config[name]["selectai_profiles"]
        if state.database_config[name]["selectai"] and len(selectai_profiles) > 0:
            if not state.user_settings["selectai"]["profile"]:
                state.user_settings["selectai"]["profile"] = selectai_profiles[0]
            # Select Profile
            st.selectbox(
                "Profile:",
                options=selectai_profiles,
                index=selectai_profiles.index(state.user_settings["selectai"]["profile"]),
                key="selected_selectai_profile",
                on_change=select_ai_profile,
            )
            selectai_objects = selectai_df(state.user_settings["selectai"]["profile"])
            if not selectai_objects.empty:
                sai_df = st.data_editor(
                    selectai_objects,
                    column_config={
                        "enabled": st.column_config.CheckboxColumn(label="Enabled", help="Toggle to enable or disable")
                    },
                    use_container_width=True,
                    hide_index=True,
                )
                if st.button("Apply SelectAI Changes", type="secondary"):
                    update_selectai(sai_df, selectai_objects)
                    st.rerun()
            else:
                st.write("No objects found for SelectAI.")
        else:
            if not state.database_config[name]["selectai"]:
                st.write("Unable to use SelectAI with Database.")
            elif len(selectai_profiles) == 0:
                st.write("No SelectAI Profiles Found.")


if __name__ == "__main__" or "page.py" in inspect.stack()[1].filename:
    main()
