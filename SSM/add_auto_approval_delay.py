import boto3
import json
from datetime import datetime, date, timedelta
import os
import calendar


def find_second_tuesday_of_month(month):
    """
    Finds the second tuesday of the month in reference to current day
    Example:
        1) if month is 9, Second Tuesday will be Sept-10-2019
        2) if month is 10, Second Tuesday will be Oct-08-2019
    :return:
    """
    now = datetime.now()
    # print(now.month)
    first_day_of_month = datetime(now.year, month, 1)
    tuesday = 1  # Selected 1 since we need Tuesday
    first_tuesday = first_day_of_month + timedelta(
        days=((tuesday - calendar.monthrange(now.year, month)[0]) + 7) % 7)
    # days=0 for first tuesday, days=7 for second tuesday of the month and so on
    second_tuesday = first_tuesday + timedelta(days=7)  # Finding the Second Tuesday of the month
    return second_tuesday.date()


def calculate_days_from_patchday():
    """
    :return: return the numbers of days lapsed from the second tuesday of the month, If any error returns False Boolean
    """
    try:
        today = date.today()
        month = today.month
        patch_date = find_second_tuesday_of_month(month)
        # date_object = datetime.strptime(patch_date, '%b-%d-%Y').date()

        diff = today - patch_date
        if int(diff.days) < 0:
            patch_date = find_second_tuesday_of_month(month-1)
            today = date.today()
            diff = today - patch_date
            return int(diff.days)
        return int(diff.days)

    except Exception as err:
        print(err)
        return False


def collect_all_patchbaselines(client, patch_baselines):
    try:
        paginator = client.get_paginator('describe_patch_baselines')
        marker = None
        response_pages = []
        response_iterator = paginator.paginate(PaginationConfig={
            'PageSize': 1,
            'StartingToken': marker}
        )

        for page in response_iterator:
            response_pages.extend(page["BaselineIdentities"])

        to_be_modified_baselines = []
        for each in response_pages:
            if each["BaselineName"] in patch_baselines:
                to_be_modified_baselines.append(each)
        return to_be_modified_baselines
    except Exception as Err:
        print(Err)
        return False


def update_delay_for_patchbaseline(client, to_be_modified_baselines, delay_days):
    response_list = []
    for each_base_line in to_be_modified_baselines:
        response = client.update_patch_baseline(
            BaselineId=each_base_line['BaselineId'],
            ApprovalRules={
                'PatchRules': [
                    {
                        'PatchFilterGroup': {
                            'PatchFilters': [
                                {
                                    'Key': 'PATCH_SET',
                                    'Values': [
                                        'OS',
                                    ]
                                },
                            ]
                        },
                        'ApproveAfterDays': delay_days,
                        'EnableNonSecurity': False
                    },
                ]
            },
            Replace=False
        )
        response_list.append(response)
    print(response_list)
    return response_list


def lambda_handler(event, context):
    client = boto3.client('ssm')

    try:
        patch_baselines = os.environ['patch_baselines'].split(",")
        # patch_date = os.environ['patch_date']
    except Exception as err:
        print("Specified Env Variable doesn't exits")
        # return "Specified Env Variable doesn't exits")
        patch_baselines = ["Test", "Test2"]
        # patch_date = "Oct-08-2019"

    delay_days = calculate_days_from_patchday()
    print(delay_days)

    patches_to_be_edited = collect_all_patchbaselines(client, patch_baselines)
    response = update_delay_for_patchbaseline(client, patches_to_be_edited, delay_days)

    return {
        'statusCode': 200,
        'body': json.dumps(str(response))
    }


if __name__ == "__main__":
    # import pdb
    # pdb.set_trace()
    print(lambda_handler({}, {}))
