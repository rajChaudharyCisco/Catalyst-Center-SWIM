#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

Catalyst Center Software Image Management Script.

Copyright (c) 2024 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

"""

__author__ = "Rajesh Chaudhary"
__email__ = "rachaud2@cisco.com"
__version__ = "1.0"
__copyright__ = "Copyright (c) 2024 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.0"

import urllib3
import requests
import json
import time
import sys
import argparse
from argparse import RawTextHelpFormatter
from requests.auth import HTTPBasicAuth
#from urllib3.exceptions import InsecureRequestWarning
from cat_config import CatC_IP, CatC_PORT, USERNAME, PASSWORD
import logging
requests.packages.urllib3.disable_warnings()

# -------------------------------------------------------------------
# Custom exception definitions
# -------------------------------------------------------------------
class TaskTimeoutError(Exception):
    pass

class TaskError(Exception):
    pass


def get_token(CatC_IP, CatC_PORT, USERNAME, PASSWORD):
    url = 'https://%s:%s/dna/system/api/v1/auth/token'%(CatC_IP, CatC_PORT)
    auth = HTTPBasicAuth(USERNAME, PASSWORD)
    headers = {'content-type' : 'application/json'}
    try:
        response = requests.post(url, auth=auth, headers=headers, verify=False)
        token = response.json()['Token']
        logging.info('Got Token from Catalyst Center')
        logging.debug(f'Token: {token}')
        return token
    except requests.exceptions.RequestException as err:
        logging.error(err)
        raise SystemExit()
        
def get_image_info(token, version_name):
    headers = { 'x-auth-token': token,
                'content-type': 'application/json' }
    url = f"https://{CatC_IP}:{CatC_PORT}/dna/intent/api/v1/image/importation?version={version_name}" 
    try:
        response = requests.get(url, headers=headers, verify=False)
        info = response.json()['response']
        return info
        #return info[0]['imageUuid']
    except requests.exceptions.RequestException as err:
        logging.error(err)
        raise SystemExit()


def get_device_info(token, device_host_num):
    headers = { 'x-auth-token': token,
                'content-type': 'application/json' }
    url =f"https://{CatC_IP}:{CatC_PORT}/dna/intent/api/v1/network-device?hostname={device_host_num}"
    try:
        response = requests.get(url, headers=headers, verify=False)
        info = response.json()['response']
        return info
        #return info[0]['id']
    except requests.exceptions.RequestException as err:
        logging.error(err)
        raise SystemExit()

# Validate that the image being loaded is expected on the device family
#def validate():
     
# Distribute the software image to the given device
def distribute(token, imageUuid, deviceUuid):
    headers = { 'x-auth-token': token,
                'content-type': 'application/json' }
    
    body = []
    body.append({"deviceUuid": deviceUuid, "imageUuid": imageUuid})

    dist_url = f"https://{CatC_IP}:{CatC_PORT}/dna/intent/api/v1/image/distribution"
    print(body)

    response = post_and_wait(token,dist_url,body)

    print(response)
    parent_id = response['id']
    det_url = f"https://{CatC_IP}:{CatC_PORT}/dna/intent/api/v1/tasks?parentId={parent_id}"
    try:
        det_response = requests.get(det_url, headers=headers, verify=False)
        print(det_response.json())
    except requests.exceptions.RequestException as err:
        logging.error(err)
        sys.exit(1)


def activate(token, imageId, devId):
    headers = { 'x-auth-token': token,
                'content-type': 'application/json' }

    body = []
    body.append({"activateLowerImageVersion": True,
                 "deviceUpgradeMode": "currentlyExists",
                 "deviceUuid": devId,
                 "distributeIfNeeded": False,
                 "imageUuidList": [imageId],
                 "smuImageUuidList": []})
    
    act_url = f"https://{CatC_IP}:{CatC_PORT}/dna/intent/api/v1/image/activation/device"
    
    response = post_and_wait(token,act_url,body)
    print(response)
    parent_id = response['id']
    det_url = f"https://{CatC_IP}:{CatC_PORT}/dna/intent/api/v1/tasks?parentId={parent_id}"
    try:
        det_response = requests.get(det_url, headers=headers, verify=False)
        print(det_response.json())
    except requests.exceptions.RequestException as err:
        logging.error(err)
        sys.exit(1)



def post_and_wait(token, url, data):
    headers = { 'x-auth-token': token,
                'content-type': 'application/json' }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)
    except requests.exceptions.RequestException  as cerror:
        print ("Error processing request", cerror)
        sys.exit(1)

    taskid = response.json()['response']['taskId']
    print ("Waiting for Task %s" % taskid)
    task_result = wait_on_task(taskid, token, timeout=3600, retry_interval=60)

    return task_result
     

def wait_on_task(task_id, token, timeout, retry_interval):

    task_url = f"https://{CatC_IP}:{CatC_PORT}/dna/intent/api/v1/task/{task_id}"  
    
    headers = {
        "x-auth-token": token
    }
    start_time = time.time()

    while True:
        result = requests.get(url=task_url, headers=headers, verify=False)
        result.raise_for_status()

        response = result.json()["response"]
        logging.debug(json.dumps(response,indent=2))
        #print json.dumps(response)
        if "endTime" in response:
            return response
        else:
            if timeout and (start_time + timeout < time.time()):
                raise TaskTimeoutError("Task %s did not complete within the specified timeout "
                                       "(%s seconds)" % (task_id, timeout))

            print("Task=%s has not completed yet. Sleeping %s seconds..." %(task_id, retry_interval))
            time.sleep(retry_interval)

        if response['isError'] == True:
            raise TaskError("Task %s had error %s" % (task_id, response['progress']))

    return response

def main():
    logging.basicConfig(
    #filename='application_run.log',
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
    logging.info('starting the program.')
    
    parser = argparse.ArgumentParser(description='select options', formatter_class=RawTextHelpFormatter)
    parser.add_argument('--hostname', dest='host', required=True,
                        help='The hostname of the device to be upgraded')
    parser.add_argument('--version', dest='software',required=True,
                        help='Version of the software to be upgraded')

    args = parser.parse_args()

    #ver = "17.10.01.0.1444"
    #hostname = "DNA02-Edge1.csspod2.com"

    hostname = args.host
    ver = args.software

    cat_token = get_token(CatC_IP, CatC_PORT, USERNAME, PASSWORD)
    image_info = get_image_info(cat_token, ver)
    dev_info = get_device_info(cat_token,hostname)
    imageId = image_info[0]['imageUuid']
    devId = dev_info[0]['id']
    print(imageId, devId)
    distribute(cat_token, imageId, devId)
    activate(cat_token, imageId, devId)


if __name__ == '__main__':
    main()
