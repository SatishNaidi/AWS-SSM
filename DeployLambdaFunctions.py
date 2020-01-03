import boto3
import os
from distutils.dir_util import copy_tree
import json
import zipfile
import shutil
from botocore.exceptions import ClientError


def zip(src, dst):
    zf = zipfile.ZipFile("%s.zip" % (dst), "w", zipfile.ZIP_DEFLATED)
    abs_src = os.path.abspath(src)
    for dirname, subdirs, files in os.walk(src):
        for filename in files:
            if filename != os.path.basename(dst)+".zip":
                absname = os.path.abspath(os.path.join(dirname, filename))
                arcname = absname[len(abs_src) + 1:]
                # print(f"zipping {os.path.join(dirname, filename)} --> {arcname}")
                zf.write(absname, arcname)
            else:
                print(f"Ignoring {dst}.zip")
    zf.close()
    return os.path.basename(dst) + ".zip"


if __name__ == "__main__":
    folder_prefix = "Lambda"
    folders = list(filter(lambda x: os.path.isdir(x) and x.startswith(folder_prefix), os.listdir('.')))
    if not folders:
        print(f"No Folders Exists in Current Directory with Prefix {folder_prefix}, Exiting!")
    dir_path = os.path.dirname(os.path.realpath(__file__))
    temp_path = os.path.join(dir_path, "tmp")
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path, ignore_errors=False, onerror=None)

    for folder in folders:
        temp_lambda_path = os.path.join(dir_path, "tmp", folder)
        lambda_path = os.path.join(dir_path, folder)
        requirements = os.path.join(dir_path, folder, "requirements.txt")
        config_file = os.path.join(dir_path, folder, "config.json")
        if os.path.isfile(config_file):
            function_config = json.load(open(config_file))
        else:
            function_config = ""
            print(f"Config file {config_file} isn't exist for folder {lambda_path}, Ignoring the folder!")
            continue

        try:
            os.makedirs(temp_lambda_path)
        except FileExistsError:
            # directory already exists
            pass
        # Copies the contents to tmp Dir
        copy_tree(lambda_path, temp_lambda_path)

        if os.path.isfile(requirements):
            cmd = f"pip3 install -r {requirements} -t {temp_lambda_path} --upgrade"
            print(cmd)
            os.system(cmd)
        archive_file = os.path.join(temp_lambda_path, "Archive")

        code_zip = os.path.join(temp_lambda_path, zip(temp_lambda_path, archive_file))
        print(f"Deploying Lambda Function : {function_config['FunctionName']}")
        user_resp = input(f"Provide IAM Role ARN, or "
                          f"Press Enter to keep default value as \"{function_config['Role']}\":").strip()
        if user_resp not in [function_config['Role'], ""]:
            function_config['Role'] = user_resp

        for env_name, env_value in function_config.get("Environment", {}).get("Variables",{}).items():
            user_resp = input(f"Provide new value for Env Var \"{env_name}\" or "
                              f"Press Enter to keep default value as \"{env_value}\":").strip()

            if user_resp not in [env_value, ""]:
                function_config["Environment"]["Variables"][env_name] = user_resp

        lambda_client = boto3.client('lambda')
        try:
            response = lambda_client.create_function(
                FunctionName=function_config["FunctionName"],
                Runtime=function_config["Runtime"],
                Role=function_config["Role"],
                Handler=function_config["Handler"],
                Description=function_config.get("Description",""),
                Code={'ZipFile': open(code_zip, 'rb').read()},
                Timeout= int(function_config["Timeout"]),
                MemorySize=int(function_config["MemorySize"]),
                Environment=function_config.get("Environment", {}),
                Tags=function_config.get("Tags", {})
            )
            print(f"\nCreated New Function, ARN: {response['FunctionArn']}\n")
        except ClientError as error:
            # print(error)
            response = lambda_client.update_function_code(
                FunctionName=function_config["FunctionName"],
                ZipFile=open(code_zip, 'rb').read(),
                Publish=True,
            )
            response = lambda_client.update_function_configuration(
                FunctionName=function_config["FunctionName"],
                Runtime=function_config["Runtime"],
                Role=function_config["Role"],
                Handler=function_config["Handler"],
                Description=function_config.get("Description",""),
                Timeout=int(function_config["Timeout"]),
                MemorySize=int(function_config["MemorySize"]),
                Environment=function_config.get("Environment", {})
            )
            print(f"\nUpdated Code and Config for {response['FunctionArn']}\n")



