from flask import request, jsonify, g
import datetime
from Memcache import webapp, memcache
import sys
import random
from utils.config import connect_to_database
from Memcache.memcache_stat import Stats
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import json
from Autoscaler.cloudwatch import CloudwatchAPI

'''///INIT GLOBAL DATA///'''
global memcacheConfig
global cacheState
cacheState = Stats()  # currently testing, use cacheState.hit cacheState.miss for hit/miss rate
print("memcache is running")

global cloudwatch
cloudwatch = CloudwatchAPI()

"""///For database connection///"""


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = connect_to_database()
    return db


@webapp.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def get_config():
    cnx = get_db()
    cursor = cnx.cursor()
    query = '''SELECT capacity, policy
                    FROM configurations WHERE config_id = 1;'''

    cursor.execute(query)
    rows = cursor.fetchall()
    cnx.close()
    global memcacheConfig
    memcacheConfig = {'capacity': rows[0][0], 'policy': rows[0][1]}


"""///FOR WRITING TO DB EVERY 5 SEC///"""


def refresh_stat():
    """
    refresh stat(writing to the database every 5 second, recoding memcache statistics)
    with webapp context defined below

    """
    global cacheState
    global metrics

    with webapp.app_context():
        numOfItem = len(memcache.keys())
        totalSize = cacheState.total_image_size / 1048576
        numOfRequests = cacheState.reqServed_num
        if cacheState.hitCount != 0 or cacheState.missCount != 0:
            hitmiss = cacheState.missCount + cacheState.hitCount
            missRate = cacheState.missCount / hitmiss
            hitRate = cacheState.hitCount / hitmiss

        else:
            missRate = 0
            hitRate = 0

        metricDict = {
            'hitRate': hitRate,
            'numOfRequests': numOfRequests,
            'totalSize': totalSize,
            'numOfItem': numOfItem,
            'missRate': missRate
        }
        for key in metricDict.keys():
            cloudwatch.putMetric(key, metricDict[key], cacheState.id)


with webapp.app_context():
    get_config()
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=refresh_stat, trigger="interval", seconds=5)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

"""///FUNCTION INVALIDATE KEY FOR MEMCACHE///"""


def subinvalidatekey(key):
    """
    subinvalidatekey delete key from memcache when needed
    """
    # request+1
    cacheState.reqServed_num += 1
    if key in memcache:
        cacheState.total_image_size = cacheState.total_image_size - sys.getsizeof(memcache[key]['content'])
        memcache.pop(key, None)
    data = {"success": "true"}
    response = webapp.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


"""///REPLACEMENT POLICY///"""


def dictLRU():
    """
    LRU: remove the "oldest" key in memcache
    """
    OldTimeStamp = min([d['time'] for d in memcache.values()])
    oldestKey = ""
    for key in memcache.keys():
        if memcache[key]['time'] == OldTimeStamp:
            oldestKey = key  # find oldest key
    # image size deducted
    cacheState.total_image_size = cacheState.total_image_size - sys.getsizeof(memcache[oldestKey]['content'])
    del memcache[oldestKey]  # delete oldest key


def dictRandom():
    """
    Remove a key randomly from memcahce
    """
    keys = list(memcache.keys())
    keyIndex = random.randint(0, len(keys) - 1)
    # image size deducted
    cacheState.total_image_size = cacheState.total_image_size - sys.getsizeof(memcache[keys[keyIndex]]['content'])
    del memcache[keys[keyIndex]]  # delete the random key


"""///CAPACITY CONTROL///"""


def fitCapacity(extraSize):
    """
    if the given size exceeded cache capacity, delete keys based on selected policy

    @param extraSize:
    """
    while (extraSize + cacheState.total_image_size) > memcacheConfig['capacity'] * 1048576 and bool(memcache):
        # capacity full
        if memcacheConfig['policy'] == "LRU":
            dictLRU()
        else:
            dictRandom()


"""///FUNCTION PUT KEY FOR MEMCACHE"""


def subPUT(key, value):
    """
    given key and image data, put key and image data into memcache
    always fit capacity make sure not overload

    :param key: key
    :param value: base64 image
    :return: response
    """
    """file type error"""
    # request+1
    cacheState.reqServed_num += 1

    if not value:
        data = {"success": "false",
                "error": {
                    "code": 400,
                    "message": "Error: unsupported file type"
                }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=400,
            mimetype='application/json'
        )
        return response

    image_size = sys.getsizeof(value)  # total image size larger than capacity
    if image_size > memcacheConfig['capacity'] * 1048576:
        data = {"success": "true"}
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json'
        )
        return response

    #   capacity allowed
    fitCapacity(image_size)  # fit capacity
    # add the key image pair in the cache
    memcache[key] = {'content': value, 'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    cacheState.total_image_size = cacheState.total_image_size + image_size
    data = {"success": "true"}
    response = webapp.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


"""///FUNCTION GRT KEY FOR MEMCACHE///"""


def subGET(key):
    """
    get method, returns images data
    also update time stamp
    @param key:
    @return: response code and content from memcache
    """
    # request+1
    cacheState.reqServed_num += 1
    if key in memcache.keys():
        # hit
        cacheState.hitCount += 1
        # timestamp update
        memcache[key]['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = {
            "success": "true",
            "content": memcache[key]['content']
        }
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json'
        )
        return response
    else:
        # miss
        cacheState.missCount += 1
        data = {"success": "false",
                "error": {
                    "code": 404,
                    "message": "Unknown Key"
                }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=404,
            mimetype='application/json'
        )
        return response


"""///FUNCTION CLEAN KEY AND CONTENT FOR MEMCACHE///"""


def subCLEAR():
    """
    clean everything in memcache
    reset memcache statistic
    @return: response
    """
    # request+1
    cacheState.reqServed_num += 1
    cacheState.total_image_size = 0
    cacheState.numOfItem = 0
    memcache.clear()
    data = {"success": "true"}
    response = webapp.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


"""///LINK WITH FRONT APP, WORKING ON ./MEM/<URL DEFINED BELOW>///"""


@webapp.route('/', methods=['POST', 'GET'])
def welcome():
    #   base page un used
    return "welcome"


@webapp.route('/GET', methods=['POST', 'GET'])
def GET():
    """
    wrap subGET function
    """
    key = request.json["key"]
    return subGET(key)


@webapp.route('/PUT', methods=['POST'])
def PUT():
    """
        wrap subPut function
    """
    key = request.json["key"]
    image = request.json["image"]
    return subPUT(key, image)


@webapp.route('/invalidateKey', methods=['POST', 'GET'])
def invalidateKey():
    """
    wrap subinvalidatekey function
    """
    key = request.json["key"]
    return subinvalidatekey(key)


@webapp.route('/clear', methods=['POST', 'GET'])
def clear():
    """
    wrap subCLEAR function
    """
    return subCLEAR()


@webapp.route('/refreshConfiguration', methods=['POST'])
def refreshConfiguration():
    """
    reconfigure the parameters based on the input
    """
    # request+1
    cacheState.reqServed_num += 1
    get_config()
    # change memcache based on new capacity (reduce memcache if new capacity is smaller)
    fitCapacity(0)
    data = {"success": "true"}
    response = webapp.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


@webapp.route('/updateId/<id>')
def getInstance_id(id):
    cacheState.id = id
    print('CacheState Id:', cacheState.id)
    return jsonify({'success': True,
                    'statusCode': 200})


@webapp.route('/getCacheList')
def getCacheList():
    data = {"success": "true",
            "memcache": memcache}
    response = webapp.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


@webapp.route('/RePUT', methods=['POST', 'GET'])
def RePUT():
    """
        Put but existing old timestamp
    """
    key = request.json["key"]
    image = request.json["image"]
    time = request.json["time"]

    print("memcache key time ", key, " ", time)
    cacheState.reqServed_num += 1
    if not image:
        data = {"success": "false",
                "error": {
                    "code": 400,
                    "message": "Error: unsupported file type"
                }}
        response = webapp.response_class(
            response=json.dumps(data),
            status=400,
            mimetype='application/json'
        )
        return response

    image_size = sys.getsizeof(image)  # total image size larger than capacity
    if image_size > memcacheConfig['capacity'] * 1048576:
        data = {"success": "true"}
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json'
        )
        return response

    #   capacity allowed
    fitCapacity(image_size)  # fit capacity
    # add the key image pair in the cache
    memcache[key] = {'content': image, 'time': time}
    cacheState.total_image_size = cacheState.total_image_size + image_size
    print("success")
    data = {"success": "true"}
    response = webapp.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


@webapp.route('/oneMinuteDataRefresh')
def oneMinuteDataRefresh():
    cacheState.hitCount = 0
    cacheState.missCount = 0
    cacheState.reqServed_num = 0
    data = {"success": "true",
            "memcache": memcache}
    response = webapp.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response
