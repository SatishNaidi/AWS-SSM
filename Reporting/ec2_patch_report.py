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


def _flatten_json(y):
    """
    Flattens json, ex:
    {
    "id":
        {
        "name":"value"
        }
    } will be converted to { "id_name":"value" }
    """
    out = {}

    def flatten(x, name=''):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)
    return out


def format_nested_keys(input_dict):
    all_keys = list(input_dict.keys())
    for each_key in all_keys:
        if each_key == "Tags":
            for value in input_dict["Tags"]:
                if value["Key"] == "Name":
                    input_dict["Name"] = value["Value"]
                else:
                    input_dict["Tag_"+value["Key"]] = value["Value"]
            del input_dict["Tags"]
        elif each_key == "SecurityGroups":
            attr = []
            for value in input_dict["SecurityGroups"]:
                attr.append(value["GroupName"] + ":" + value["GroupId"])
            input_dict["SecurityGroups"] = ",".join(attr)
        elif each_key == "IamInstanceProfile":
            input_dict["IamInstanceProfile"] = input_dict["IamInstanceProfile"]["Arn"]
        elif each_key == "State":
            input_dict["State"] = input_dict["State"]["Name"]
        elif each_key == "LaunchTime":
            input_dict["LastBootTime"] = input_dict["LaunchTime"]
            del input_dict["LaunchTime"]
        else:
            pass
    return _flatten_json(input_dict)


def gather_ec2_instance_info(ec2_client):
    pages = ec2_client.get_paginator('describe_instances')
    all_instances_info = []
    for page in pages.paginate():
        for reservation in page.get("Reservations"):
            for instance in reservation.get("Instances"):
                all_instances_info.append(instance)
    return all_instances_info


def divide_chunks(items_list, n):
    # looping till length l
    for i in range(0, len(items_list), n):
        yield items_list[i:i + n]


def gather_instance_patch_states(ssm_client, ec2_instance_ids):
    pages = ssm_client.get_paginator('describe_instance_patch_states')
    chunked_ids = list(divide_chunks(ec2_instance_ids, 49))
    instance_patches = []
    for each_chunk in chunked_ids:
        for page in pages.paginate(InstanceIds=each_chunk):
            instance_patches.extend(page["InstancePatchStates"])
    return instance_patches


def gather_instance_patch_info(ssm_client):
    pages = ssm_client.get_paginator('describe_instance_information')
    all_instances = []
    for page in pages.paginate():
        all_instances.extend(page.get("InstanceInformationList", []))
    return all_instances


def detailed_instance_patch_report(ssm_client, instance_ids):
    all_instances_patch_report = []
    for each_instance in instance_ids:
        paginator = ssm_client.get_paginator('describe_instance_patches')
        states = ["Installed", "Missing", "Failed"]
        for each_state in states:
            try:
                page_iterator = paginator.paginate(InstanceId=each_instance,
                                                   Filters=[
                                                       {
                                                           'Key': 'State',
                                                           'Values': [
                                                               each_state
                                                           ]
                                                       }
                                                   ]
                                                   )
                items = []
                for each_page in page_iterator:
                    items.extend(each_page.get("Patches", []))
                items = [dict(item, InstanceId=each_instance) for item in items]
                instance_patch_report = json.loads(json.dumps(items, default=json_serial))
                all_instances_patch_report.extend(instance_patch_report)
            except Exception as outErr:
                print(outErr)
                pass
    return [i for i in all_instances_patch_report if i['State'] in states]


def filter_needed_fields(input_dict, filter_keys):
    final_out = []
    for each_instance in input_dict:
        json_formatted = json.loads(json.dumps(each_instance, default=json_serial))
        input_dict_keys = json_formatted.keys()
        each_instance_dict = {}
        for each_key in filter_keys:
            if each_key in input_dict_keys:
                each_instance_dict[each_key] = json_formatted[each_key]
        final_out.append(format_nested_keys(each_instance_dict))
    return final_out


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


def patch_base_line_names_to_ids(client, patch_baselines):
    try:
        paginator = client.get_paginator('describe_patch_baselines')
        response_base_lines = {}
        response_iterator = paginator.paginate(
            Filters=[
                {
                    'Key': 'NAME_PREFIX',
                    'Values': patch_baselines
                }
            ]
        )
        for page in response_iterator:
            for each_item in page["BaselineIdentities"]:
                base_line_id = each_item["BaselineId"]
                base_line_name = each_item["BaselineName"]
                response_base_lines[base_line_id] = base_line_name
        return response_base_lines
    except Exception as Err:
        print(Err)
        return False


def get_effective_patches(client, patch_base_lines):
    list_of_patches = []
    for pbid, pbname in patch_base_lines.items():
        try:
            patch_baseline_response = client.describe_effective_patches_for_patch_baseline(
                BaselineId=pbid
            )
            json_serialized = json.loads(json.dumps(patch_baseline_response, default=json_serial))
            for each_patch in json_serialized["EffectivePatches"]:
                new_item = each_patch["Patch"]
                new_item.update(each_patch["PatchStatus"])
                new_item.update({"PBName": pbname, "PBId": pbid})
                list_of_patches.append(new_item)
        except Exception as err:
            print(err, pbname, pbid)
            pass
    return list_of_patches


def upload_file_s3(client, bucket_name, to_be_upload_filename):
    only_filename = os.path.basename(to_be_upload_filename)
    try:
        res = client.upload_file(to_be_upload_filename, bucket_name, only_filename)
        return "File: "+only_filename + "Uploaded to bucket : "+bucket_name
    except Exception as err:
        print(err)
        return err


def lambda_handler(event, context):
    """
    Default Handler
    """
    # Connection Objects
    ec2_client = boto3.client('ec2', region_name="us-east-1")
    ssm_client = boto3.client('ssm', region_name="us-east-1")

    try:
        bucket_name = os.environ['bucket_name']
    except Exception as err:
        print("Env Variable 'bucket_name' doesn't exits")
        bucket_name = 'madhav-ssm-logs'

    # EC2Report
    field_names = ['InstanceId', 'State', 'IamInstanceProfile', 'Tags', 'LaunchTime']
    ec2_info = gather_ec2_instance_info(ec2_client)
    required_info = filter_needed_fields(ec2_info, field_names)
    required_info_instance_ids = {item["InstanceId"]: item for item in required_info}

    # Instance Patch State
    instance_patch_state = gather_instance_patch_states(ssm_client, list(required_info_instance_ids.keys()))
    instance_patch_state = {each_item["InstanceId"]: each_item for each_item in instance_patch_state}

    # Instance Patch Info
    instance_patch_info = gather_instance_patch_info(ssm_client)
    instance_patch_info = {each_item["InstanceId"]: each_item for each_item in instance_patch_info}

    # Detailed Instance Patch Report
    instance_patch_report = detailed_instance_patch_report(ssm_client, list(instance_patch_info.keys()))
    for each_instance in instance_patch_report:
        if each_instance["InstanceId"] in required_info_instance_ids:
            each_instance["Name"] = required_info_instance_ids[each_instance["InstanceId"]].get("Name","NA")
            each_instance["RunState"] = required_info_instance_ids[each_instance["InstanceId"]]["State"]


    s3_client = boto3.client("s3", region_name="us-east-1")

    current_date = datetime.now()
    dt_string = current_date.strftime("%d_%b_%Y_%H_%M")
    ec2_patch_report = "EC2_Patch_Report_"+dt_string+".csv"
    print(write_to_csv(ec2_patch_report, instance_patch_report))
    final_response = {}

    try:
        result = upload_file_s3(s3_client,bucket_name, ec2_patch_report)
        final_response[os.path.basename(ec2_patch_report)] = result
    except Exception as err:
        print("Error in Uploading file : " + ec2_patch_report)
        final_response[os.path.basename(ec2_patch_report)] = "Upload Failed"
    return {
        'statusCode': 200,
        'body': final_response
    }


if __name__ == "__main__":
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))