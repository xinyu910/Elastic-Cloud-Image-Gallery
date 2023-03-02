import mysql.connector

"""Use the following for RDS database. 
1. Create a database instance and input the password and master name entered as PASSWORD and USER below
2. After the creation of database instance, get the ENDPOINT and PORT from the instance details view
3. Database is created through start.sh command (load databse.sql file before running application)///'''
"""
db_config = {'USER': 'root',
             'REGION': 'us-east-1',
             'PASSWORD': '##',
             'DBNAME': '##',
             'ENDPOINT': '##',
             'PORT': '3306'}


def connect_to_database():
    return mysql.connector.connect(user=db_config['USER'],
                                   passwd=db_config['PASSWORD'],
                                   host=db_config['ENDPOINT'],
                                   database=db_config['DBNAME'],
                                   port=db_config['PORT'],
                                   ssl_ca='SSLCERTIFICATE')


ConfigAWS = {
    'aws_access_key_id': "##",
    'aws_secret_access_key': "##",
    'ami': 'ami-0c55ccffa6be24c0a',
    'subnetID': "subnet-04c36a14d949bfad0",
    'securityID': "sg-03c9d4a6850da2ef3"
}