import boto3
import botocore
import sys
import pprint


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
        all_instances = []
        list_of_images = {}
        for page in pages.paginate():
            for reservation in page.get("Reservations"):
                for instance in reservation.get("Instances"):
                    each_inst_dict = dict()
                    each_inst_dict["InstanceId"] = instance.get("InstanceId")
                    each_inst_dict["imageID"] = instance.get("ImageId")
                    list_of_images[instance.get("ImageId")] = ""
                    all_tags = {}
                    for each_tag in instance.get("Tags", {}):
                        all_tags[each_tag["Key"]] = each_tag["Value"]
                    each_inst_dict["existing_tags"] = all_tags
                    all_instances.append(each_inst_dict)
        # Gather all imageID's name
        images_description = ec2_conn_obj.describe_images(
            Filters=[{'Name': 'image-id', 'Values': list(list_of_images.keys())}])
        for each_image in images_description.get("Images"):
            image_name = each_image.get("Name").lower()
            image_id = each_image.get("ImageId").lower()
            list_of_images[image_id] = image_name
        pprint.pprint({ec2_conn_obj.meta.region_name:list_of_images})

        """
        Sample output from above code
        
        { 
            "us-east-1" : {
                    'ami-087c2c50437d0b80d': 'rhel-8.0.0_hvm-20190618-x86_64-1-hourly2-gp2',
                    'ami-0a85857bfc5345c38': 'amzn2-ami-hvm-2.0.20191024.3-x86_64-gp2',
                    'ami-0bff712af642c77c9': 'windows_server-2019-english-full-base-2019.10.09'
            }
        }
        """

        tag_value = None
        for each_instance in all_instances:
            image_id = each_instance["imageID"]
            image_name = list_of_images[image_id]
            if "win" in image_name:
                tag_value = custom_tag_info.get("windows","NoTagDefinedForWindows")
            elif "rhel" in image_name:
                tag_value = custom_tag_info.get("linux", "NoTagDefinedForLinux")
            elif "amzn" in image_name:
                tag_value = custom_tag_info.get("amzlnx", "NoTagDefinedForAmzonLinux")
            else:
                print("No OS type defined for "+instance.get("InstanceId")+ " with Image Name: " + image_name)
            if tag_value:
                each_instance["to_be_added_tag"] = {tag_name: tag_value}
        return all_instances

    except botocore.exceptions.EndpointConnectionError as err:
        print("Error:- Couldn't connect to the internet Please check the network setting")
        sys.exit(1)


def add_tags(ec2_conn_obj,tag_info):
    tags = []
    for each_item in tag_info["to_be_added_tag"]:
        item1 = {"Key": each_item, "Value": tag_info["to_be_added_tag"].get(each_item)}
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
    regions = ["us-west-2", "us-east-2"]
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
            print("Connection create for region " + region)
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
                if not each_item.get("to_be_added_tag"):
                    each_item["to_be_added_tag"] = {}
                each_item["to_be_added_tag"][tag_name] = each_item["existing_tags"].get(to_be_copied_tag_auto_scaling_group,"RequestorSLID Doesn't exits")
            if each_item.get("to_be_added_tag", {}).items() <= each_item.get("existing_tags", {}).items():
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
    import pdb
    pdb.set_trace()
    pprint.pprint(lambda_handler({}, {}))
