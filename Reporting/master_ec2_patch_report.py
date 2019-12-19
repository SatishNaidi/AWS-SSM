import boto3
import pprint
import csv
from datetime import datetime, date, time
import json
import os


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def pp(item):
    """Pretty Prints the output based on Content"""
    pprint.pprint(item)


def gather_ec2_instance_info(ec2_client):
    pages = ec2_client.get_paginator('describe_instances')
    all_instances_info = []
    for page in pages.paginate():
        for reservation in page.get("Reservations"):
            for instance in reservation.get("Instances"):
                all_instances_info.append(instance)
    return all_instances_info


def write_to_csv(filename, list_of_dict):
    """
    :param filename:
    :param list_of_dict:
    :return:
    """
    # Making sure to write to /tmp dir if running on AWS Lambda other wise to current dir
    if __name__ == "__main__":
        if not os.path.exists("tmp/"):
            os.mkdir("tmp")
        filename = "tmp/" + filename
    else:
        filename = "/tmp/" + filename

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


def lambda_handler(event, context):
    """
    Default Handler
    """
    # Connection Objects
    ec2_client = boto3.client('ec2', region_name="us-east-1")

    try:
        bucket_name = os.environ['bucket_name']
    except Exception as err:
        print("Env Variable 'bucket_name' doesn't exits")
        bucket_name = 'madhav-ssm-logs'

    try:
        slave_function = os.environ['slave_function']
    except Exception as err:
        print("Env Variable 'bucket_name' doesn't exits")
        slave_function = 'SSM-EC2PatchSlave'

    states = ["Installed", "Missing", "Failed"]

    # EC2Report
    ec2_info = gather_ec2_instance_info(ec2_client)
    required_info_instance_ids = {item["InstanceId"]: item for item in ec2_info}
    lambda_client = boto3.client('lambda', region_name="us-east-1")
    final_response = []
    for each_instance in required_info_instance_ids:
        print("Invoking Lambda: ", each_instance)
        response = lambda_client.invoke(
            FunctionName=slave_function,
            InvocationType='Event',
            LogType='Tail',
            Payload=json.dumps(json.loads(json.dumps(required_info_instance_ids[each_instance], default=json_serial)))
        )
        print(response)
        final_response.append("Invoking Lambda: "+each_instance)

    return {
        'statusCode': 200,
        'body': final_response
    }


if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))