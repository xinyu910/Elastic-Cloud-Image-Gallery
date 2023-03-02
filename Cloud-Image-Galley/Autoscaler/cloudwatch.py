import time
import datetime
import boto3
from utils.config import ConfigAWS


class CloudwatchAPI(object):

    def __init__(self):
        self.client = boto3.client('cloudwatch',
                                   region_name='us-east-1',
                                   aws_access_key_id=ConfigAWS['aws_access_key_id'],
                                   aws_secret_access_key=ConfigAWS['aws_secret_access_key'])

    def putMetric(self, metric_name, value, instance_name):
        response = self.client.put_metric_data(
            Namespace='ece1779/memcache',
            MetricData=[{
                'MetricName': metric_name,
                'Dimensions': [{
                    'Name': 'InstanceId',
                    'Value': instance_name
                }],
                'Value': value,
                'Unit': 'Percent'},
            ]
        )
        return response

    def putCacheMissRate(self, missrate, instance_name):

        response = self.client.put_metric_data(
            Namespace='ece1779/memcache',
            MetricData=[{
                'MetricName': 'miss_rate',
                'Dimensions': [{
                    'Name': 'InstanceId',
                    'Value': instance_name
                }],
                'Value': missrate,
                'Unit': 'Percent'},
            ]
        )
        return response

    # def getMetricStatistics(self, instances: list, intervals=60, period=60):

    #     responses = []
    #     for i in instances:
    #         responses.append(
    #             self.client.get_metric_statistics(
    #                 Namespace='ece1779/memcache',
    #                 MetricName='miss_rate',
    #                 Dimensions=[{
    #                     "Name": "InstanceId",
    #                     "Value": i
    #                 }],
    #                 StartTime=datetime.datetime.utcnow() - datetime.timedelta(seconds=intervals),
    #                 EndTime=datetime.datetime.utcnow(),
    #                 Period=period,
    #                 Statistics=['Maximum'],
    #                 Unit='Percent',
    #             )
    #         )
    #     return responses

    def getMetricStatistics(self, metric_name, instances: list, intervals=60, period=60):

        responses = []
        for i in instances:
            responses.append(
                self.client.get_metric_statistics(
                    Namespace='ece1779/memcache',
                    MetricName=metric_name,
                    Dimensions=[{
                        "Name": "InstanceId",
                        "Value": i
                    }],
                    StartTime=datetime.datetime.utcnow() - datetime.timedelta(seconds=intervals),
                    EndTime=datetime.datetime.utcnow(),
                    Period=period,
                    Statistics=['Maximum'],
                    Unit='Percent',
                )
            )
        return responses

    def get_mean_metric(self, metric_name, instances):

        responses = self.getMetricStatistics(metric_name, instances, intervals=60, period=60)

        sum_mean = 0
        numOfinstances = 0
        for i in responses:
            datapoints = i['Datapoints']
            if len(datapoints) == 0:
                continue
            elif len(datapoints) == 1:
                latest_data = datapoints[0]
                numOfinstances += 1
            else:
                numOfinstances += 1
                timestamps = [j['Timestamp'] for j in datapoints]
                timestamps.sort()
                latest_data = None
                for data in datapoints:
                    if data['Timestamp'] == timestamps[-1]:
                        latest_data = data
                        break
            if latest_data is None:
                raise Exception('Error finding latest datapoint when processing responces')
            else:
                print('Retrieve data from cloudwatch ......')
                print(latest_data.keys())
                print(latest_data['Maximum'])
                sum_mean += latest_data['Maximum']
        if numOfinstances == 0:
            return 0.0
        else:
            return sum_mean / numOfinstances

    def get_sum_metric(self, metric_name, instances):
        responses = self.getMetricStatistics(metric_name, instances, intervals=60, period=60)
        sumMet = 0
        for i in responses:
            datapoints = i['Datapoints']
            if len(datapoints) == 0:
                continue
            elif len(datapoints) == 1:
                latest_data = datapoints[0]

            else:
                timestamps = [j['Timestamp'] for j in datapoints]
                timestamps.sort()
                latest_data = None
                for data in datapoints:
                    if data['Timestamp'] == timestamps[-1]:
                        latest_data = data
                        break
            if latest_data is None:
                raise Exception('Error finding latest datapoint when processing responces')
            else:
                print('Retrieve data from cloudwatch ......')
                print(latest_data.keys())
                print(latest_data['Maximum'])
                sumMet += latest_data['Maximum']

        return sumMet


if __name__ == '__main__':
    cloudwatch = CloudwatchAPI()
