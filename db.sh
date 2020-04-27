#!/bin/bash

set -Eeu

usage() {
  echo "Usage: $0 (create|destroy|reset)"
}

if [ $# -ne 1 ]; then
  usage
  exit 1
fi

DBFILE=credentials.sqlite3

case $1 in
  "create")
    sqlite3 $DBFILE < schema.sql
    ;;

  "destroy")
    rm -rf $DBFILE
    ;;

  "reset")
    rm -rf $DBFILE
    sqlite3 $DBFILE < schema.sql
    ;;

  *)
    usage
    exit 1
    ;;
esac
