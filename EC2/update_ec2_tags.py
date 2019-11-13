import boto3
import botocore
import sys

def ec2_list_of_instances(ec2_conn_obj, custom_tag_info, tag_name):
    """
    :param ec2_conn_obj: Takes connection object as an input
    :param custom_tag_info: EX: {
        "windows": "WINDOWS",
        "linux": "LINUX",
        "amzlnx": "AMAZON"
    } 
    :param tag_name: Patch Group
    :return:
    """
    try:
        pages=ec2_conn_obj.get_paginator('describe_instances')
        all_inst_dict_tolist = []
        for page in pages.paginate():
            for reservation in page.get("Reservations"):
                for instance in reservation.get("Instances"):
                    each_inst_dict = dict()
                    instance_image = instance.get("ImageId")
                    each_inst_dict["InstanceId"] = instance.get("InstanceId")
                    if instance.get("Platform") == "windows":
                        tag_value = custom_tag_info.get("windows","NoTagDefinedForWindows")
                    else:
                        tag_value = custom_tag_info.get("linux","NoTagDefinedForLinux")

                    image_description = ec2_conn_obj.describe_images(
                        Filters=[{'Name': 'image-id', 'Values': [instance_image]}])

                    if image_description.get("Images"):
                        if image_description.get("Images")[0].get("ImageOwnerAlias") == "amazon":
                            tag_value = custom_tag_info.get("amzlnx","NoTagDefinedForAmzLinux")

                    each_inst_dict["to_be_added_tag"] = {tag_name: tag_value}
                    all_tags = {}
                    for each_tag in instance.get("Tags", {}):
                        all_tags[each_tag["Key"]] = each_tag["Value"]
                    each_inst_dict["existing_tags"] = all_tags
                    all_inst_dict_tolist.append(each_inst_dict)
        return all_inst_dict_tolist
    except botocore.exceptions.EndpointConnectionError as err:
        print("Error:- Couldn't connect to the internet Please check the network setting")
        sys.exit(1)


def add_tags(ec2_conn_obj,tag_info):
    tags = []
    for each_item in tag_info["to_be_added_tag"]:
        item1 = {"Key": each_item, "Value": tag_info["to_be_added_tag"][each_item]}
        tags.append(item1)
    response = ec2_conn_obj.create_tags(
        Resources=[
            tag_info["InstanceId"]
        ],
        Tags=tags,
    )
    return response


def lambda_handler(event,context):
    # Make sure to add the regions which you do operate
    regions = ["us-east-1", "us-east-2"]
    tag_name = "Patch Group"
    custom_tag_info = {
        "windows": "WINDOWS",
        "linux": "LINUX",
        "amzlnx": "AMAZON"
    }
    to_be_copied_tag_auto_scaling_group = "RequestorSLID"
    final_response = {}
    for region in regions:
        try:
            ec2_conn_obj = boto3.client('ec2',region_name=region)
        except botocore.exceptions.NoCredentialsError:
            print("Unable to locate default credentials. Configure credentials")
            ec2_conn_obj = boto3.client(
                'ec2',
                aws_access_key_id="",
                aws_secret_access_key=""
            )
        tags_info = ec2_list_of_instances(ec2_conn_obj,custom_tag_info,tag_name)
        response = []
        for each_item in tags_info:
            # Change the text from "AutoScaling" to ignore the value for the tag
            if each_item["existing_tags"].get("aws:autoscaling:groupName"):
                response.append("AutoScaling Instance : "+each_item["InstanceId"])
                each_item["to_be_added_tag"][tag_name]=each_item["existing_tags"].get(to_be_copied_tag_auto_scaling_group,"RequestorSLID Doesn't exits")
            if each_item["to_be_added_tag"].items() <= each_item["existing_tags"].items():
                response.append("Tags Exists for " + each_item["InstanceId"])
            else:
                response.append("Tags doesn't Exists for " + each_item["InstanceId"])
                response.append(add_tags(ec2_conn_obj, each_item))
        final_response[region] = response
    return {
        'statusCode': 200,
        'body': final_response
    }


if __name__ == "__main__":
    print(lambda_handler({}, {}))
