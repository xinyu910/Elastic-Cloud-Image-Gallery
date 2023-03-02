CREATE DATABASE IF NOT EXISTS memcache;

USE memcache;

DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS configurations;


CREATE TABLE images(image_key varchar(100) NOT NULL,
                    image_path varchar(200) NOT NULL,
                    PRIMARY KEY (image_key));

CREATE TABLE configurations(config_id int NOT NULL DEFAULT 1,
                            capacity int NOT NULL,
                            policy varchar(100) NOT NULL,
                            PRIMARY KEY (config_id));

INSERT INTO configurations VALUES(1, 1024, "Random Replacement");