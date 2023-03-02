import boto3

from utils.config import ConfigAWS

user_data = '''#!/bin/bash
            source /home/ubuntu/venv/bin/activate
            python3 /home/ubuntu/ECE_1779/Cloud-Image-Galley/mem_run.py'''


class MemcacheEC2(object):
    def __init__(self, ec2_client):
        self.client = ec2_client
        self.maxMemcacheNumber = 8
        # predefine the instance id you want to host your entire app on
        instance = self.client.Instance("i-0c841e13abbf09d94")
        self.instance_list = {"i-0c841e13abbf09d94": {
            "public_ip": instance.public_ip_address,
            "status": "running"
        }}
        self.amiID = ConfigAWS['ami']
        self.subnetID = ConfigAWS["subnetID"]
        self.security_id = ConfigAWS['securityID']

    def getRunningInstances(self):
        running_list = {}
        for instanceID, value in self.instance_list.items():
            if value["status"] == "running":
                running_list[instanceID] = value
        return running_list

    def getStoppedInstances(self):
        stopped_list = {}
        for instanceID, value in self.instance_list.items():
            if value["status"] == "stopped":
                stopped_list[instanceID] = value
        return stopped_list

    def getAllInstances(self):
        return list(self.instance_list.keys())

    def waitUntilReady(self, instance):
        """
        This function is a waiter function which waits for the instance to be fully functional,
        and sets the public ip and status of the instance in the instance list
        """
        instance.wait_until_running()
        instance.reload()
        public_ip = instance.public_ip_address
        instance_id = instance.instance_id
        waiter = self.client.meta.client.get_waiter('instance_status_ok')
        waiter.wait(InstanceIds=[instance_id])
        # key is instance id, value contains ip address and status
        self.instance_list[str(instance_id)] = {
            "public_ip": public_ip,
            "status": instance.state['Name']
        }

    # ------------------Function to create an instance----------------------------
    def create_ec2_instance(self):
        """
        A function to create a new ec2 instance
        """
        # Check the number of existing instances
        if len(self.instance_list) >= self.maxMemcacheNumber:
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "maximum node reached"
                }}
            return data

        try:
            # Creating an ec2 instance
            new_instance = self.client.create_instances(
                ImageId=self.amiID,
                MinCount=1,
                MaxCount=1,
                InstanceType="t2.micro",
                SubnetId=self.subnetID,
                SecurityGroupIds=[self.security_id],
                KeyName="ece1779",
                UserData=user_data)

            self.waitUntilReady(new_instance[0])
            print(self.instance_list)

            data = {
                "success": "true",
                "instance_id": new_instance[0].instance_id
            }
            return data

        except Exception as e:
            print(e)
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "Create instance error"
                }}
            return data

    def create_more_than_one_ec2_instance(self, num):
        """
        A function to create new ec2 instances
        """
        # Check the number of existing instances
        if len(self.instance_list) + num > self.maxMemcacheNumber:
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "maximum node reached"
                }}
            return data

        try:
            instances = []
            instance_ids = []
            for i in range(num):
                # Creating an ec2 instance
                new_instance = self.client.create_instances(
                    ImageId=self.amiID,
                    MinCount=1,
                    MaxCount=1,
                    InstanceType="t2.micro",
                    SubnetId=self.subnetID,
                    SecurityGroupIds=[self.security_id],
                    KeyName="ece1779",
                    UserData=user_data)

                new_instance[0].wait_until_running()
                new_instance[0].reload()
                instances.append(new_instance[0])
                instance_id = new_instance[0].instance_id
                instance_ids.append(instance_id)

            # wait all instances
            waiter = self.client.meta.client.get_waiter('instance_status_ok')
            waiter.wait(InstanceIds=instance_ids)

            # key is instance id, value contains ip address and status
            for i in instances:
                public_ip = i.public_ip_address
                instance_id = i.instance_id
                self.instance_list[str(instance_id)] = {
                    "public_ip": public_ip,
                    "status": i.state['Name']
                }

            print(self.instance_list)

            data = {
                "success": "true"
            }
            return data

        except Exception as e:
            print(e)
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "Create instance error"
                }}
            return data

    # ------------------Function to start an instance----------------------------
    def start_ec2_instance(self, instanceID):
        """This function starts a specific previously stopped instance"""
        try:
            if self.instance_list:
                if instanceID not in self.instance_list:
                    data = {
                        "success": "false",
                        "error": {
                            "code": 404,
                            "message": "instance ID not found"
                        }}
                    return data
            instance = self.client.Instance(instanceID)
            if instance.state['Name'] == 'stopped':
                self.client.meta.client.start_instances(InstanceIds=[instanceID], UserData=user_data)
                self.waitUntilReady(instance)
            data = {
                "success": "true"
            }
            return data

        except Exception as e:
            print(e)
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "start instance error"
                }}
            return data

    # ------------------Function to stop an instance----------------------------
    def stop_ec2_instance(self, instanceID):
        """This function stops a specific previously running instance"""
        try:
            if self.instance_list:
                if instanceID not in self.instance_list:
                    data = {
                        "success": "false",
                        "error": {
                            "code": 404,
                            "message": "instance ID not found"
                        }}
                    return data

                instance = self.client.Instance(instanceID)
                if instance.state['Name'] == 'running':
                    self.client.meta.client.stop_instances(InstanceIds=[instanceID])
                    self.instance_list[str(instanceID)] = {
                        "public_ip": "",
                        "status": "stopped"
                    }
            data = {
                "success": "true"
            }
            return data
        except Exception as e:
            print(e)
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "start instance error"
                }}
            return data

    # ------------------Function to terminate an instance----------------------------
    def terminate_ec2_instance(self, instanceID):
        """
        This function terminates a specific ec2 instance
        """
        try:
            if self.instance_list:
                if instanceID not in self.instance_list:
                    data = {
                        "success": "false",
                        "error": {
                            "code": 404,
                            "message": "instance ID not found"
                        }}
                    return data

                instance = self.client.Instance(instanceID)
                state = instance.state['Name']
                if state != "shutting-down" and state != "terminated":
                    self.client.meta.client.terminate_instances(InstanceIds=[instanceID])
                    self.instance_list.pop(instanceID)
            data = {
                "success": "true"
            }
            return data

        except Exception as e:
            print(e)
            data = {
                "success": "false",
                "error": {
                    "code": 500,
                    "message": "start instance error"
                }}
            return data

    def terminate_everything(self):
        """
        This function terminate all the ec2 instances in the instance list
        """
        key_list = []
        for key in self.instance_list:
            key_list.append(key)
        for i in range(len(key_list)):
            result = self.terminate_ec2_instance(key_list[i])
            if result["success"] == "false":
                return result

        data = {
            "success": "true"
        }
        return data


if __name__ == '__main__':
    client = boto3.resource('ec2', aws_access_key_id=ConfigAWS["aws_access_key_id"],
                            aws_secret_access_key=ConfigAWS['aws_secret_access_key'])

    call_obj = MemcacheEC2(client)
