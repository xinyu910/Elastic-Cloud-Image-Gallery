#!../venv/bin/python
from Memcache import webapp as mem
mem.debug = False

if __name__ == '__main__':
    mem.run(host='0.0.0.0', port='5001', debug=False, use_reloader=False, use_debugger=False)
