#!/bin/bash

pip install -r requirements.txt
mysql -h ece-1779-assignment2.cfgqalg5swwx.us-east-1.rds.amazonaws.com -P 3306 -u root -p memcache < database.sql
python3 "run.py"