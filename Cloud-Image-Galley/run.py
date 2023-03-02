#!../venv/bin/python

from werkzeug.serving import run_simple  # werkzeug development server
from werkzeug.middleware.dispatcher import DispatcherMiddleware

"""IMPORT FLASK INSTANCES FROM FOLDER ManagerApp AND FrontEnd"""
from FrontEnd import webapp as front
from ManagerApp import webapp as manager
from Autoscaler import webapp as scaler
from Memcache import webapp as mem
import threading

"""MERGE Three FLASK INSTANCES: SCALER, FRONTEND and MANAGER APP"""
applications = DispatcherMiddleware(front, {
    '/manager': manager,
    '/scaler': scaler
})


def run_app():
    mem.run(host='0.0.0.0', port='5001', debug=False, use_reloader=False, use_debugger=False, threaded=True)


def run_other_app():
    run_simple('0.0.0.0', 5000, applications,
               use_reloader=False,
               use_debugger=False,
               use_evalex=True,
               threaded=True)


if __name__ == "__main__":
    """THREADED = TRUE FOR THREE INSTANCE WORKING TOGETHER"""
    second_thread = threading.Thread(target=run_other_app)
    first_thread = threading.Thread(target=run_app)
    second_thread.start()
    first_thread.start()
