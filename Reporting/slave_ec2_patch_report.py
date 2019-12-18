import boto3
from botocore.exceptions import ClientError
import pprint
import csv
from datetime import datetime, date, time
from botocore.config import Config
import json
import os
import sys
from time import sleep

BOTO3_CONFIG = Config(
    retries = dict(
        max_attempts = 10
    )
)

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def pp(item):
    """Pretty Prints the output based on Content"""
    pprint.pprint(item)


def detailed_instance_patch_report(ssm_client, instance_id):
    retries = 1
    success = False
    states = ["Installed", "Missing", "Failed"]
    while not success:
        try:
            all_instances_patch_report = []
            paginator = ssm_client.get_paginator('describe_instance_patches')
            page_iterator = paginator.paginate(InstanceId=instance_id)
            items = []
            for each_page in page_iterator:
                print(each_page.get("Patches", []))
                items.extend(each_page.get("Patches", []))
            items = [dict(item, InstanceId=instance_id) for item in items]
            instance_patch_report = json.loads(json.dumps(items, default=json_serial))
            all_instances_patch_report.extend(instance_patch_report)
            success = True
        except ClientError as cl_err:
            print(cl_err)
            wait = retries * 5
            print(f'Error! Waiting {wait} secs and re-trying...')
            sys.stdout.flush()
            sleep(wait)
            retries += 1
        except Exception as outErr:
            print("**************")
            print(outErr)
            pass
    return [i for i in all_instances_patch_report if i['State'] in states]


def write_to_csv(filename, list_of_dict):
    """
    :param filename:
    :param list_of_dict:
    :return:
    """
    # Making sure to write to /tmp dir if running on AWS Lambda other wise to current dir
    if __name__ != "__main__":
        filename = "/tmp/"+filename

    json_serialized = json.loads(json.dumps(list_of_dict, default=json_serial))
    columns = []
    all_rows = []
    for each_item in json_serialized:
        row = ["" for col in columns]
        for key, value in each_item.items():
            try:
                index = columns.index(key)
            except ValueError:
                # this column hasn't been seen before
                columns.append(key)
                row.append("")
                index = len(columns) - 1
            row[index] = value
        all_rows.append(row)
    with open(filename, "w", newline='') as csv_file:
        writer = csv.writer(csv_file)
        # first row is the headers
        writer.writerow(columns)
        # then, the rows
        writer.writerows(all_rows)
    return filename


def upload_file_s3(client, bucket_name, to_be_upload_filename):
    only_filename = os.path.basename(to_be_upload_filename)
    dt_string = datetime.now().strftime("%Y/%m/%d/")

    try:
        res = client.upload_file(to_be_upload_filename, bucket_name, dt_string+only_filename)
        return "File: "+only_filename + "Uploaded to bucket : "+bucket_name
    except Exception as err:
        print(err)
        return err


def lambda_handler(event, context):
    """
    Default Handler
    """
    # event = {
    #     'AmiLaunchIndex': 0,
    #     'ImageId': 'ami-08c7081300f7d9abb',
    #     'InstanceId': 'i-0634e02aaf7cce7cc',
    #     'InstanceType': 't1.micro', 'KeyName': 'madhav-k', 'LaunchTime': '2019-12-17T03:01:34+00:00', 'Monitoring': {'State': 'disabled'}, 'Placement': {'AvailabilityZone': 'us-east-1c', 'GroupName': '', 'Tenancy': 'default'}, 'Platform': 'windows', 'PrivateDnsName': 'ip-172-31-17-43.ec2.internal', 'PrivateIpAddress': '172.31.17.43', 'ProductCodes': [], 'PublicDnsName': '', 'State': {'Code': 80, 'Name': 'stopped'}, 'StateTransitionReason': 'User initiated (2019-12-17 05:52:18 GMT)', 'SubnetId': 'subnet-1b5b6a51', 'VpcId': 'vpc-f143f18b', 'Architecture': 'x86_64', 'BlockDeviceMappings': [{'DeviceName': '/dev/sda1', 'Ebs': {'AttachTime': '2019-11-30T02:08:00+00:00', 'DeleteOnTermination': True, 'Status': 'attached', 'VolumeId': 'vol-090433522e4d6596a'}}], 'ClientToken': '', 'EbsOptimized': False, 'EnaSupport': True, 'Hypervisor': 'xen', 'IamInstanceProfile': {'Arn': 'arn:aws:iam::495830459543:instance-profile/SSM_EC2_Role', 'Id': 'AIPAXG4OMMSLYNVZVWKR6'}, 'NetworkInterfaces': [{'Attachment': {'AttachTime': '2019-11-30T02:07:59+00:00', 'AttachmentId': 'eni-attach-04800f6a8b4496f5b', 'DeleteOnTermination': True, 'DeviceIndex': 0, 'Status': 'attached'}, 'Description': '', 'Groups': [{'GroupName': 'default', 'GroupId': 'sg-0e75ff4b'}], 'Ipv6Addresses': [], 'MacAddress': '0a:bd:56:21:e3:cf', 'NetworkInterfaceId': 'eni-092cee035c2c3709d', 'OwnerId': '495830459543', 'PrivateDnsName': 'ip-172-31-17-43.ec2.internal', 'PrivateIpAddress': '172.31.17.43', 'PrivateIpAddresses': [{'Primary': True, 'PrivateDnsName': 'ip-172-31-17-43.ec2.internal', 'PrivateIpAddress': '172.31.17.43'}], 'SourceDestCheck': True, 'Status': 'in-use', 'SubnetId': 'subnet-1b5b6a51', 'VpcId': 'vpc-f143f18b', 'InterfaceType': 'interface'}], 'RootDeviceName': '/dev/sda1', 'RootDeviceType': 'ebs', 'SecurityGroups': [{'GroupName': 'default', 'GroupId': 'sg-0e75ff4b'}], 'SourceDestCheck': True, 'StateReason': {'Code': 'Client.UserInitiatedShutdown', 'Message': 'Client.UserInitiatedShutdown: User initiated shutdown'}, 'Tags': [{'Key': 'Name', 'Value': 'Window 2016'}, {'Key': 'Patch Group', 'Value': 'SRV_SATURDAY_4AM-6AM'}], 'VirtualizationType': 'hvm', 'CpuOptions': {'CoreCount': 1, 'ThreadsPerCore': 1}, 'CapacityReservationSpecification': {'CapacityReservationPreference': 'open'}, 'HibernationOptions': {'Configured': False}, 'MetadataOptions': {'State': 'applied', 'HttpTokens': 'optional', 'HttpPutResponseHopLimit': 1, 'HttpEndpoint': 'enabled'}}
    # Connection Objects
    print(event)
    ssm_client = boto3.client('ssm', region_name="us-east-1")

    try:
        bucket_name = os.environ['bucket_name']
    except Exception as err:
        print("Env Variable 'bucket_name' doesn't exits")
        bucket_name = 'madhav-ssm-logs'

    # Detailed Instance Patch Report
    instance_patch_report = detailed_instance_patch_report(ssm_client, event["InstanceId"])

    s3_client = boto3.client("s3", region_name="us-east-1")

    ec2_patch_report = event["InstanceId"]+".csv"
    instance_patch_report_file = write_to_csv(ec2_patch_report, instance_patch_report)
    final_response = {}

    try:
        result = upload_file_s3(s3_client, bucket_name, instance_patch_report_file)
        final_response[os.path.basename(instance_patch_report_file)] = result
    except Exception as err:
        print("Error in Uploading file : " + instance_patch_report_file)
        final_response[os.path.basename(instance_patch_report_file)] = "Upload Failed"
    return {
        'statusCode': 200,
        'body': final_response
    }


if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))