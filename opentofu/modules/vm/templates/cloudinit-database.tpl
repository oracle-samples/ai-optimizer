#cloud-config
# Copyright (c) 2024, 2025, Oracle and/or its affiliates.
# All rights reserved. The Universal Permissive License (UPL), Version 1.0 as shown at http://oss.oracle.com/licenses/upl
# spell-checker: disable

write_files:
  - path: /tmp/db_priv_sql.sh
    permissions: '0755'
    content: |
      export API_SERVER_HOST=$(hostname -f)
      export DB_USERNAME='AI_OPTIMIZER'
      export DB_PASSWORD='${db_password}'
      export DB_DSN='${db_name}_TP'

      sql /nolog <<EOF
      WHENEVER SQLERROR EXIT 1
      WHENEVER OSERROR EXIT 1
      set cloudconfig /app/tns_admin/wallet.zip
      connect ADMIN/$DB_PASSWORD@$DB_DSN
      DECLARE
        l_conn_user VARCHAR2(255);
        l_user      VARCHAR2(255);
        l_tblspace  VARCHAR2(255);
      BEGIN
        BEGIN
            SELECT user INTO l_conn_user FROM DUAL;
            SELECT username INTO l_user FROM DBA_USERS WHERE USERNAME='$DB_USERNAME';
        EXCEPTION WHEN no_data_found THEN
            EXECUTE IMMEDIATE 'CREATE USER "$DB_USERNAME" IDENTIFIED BY "$DB_PASSWORD"';
        END;
        SELECT default_tablespace INTO l_tblspace FROM dba_users WHERE username = '$DB_USERNAME';
        EXECUTE IMMEDIATE 'ALTER USER "$DB_USERNAME" QUOTA UNLIMITED ON ' || l_tblspace;
        EXECUTE IMMEDIATE 'GRANT DB_DEVELOPER_ROLE TO "$DB_USERNAME"';
        EXECUTE IMMEDIATE 'GRANT EXECUTE ON DBMS_CLOUD TO "$DB_USERNAME"';
        EXECUTE IMMEDIATE 'GRANT EXECUTE ON DBMS_CLOUD_AI TO "$DB_USERNAME"';
        EXECUTE IMMEDIATE 'GRANT EXECUTE ON DBMS_CLOUD_PIPELINE TO "$DB_USERNAME"';
        EXECUTE IMMEDIATE 'ALTER USER "$DB_USERNAME" DEFAULT ROLE ALL';
      END;
      /
      BEGIN
        DBMS_NETWORK_ACL_ADMIN.APPEND_HOST_ACE(
          host => '$API_SERVER_HOST',
          ace  => xs\$ace_type(
            privilege_list => xs\$name_list('http', 'connect', 'resolve'),
            principal_name => '$DB_USERNAME',
            principal_type => xs_acl.ptype_db
          )
        );
      END;
      /
      EOF

  - path: /tmp/db_setup.sh
    permissions: '0755'
    content: |
      #!/bin/bash

      export OCI_CLI_AUTH=instance_principal
      mkdir -p /app/tns_admin
      # Wait for Database and Download Wallet
      max_attempts=40
      attempt=1
      while [ $attempt -le $max_attempts ]; do
        echo "Waiting for Database... ${db_name}"
        ID=$(oci db autonomous-database list --compartment-id ${compartment_id} --display-name ${db_name} \
          --lifecycle-state AVAILABLE --query 'data[0].id' --raw-output)
        if [ -n "$ID" ]; then
          echo "Database Found; Downloading Wallet for $ID..."
          oci db autonomous-database generate-wallet --autonomous-database-id $ID --password '${db_password}' --file /app/tns_admin/wallet.zip
          break
        fi
        sleep 15
        ((attempt++))
      done
      unzip -o /app/tns_admin/wallet.zip -d /app/tns_admin

runcmd:
  - su - oracleai -c '/tmp/db_setup.sh'
  - su - oracleai -c '/tmp/db_priv_sql.sh'
