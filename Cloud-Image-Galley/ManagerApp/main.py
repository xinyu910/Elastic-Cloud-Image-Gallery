import math
import time
from flask import render_template, request, g, redirect, url_for, json, jsonify
import requests as api_call
from ManagerApp import webapp
from utils.config import connect_to_database
import threading
from utils.Helpers import MD5Hasher
import requests

AUTOSCALE_MODE = 0
configurations = {}

mem_capacity = 0
mem_policy = "LRU"
memcacheIP_List = []

global stats
stats = []

global growing


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


@webapp.before_first_request
def runOnAppStart():
    global memcacheIP_List
    res = requests.get("http://localhost:5000/scaler/getAllIPs")
    memcacheIP_List = res.json()['ip_list']
    # Autoscaler
    autoscaler_thread = threading.Thread(target=autoscalerMonitor)
    autoscaler_thread.start()
    stats_thread = threading.Thread(target = UpdateStats)
    stats_thread.start()


@webapp.route('/')
@webapp.route('/home')
def home():
    """Render Homepage, returns: home page html"""
    return render_template("home.html")


@webapp.route('/success')
def success():
    """Render success page"""
    msg = request.args.get('msg')
    return render_template("success.html", msg=msg)


@webapp.route('/failure')
def failure():
    """Render error page"""
    msg = request.args.get('msg')
    return render_template("failure.html", msg=msg)


@webapp.route('/clear_form')
def clear_form():
    """Display an empty HTML form that allows users to browse image by key"""
    return render_template("clear_form.html")


@webapp.route('/resize_form')
def resize_form():
    """Display an empty HTML form that allows users to browse image by key"""
    return render_template("resize_form.html")


@webapp.route('/statistics')
def statistics():
    """From database get and show past 30 minutes' memcache statistics"""
    print("Memcache Statistics!!!")
    global stats

    return render_template("statistics.html", rows=stats)


@webapp.route('/config')
def config():
    """render the configuration form, show form default value that is consistent with the database values"""
    cnx = get_db()
    cursor = cnx.cursor()

    cursor.execute("SELECT capacity, policy FROM configurations WHERE config_id = 1")

    rows = cursor.fetchall()
    cnx.close()
    return render_template("config.html", capacity=rows[0][0], policy=rows[0][1])


@webapp.route('/update_config', methods=['POST'])
def update_config():
    """update the new configuration value get from user in the database and memcache"""
    global mem_capacity
    global mem_policy

    if request.method == 'POST':
        mem_capacity = int(request.form['capacity'])
        mem_policy = request.form['policy']
    else:
        return redirect(url_for('failure', msg="Method not allowed"))

    if not mem_capacity or not mem_policy:
        return redirect(url_for('failure', msg="Missing form information"))

    if mem_capacity == '' or mem_policy == '':
        return redirect(url_for('failure', msg="One of the form parameter is empty"))

    cnx = get_db()
    cursor = cnx.cursor()

    cursor.execute("UPDATE configurations SET capacity = %s, policy = %s WHERE config_id = 1",
                   (mem_capacity, mem_policy))
    cnx.commit()
    cnx.close()

    # send reconfiguration request to backend
    response = api_call.get('http://localhost:5000/scaler/getAllIPs')
    ip_list = response.json()
    ip_list = ip_list['ip_list']

    for ip in ip_list:
        url = 'http://' + ip + ':5001/refreshConfiguration'
        res = api_call.post(url)
        if res.status_code != 200:
            return redirect(url_for('failure', msg="Memcache configuration error"))
    return redirect(url_for('success', msg="Configuration changed successfully"))


@webapp.route('/clear_data', methods=['POST'])
def clear_data():
    if request.method == 'POST':
        clear_result = request.form['clear']
    else:
        return redirect(url_for('failure', msg="Method not allowed"))

    if not clear_result:
        return redirect(url_for('failure', msg="Missing form information"))

    if clear_result == '':
        return redirect(url_for('failure', msg="Form parameter is empty"))

    if clear_result == "Clear All Image Data":
        # send clear s3 and RDS data request to FrontEnd
        res = api_call.post('http://localhost:5000/clearImageData')
        if res.status_code != 200:
            return redirect(url_for('failure', msg="S3 and RDS data clearing error"))

    # send clear data request to memcache
    response = api_call.get('http://localhost:5000/scaler/getAllIPs')
    ip_list = response.json()['ip_list']
    for ip in ip_list:
        url = 'http://' + ip + ':5001/clear'
        res = api_call.post(url)
        if res.status_code != 200:
            return redirect(url_for('failure', msg="Memcache clear error"))
    return redirect(url_for('success', msg="Data cleared successfully"))


@webapp.route('/automatic_form')
def automatic_form():
    """render autoscaler config form"""
    return render_template("automatic.html")


@webapp.route('/manual_form')
def manual_form():
    """render manual scaler resize form"""
    res = requests.get('http://localhost:5000/scaler/getAllIPs')
    numOfNode = len(res.json()['ip_list'])
    return render_template("manual.html", numOfNode=numOfNode)


@webapp.route('/automatic_resize', methods=['POST'])
def automatic_resize():
    if request.method == 'POST':
        MaxThreshold = float(request.form['MaxThreshold']) / 100
        MinThreshold = float(request.form['MinThreshold']) / 100
        ExpandRatio = float(request.form['ExpandRatio'])
        ShrinkRatio = float(request.form['ShrinkRatio'])

        global configurations
        configurations['MaxThreshold'] = MaxThreshold
        configurations['MinThreshold'] = MinThreshold
        configurations['ExpandRatio'] = ExpandRatio
        configurations['ShrinkRatio'] = ShrinkRatio

        if MaxThreshold == MinThreshold:
            return redirect(url_for('failure', msg="Max threshold should be significantly greater than Min threshold"))

        if not MaxThreshold or not MinThreshold or not ExpandRatio or not ShrinkRatio:
            return redirect(url_for('failure', msg="Missing form information"))

        if MaxThreshold == '' or MinThreshold == '' or ExpandRatio == '' or ShrinkRatio == '':
            return redirect(url_for('failure', msg="One of the form parameter is empty"))

        global AUTOSCALE_MODE
        AUTOSCALE_MODE = 1

    else:
        return redirect(url_for('failure', msg="Method not allowed"))

    return redirect(url_for('success', msg="AutoScaler is on"))


@webapp.route('/manual_resize', methods=['POST'])
def manual_resize():
    # moved expand and shrink node here based on the UI change and add redistribute key
    if request.method == 'POST':
        numOfNode = int(request.form['size'])
    else:
        return redirect(url_for('failure', msg="Method not allowed"))

    if not numOfNode:
        return redirect(url_for('failure', msg="Missing form information"))

    if numOfNode == '':
        return redirect(url_for('failure', msg="One of the form parameter is empty"))

    global AUTOSCALE_MODE
    AUTOSCALE_MODE = 0

    old_numOfNode = len(memcacheIP_List)
    if old_numOfNode == numOfNode:
        return redirect(url_for('success', msg="Nothing changes"))
    all_memcache = getMemcacheInfo()
    # expand
    if old_numOfNode + 1 == numOfNode:
        res = api_call.post('http://localhost:5000/scaler/create')
        if res.status_code == 200:
            time.sleep(10)
            if not redistributeKeys(all_memcache):
                return redirect(url_for('failure', msg="Redistribute error"))
            return redirect(url_for('success', msg="Memcache Pool Size Growing Successfully."))
        else:
            return redirect(url_for('failure', msg="Growing Failed. Error in creating instance."))
    # shrink
    if old_numOfNode - 1 == numOfNode:
        res = api_call.post('http://localhost:5000/scaler/terminate')
        if res.status_code == 200:
            if not redistributeKeys(all_memcache):
                return redirect(url_for('failure', msg="Redistribute error"))
            return redirect(url_for('success', msg="Memcache Pool Size Shrunk Successfully."))
        else:
            return redirect(url_for('failure', msg="Shrinking Failed. Error in terminating instance."))
    else:
        return redirect(url_for('failure', msg="IP numbers don't match"))


def redistributeKeys(all_memcache):
    res = api_call.post('http://localhost:5000/scaler/getAllIPs')
    ip_list = res.json()['ip_list']
    for i in ip_list:
        url = 'http://' + i + ':5001'
        api_call.post(url + '/clear')
    for key, value in all_memcache.items():
        if not putKeywithTime(key, value["content"], value["time"], ip_list):
            return False
    UpdateMemcacheID()
    return True


def putKeywithTime(key, image, time, list):
    ip, _ = MD5Hasher(key, list)
    print("key and ip ", key, " ", ip)
    url = 'http://' + ip + ':5001'
    dataSend = {"key": key, "image": image, "time": time}
    put_res = api_call.post(url + '/RePUT', json=dataSend)
    if put_res.status_code != 200:
        # false means error
        return False
    return True


def UpdateMemcacheID():
    response = api_call.get('http://localhost:5000/scaler/getAllInstances')
    instances = response.json()
    instances = instances['instances']
    print("get all instances", instances)
    print(instances.keys())

    for key in instances.keys():
        public_ip = instances[key]['public_ip']
        print(public_ip)
        url = 'http://' + public_ip + ':5001/updateId/' + str(key)
        print("update id for: ", url)
        api_call.get(str(url))
        print("get this time")

    res = api_call.get('http://localhost:5000/scaler/getAllIPs')
    ip_list = res.json()['ip_list']

    global memcacheIP_List
    memcacheIP_List = ip_list
    print("UpdateMemcacheID ip_list:", ip_list)
    data = {"ip_list": ip_list}
    api_call.get('http://localhost:5000/IPListUpdate', json=data, timeout=5)


def getMemcacheInfo():
    old_numOfNode = len(memcacheIP_List)
    all_memcache = {}
    for i in range(old_numOfNode):
        url = 'http://' + memcacheIP_List[i] + ':5001'
        memcache_res = api_call.get(url + '/getCacheList')
        all_memcache.update(memcache_res.json()['memcache'])
    return all_memcache


def autoscalerMonitor():
    with webapp.app_context():
        while True:
            autoScaler()
            UpdateMemcacheID()
            time.sleep(59)


def UpdateStats():
    with webapp.app_context():
        while True:
            res = requests.get("http://localhost:5000/scaler/getCloudWatchStats")
            global stats
            row = res.json()['rows']
            stats.append(row)
            '''
            res = api_call.get('http://localhost:5000/scaler/getAllIPs')
            ip_list = res.json()['ip_list']
            for i in ip_list:
                url = 'http://' + i + ':5001'
                api_call.get(url + '/oneMinuteDataRefresh')
            '''
            time.sleep(59)


def autoScaler():
    global AUTOSCALE_MODE
    global growing

    if AUTOSCALE_MODE == 1:
        res = api_call.get('http://localhost:5000/scaler/getMissRate')
        missrate = res.json()['rate']
        print("Missrate:", missrate)

        response = api_call.get('http://localhost:5000/scaler/getAllInstances')
        instances = response.json()
        instances = list(instances['instances'].keys())
        print(instances)

        global configurations
        all_memcache = getMemcacheInfo()
        growing = 0
        if missrate < configurations['MinThreshold'] and len(instances) > 1:
            num_instances = int(float(len(instances)) * configurations['ShrinkRatio'])

            if num_instances < 1:
                num_instances = 1
            if growing == 0:
                for i in range(len(instances) - num_instances):
                    res = api_call.get('http://localhost:5000/scaler/terminate')
                    if res.status_code != 200:
                        response = webapp.response_class(
                            response=json.dumps("Shrinking Failed. Error in terminating instance."),
                            status=200,
                            mimetype='application/json'
                        )
                        break
                if not redistributeKeys(all_memcache):
                    print('Redistribute error')
                    response = webapp.response_class(
                        response=json.dumps("Redistribute error."),
                        status=200,
                        mimetype='application/json'
                    )
                else:
                    response = webapp.response_class(
                        response=json.dumps("Memcache Pool Size Shrinked Successfully."),
                        status=200,
                        mimetype='application/json'
                    )
                print("Autoscaler Shrink:", response)

        elif missrate > configurations['MaxThreshold'] and len(instances) < 8:
            num_instances = math.ceil(float(len(instances)) * configurations['ExpandRatio'])
            print(num_instances)
            if num_instances > 8:
                num_instances = 8

            target = num_instances - len(instances)
            print("Target instances:", target)
            if growing == 0:
                growing = 1
                data = {"num": target}
                res = api_call.get('http://localhost:5000/scaler/bulkCreate', json=data)
                if res.status_code == 200:
                    time.sleep(10)
                    if not redistributeKeys(all_memcache):
                        print('Redistribute error')
                    response = webapp.response_class(
                        response=json.dumps("Memcache Pool Size Growing Successfully."),
                        status=200,
                        mimetype='application/json'
                    )
                else:
                    response = webapp.response_class(
                        response=json.dumps("Growing Failed. Error in creating instance."),
                        status=200,
                        mimetype='application/json'
                    )
                print("Autoscaler Grow:", response)
                # wait a bit to immediately shrink or expand
                time.sleep(10)
                growing = 0
        else:
            print('Miss rates are in accordance with the thresholds.')


@webapp.route('/wakeUp')
def wakeUp():
    return jsonify({"success": "true",
                    "statusCode": 200})
