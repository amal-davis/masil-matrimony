#!/bin/bash
# Runs once, on first initialisation of an empty data volume.
# Lets the application user create/drop the test_<DB_NAME> database that
# Django's test runner uses. It is granted nothing beyond its own databases.
set -euo pipefail

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
GRANT ALL PRIVILEGES ON \`test_${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL
