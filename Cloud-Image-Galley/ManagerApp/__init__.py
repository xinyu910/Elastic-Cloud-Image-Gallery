from flask import Flask, current_app

webapp = Flask(__name__, static_url_path='/FrontEnd/static', template_folder='../ManagerApp/templates')

from ManagerApp import main