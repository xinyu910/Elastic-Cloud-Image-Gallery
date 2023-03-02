# Cloud-Computing-MemCache (UofT ECE 1779 Project)

# About Project

This project is a storage web application with an in-memory key-value memory cache. Python and the Flask framework are used to implement this project. This project will also be deployed and run on Amazon EC2. The project consists of two flask instances, one is called FrontEnd which displays web pages and interacts with users, and the other one is an internal memcache integrated with a scheduler for periodic reporting statistics tasks. 

Key components include:

* A web browser that initiates requests

* A web front end that manages requests and operations

* A local file system where all data is stored

* A mem-cache that provides faster access

* A relational database



# Prerequisites

Main packages required:

* python 3.8
* flask 2.2.2
* mysql-connector 2.2.9
* requests 3.7.0
* APScheduler 3.8.0
* Werkzeug 2.2.2

Execute `start.sh` will install the required packages for you.

# Installation

Make sure port 5000 is opened before initializing the server.

Use `git clone https://github.com/xinyu910/Cloud--Image-Gallery.git`

Download the software package, run `start.sh` in the root dictionary to start the system.

Go to `localhost:5000` to access the application.
