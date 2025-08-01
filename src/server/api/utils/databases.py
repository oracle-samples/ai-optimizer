"""
Copyright (c) 2024, 2025, Oracle and/or its affiliates.
Licensed under the Universal Permissive License v1.0 as shown at http://oss.oracle.com/licenses/upl.
"""
# spell-checker:ignore selectai clob nclob

import oracledb

import common.schema as schema
import common.logging_config as logging_config

logger = logging_config.logging.getLogger("api.utils.database")


class DbException(Exception):
    """Custom Database Exceptions to be passed to HTTPException"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def connect(config: schema.Database) -> oracledb.Connection:
    """Establish a connection to an Oracle Database"""
    logger.info("Connecting to Database: %s", config.dsn)
    include_fields = set(schema.DatabaseAuth.model_fields.keys())
    db_config = config.model_dump(include=include_fields)
    logger.debug("Database Config: %s", db_config)
    # If a wallet password is provided but no wallet location is set
    # default the wallet location to the config directory
    if db_config.get("wallet_password") and not db_config.get("wallet_location"):
        db_config["wallet_location"] = db_config["config_dir"]
    # Check if connection settings are configured
    if any(not db_config[key] for key in ("user", "password", "dsn")):
        raise DbException(status_code=400, detail="missing connection details")

    # Attempt to Connect
    try:
        logger.debug("Attempting Database Connection...")
        conn = oracledb.connect(**db_config)
    except oracledb.DatabaseError as ex:
        if "ORA-01017" in str(ex):
            raise DbException(status_code=401, detail="invalid credentials") from ex
        if "DPY-6005" in str(ex):
            raise DbException(status_code=503, detail="unable to connect") from ex
        else:
            raise DbException(status_code=500, detail=str(ex)) from ex
    logger.debug("Connected to Databases: %s", config.dsn)
    return conn


def test(config: schema.Database) -> None:
    """Test connection and re-establish if no longer open"""
    try:
        config.connection.ping()
        logger.info("%s database connection is active.", config.name)
    except oracledb.DatabaseError:
        db_conn = connect(config)
        logger.info("Refreshing %s database connection.", config.name)
        config.set_connection(db_conn)
    except AttributeError as ex:
        raise DbException(status_code=400, detail="missing connection details") from ex


def disconnect(conn: oracledb.Connection) -> None:
    """Disconnect from an Oracle Database"""
    logger.debug("Disconnecting Databases Connection: %s", conn)
    return conn.close()


def execute_sql(conn: oracledb.Connection, run_sql: str, binds: dict = None) -> list:
    """Execute SQL against Oracle Database"""
    logger.debug("SQL: %s with binds %s", run_sql, binds)
    try:
        # Use context manager to ensure the cursor is closed properly
        with conn.cursor() as cursor:
            rows = None
            cursor.callproc("dbms_output.enable")
            status_var = cursor.var(int)
            text_var = cursor.var(str)
            cursor.execute(run_sql, binds)
            if cursor.description:  # Check if the query returns rows
                rows = cursor.fetchall()
                lob_columns = [
                    idx
                    for idx, fetch_info in enumerate(cursor.description)
                    if fetch_info.type_code in (oracledb.DB_TYPE_CLOB, oracledb.DB_TYPE_BLOB, oracledb.DB_TYPE_NCLOB)
                ]
                if lob_columns:
                    # Convert rows to list of dictionaries with LOB handling
                    rows = [
                        {
                            cursor.description[idx].name: (value.read() if idx in lob_columns else value)
                            for idx, value in enumerate(row)
                        }
                        for row in rows
                    ]
            else:
                cursor.callproc("dbms_output.get_line", (text_var, status_var))
                if status_var.getvalue() == 0:
                    logger.info("Returning DBMS_OUTPUT.")
                    rows = text_var.getvalue()
            return rows
    except oracledb.DatabaseError as ex:
        if ex.args:
            error_obj = ex.args[0]
            if hasattr(error_obj, "code") and error_obj.code == 955:
                logger.info("Table exists")
            if hasattr(error_obj, "code") and error_obj.code == 942:
                logger.info("Table does not exist")
            else:
                logger.exception("Database error: %s", ex)
                logger.info("Failed SQL: %s", run_sql)
                raise
        else:
            logger.exception("Database error: %s", ex)
            raise

    except oracledb.InterfaceError as ex:
        logger.exception("Interface error: %s", ex)
        raise
