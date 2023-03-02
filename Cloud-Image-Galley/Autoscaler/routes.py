import boto3

from Autoscaler.ec2instances import MemcacheEC2
from Autoscaler import webapp
from flask import render_template, json, jsonify, request
from utils.config import ConfigAWS
from Autoscaler.cloudwatch import CloudwatchAPI

client = boto3.resource('ec2',
                        region_name='us-east-1',
                        aws_access_key_id=ConfigAWS['aws_access_key_id'],
                        aws_secret_access_key=ConfigAWS['aws_secret_access_key']
                        )
call_obj = MemcacheEC2(client)
cloudwatch = CloudwatchAPI()


@webapp.route('/')
@webapp.route('/home')
def home():
    """Render Homepage, returns: home page html"""
    return render_template("home.html")


@webapp.route('/getAllInstances', methods=['GET', 'POST'])
def getAllInstances():
    instances = call_obj.instance_list
    data = {
        'success': True,
        'instances': instances
    }
    return jsonify(data)


@webapp.route('/getAllIPs', methods=['GET', 'POST'])
def getAllIPs():
    ip_list = []
    instances = call_obj.instance_list
    for value in instances.values():
        ip_list.append(value["public_ip"])
    data = {
        'success': True,
        'ip_list': ip_list
    }
    return jsonify(data)


@webapp.route('/create', methods=['GET', 'POST'])
def create():
    data = call_obj.create_ec2_instance()
    if data["success"] == "true":
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json')
    else:
        response = webapp.response_class(
            response=json.dumps(data),
            status=500,
            mimetype='application/json')
    return response


@webapp.route('/bulkCreate', methods=['GET', 'POST'])
def bulkCreate():
    num = request.json["num"]
    data = call_obj.create_more_than_one_ec2_instance(num)
    if data["success"] == "true":
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json')
    else:
        response = webapp.response_class(
            response=json.dumps(data),
            status=500,
            mimetype='application/json')
    return response


@webapp.route('/terminate', methods=['GET', 'POST'])
def terminate():
    data = call_obj.terminate_ec2_instance(list(call_obj.instance_list.keys())[-1])
    if data["success"] == "true":
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json')
    else:
        response = webapp.response_class(
            response=json.dumps(data),
            status=500,
            mimetype='application/json')
    return response


@webapp.route('/terminateAll', methods=['GET', 'POST'])
def terminateAll():
    data = call_obj.terminate_everything()
    if data["success"] == "true":
        response = webapp.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json')
    else:
        response = webapp.response_class(
            response=json.dumps(data),
            status=500,
            mimetype='application/json')
    return response


@webapp.route('/getCloudWatchStats', methods=['GET', 'POST'])
def getCloudWatchStats():
    instances = call_obj.getRunningInstances()
    sumReq = cloudwatch.get_sum_metric(metric_name='numOfRequests', instances=instances)
    sumSize = cloudwatch.get_sum_metric(metric_name='totalSize', instances=instances)
    sumItem = cloudwatch.get_sum_metric(metric_name='numOfItem', instances=instances)
    meanHitRate = cloudwatch.get_mean_metric(metric_name='hitRate', instances=instances)
    meanMissRate = cloudwatch.get_mean_metric(metric_name='missRate', instances=instances)
    sumInstances = len(instances)
    rows = [sumReq, sumSize, sumItem, meanHitRate, meanMissRate, sumInstances]

    return jsonify({
        'success': True,
        'rows': rows
    })


@webapp.route('/getMissRate', methods=['GET', 'POST'])
def getMissRate():
    instances = call_obj.getRunningInstances()
    missrate = cloudwatch.get_mean_metric(metric_name='missRate', instances=instances)

    return jsonify({
        'success': True,
        'rate': missrate
    })
