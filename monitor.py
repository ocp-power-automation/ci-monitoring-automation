import json
import re
import sys
from bs4 import BeautifulSoup
import urllib3
import requests
from datetime import datetime
import xml.etree.ElementTree as ET

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
PROW_URL = "https://prow.ci.openshift.org/job-history/gs/origin-ci-test/logs/"
PROW_VIEW_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs"


def load_config(config_file):

    '''
    Loads data from a config file.

    Parameter:
        config_file(string): Config file name.

    Returns:
        dict: Data from config file converted to dict data type.
    '''
    try:
        with open(config_file,'r') as config_file:
            config = json.load(config_file)
        return config
    except(OSError, json.JSONDecodeError) as e:
        print(f"Error while reading the config file: {e}")
        sys.exit(1)

def get_current_date():
    return datetime.now().date()

def parse_job_date(date):

    '''
    Converts string to Date datatype.

    Parameter:
        date: string.

    Returns:
        Date
    '''
    
    parse_date=datetime.strptime(date,"%Y-%m-%dT%H:%M:%SZ")
    job_run_date=parse_date.date()
    return job_run_date


def get_jobs(prow_link):
    
    '''
    Gets SpyglassLink of all the jobs which have run on the current day on a CI.

    Parameter:
        prow_link (string):  keyword used to generate CI link

    Returns:
        list(strings): SpyglassLinks of jobs
    '''

    url = PROW_URL + prow_link

    try:
        response = requests.get(url, verify=False, timeout=15)
    
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            script_elements = soup.find_all('script')
            selected_script_element = None

            for script_element in script_elements:
                script_content = script_element.string
                if script_content:
                    if 'allBuilds' in script_content:
                        selected_script_element = script_content
                        break
        
            if selected_script_element:
                var_name = 'allBuilds'
                pattern = rf'{var_name}\s*=\s*(.*?);'

                match = re.search(pattern, selected_script_element)
                if match:
                    all_jobs=match.group(1)
                    all_jobs_parsed=json.loads(all_jobs)
                    current_date=get_current_date()
                    jobs_run_today = []
                    for ele in all_jobs_parsed:
                        job_time=parse_job_date(ele["Started"])
                        if job_time == current_date and ele["Result"] != "PENDING":
                            job_log_path = ele["SpyglassLink"]
                            jobs_run_today.append(job_log_path)
                    return jobs_run_today                    
        else:
            return "Failed to get the prowCI response"
    except requests.Timeout as e:
        return "Request timed out"
    except requests.RequestException as e:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        return "Failed to extract the spy-links"

def get_n_recent_jobs(prow_link,n):
    
    '''
    Gets SpyglassLink of all the 'n' latest jobs run on the prowCI.

    Parameter:
        prow_link (string):  keyword used to generate CI link
        n (int): number of latest jobs

    Returns:
        list(strings): SpyglassLinks of jobs
    '''

    url = PROW_URL + prow_link

    try:
        response = requests.get(url, verify=False, timeout=15)
    
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            script_elements = soup.find_all('script')
            selected_script_element = None

            for script_element in script_elements:
                script_content = script_element.string
                if script_content:
                    if 'allBuilds' in script_content:
                        selected_script_element = script_content
                        break
        
            if selected_script_element:
                var_name = 'allBuilds'
                pattern = rf'{var_name}\s*=\s*(.*?);'

                match = re.search(pattern, selected_script_element)
                if match:
                    all_jobs=match.group(1)
                    all_jobs_parsed=json.loads(all_jobs)
                    n_jobs=[]
                    for ele in all_jobs_parsed[:n]:
                        if ele["Result"] != "PENDING":
                            n_jobs.append(ele["SpyglassLink"])
                    return n_jobs                   
        else:
            return "Failed to get the prowCI response"
    except requests.Timeout as e:
        return "Request timed out"
    except requests.RequestException as e:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        return "Failed to extract the spy-links"


def cluster_deploy_status(spy_link):

    '''
    Gets the status of cluster deployment step of a job.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.

    Returns:
        string: Cluster Deployment Status 
    '''

    job_type,job_platform = job_classifier(spy_link)
    if "mce" in spy_link:
        mce_install_log_url = PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/hypershift-mce-install/finished.json'

        try:
            response = requests.get(mce_install_log_url, verify=False, timeout=15)
            if response.status_code == 200:
                
                cluster_status = json.loads(response.text)
                cluster_result = "MCE-INSTALL "+ cluster_status["result"]
                if cluster_status["result"] == "SUCCESS":
                        # check mce-power-create status also
                    mce_power_log_url = PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/hypershift-mce-power-create/finished.json'

                    response = requests.get(mce_power_log_url, verify=False, timeout=15)
                    if response.status_code == 200:
            
                        cluster_status = json.loads(response.text)
                        cluster_result += "\nMCE-POWER-CREATE "+ cluster_status["result"]
                        if cluster_status["result"] == "SUCCESS":
                            cluster_result = "SUCCESS"
                        return cluster_result
                else:
                    return cluster_result
            else:
                return 'ERROR'
        except requests.Timeout:
            return "Request timed out"
        except requests.RequestException:
            return "Error while sending request to url"
        except json.JSONDecodeError as e:
            return 'ERROR'
    else:
        job_log_url = PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/ipi-install-' + job_platform +'-install/finished.json'
        if "sno" in spy_link:
            job_log_url = PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/upi-install-powervs-sno/finished.json'
        try:
            response = requests.get(job_log_url, verify=False, timeout=15)
            if response.status_code == 200:
                
                cluster_status = json.loads(response.text)
                return cluster_status["result"]
            else:
                return 'ERROR'
        except requests.Timeout:
            return "Request timed out"
        except requests.RequestException:
            return "Error while sending request to url"
        except json.JSONDecodeError as e:
            return 'ERROR'
    
def cluster_creation_error_analysis(spylink):

    '''
    Prints the reason for cluster deployment failure step of a job.

    Parameter:
        spylink (string):  SpyglassLink used to generate url to access logs of a job.
    '''

    job_type,job_platform = job_classifier(spylink)
    job_log_url = PROW_VIEW_URL + spylink[8:] + '/artifacts/' + job_type + '/ipi-install-' + job_platform +'-install/build-log.txt'
    
    try:
        response = requests.get(job_log_url,verify=False)

        if response.status_code == 200:

            installation_log = response.text
            if job_platform == "powervs":
                failed_line_index = installation_log.find("FAILED")
                cluster_failure_log = installation_log[failed_line_index:].splitlines()
                for line in cluster_failure_log[1:7]:
                    print(line)
                    
            elif job_platform == "libvirt":
                failed_line_index_1 = installation_log.find("level-error")
            
                if failed_line_index_1 == -1:
                    failed_line_index_2 = installation_log.find("level=fatal")
                    if failed_line_index_2 == -1:
                        failed_line_number_3 = installation_log.find("error:")
                        cluster_failure_log = installation_log[failed_line_number_3:].splitlines()

                        for line in cluster_failure_log[:7]:
                            print(line)
                    else:
                        cluster_failure_log = installation_log[failed_line_index_2:].splitlines()

                        for line in cluster_failure_log[:7]:
                            print(line)
                else:
                    cluster_failure_log = installation_log[failed_line_index_1:].splitlines()
                    for line in cluster_failure_log[1:7]:
                        print(line)
        else:
            print("Error while fetching cluster installation logs")
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"

def get_node_status(spy_link):

    '''
    Gets the node status of the job.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.

    Returns:
        string: Node Status.
    '''
    
    job_type,job_platform = job_classifier(spy_link)
    if job_platform == "powervs" or job_platform == "mce":
        job_type += "/gather-extra"
    else:
        job_type += "/gather-libvirt"
    
    node_log_url = PROW_VIEW_URL + spy_link[8:] + \
        "/artifacts/" + job_type +"/artifacts/oc_cmds/nodes"
    
    try:
        node_log_response = requests.get(node_log_url, verify=False, timeout=15)
        if "NAME" in node_log_response.text:
            response_str=node_log_response.text
            if "NotReady" in response_str:
                return "Some Nodes are in NotReady state"
            elif response_str.count("control-plane,master") != 3:
                return "Not all master nodes are up and running"
            elif (job_platform == "mce" and response_str.count("worker") != 3) or (job_platform != "mce" and response_str.count("worker-") != 2): 
                return "Not all worker nodes are up and running"
        else:
            return "Node details not found"
        return "All nodes are in Ready state"
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"

def check_node_crash(spy_link):

    '''
    Checks and prints if any node crash has occured in the cluster.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.
    '''

    if "mce" not in spy_link and "sno" not in spy_link:
        job_type,_ = job_classifier(spy_link)
        crash_log_url = PROW_VIEW_URL + spy_link[8:] + "/artifacts/" +job_type + "/ipi-conf-debug-kdump-gather-logs/artifacts/"
        
        try:
            crash_log_response = requests.get(crash_log_url, verify=False, timeout=15)
            if "kdump.tar" in crash_log_response.text:
                print("*********************************")
                print ("ERROR- Crash observed in the job")
                print("*********************************")
            else:
                print("No crash observed")
        except requests.Timeout:
            return "Request timed out"
        except requests.RequestException:
            return "Error while sending request to url"

def get_quota_and_nightly(spy_link):

    '''
    Gets lease/region where cluster is deployed and the nightly image used.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.

    Returns:
        lease(string): Acquired lease/region.
        nightly(string): Nighlty image used.
    '''

    _,job_platform = job_classifier(spy_link)
    lease = ""

    if 'ppc64le' in spy_link:
        build_log_url = PROW_VIEW_URL + spy_link[8:] + "/build-log.txt"
        if job_platform == "libvirt":
            job_platform+="-ppc64le"
        elif job_platform == "powervs":
            job_platform+="-[1-9]"

        zone_log_re = re.compile('(Acquired 1 lease\(s\) for {}-quota-slice: \[)([^]]+)(\])'.format(job_platform), re.MULTILINE|re.DOTALL)
        try:
            build_log_response = requests.get(build_log_url, verify=False, timeout=15)
            zone_log_match = zone_log_re.search(build_log_response.text)
            if zone_log_match is None:
                lease = "Failed to fetch lease information"
            else:
                lease = zone_log_match.group(2)
    # Fetch the nightly information for non-upgrade jobs
            if "upgrade" not in build_log_url:
                nightly_log_re = re.compile('(Resolved release ppc64le-latest to (\S+))', re.MULTILINE|re.DOTALL)
                nightly_log_match = nightly_log_re.search(build_log_response.text)
                if nightly_log_match is None:
                    rc_nightly_log_re = re.compile('(Using explicitly provided pull-spec for release ppc64le-latest \((\S+)\))', re.MULTILINE|re.DOTALL)
                    rc_nightly_log_match = rc_nightly_log_re.search(build_log_response.text)
                    if rc_nightly_log_match is None:
                        nightly = "Unable to fetch nightly information- No match found"
                    else:
                        nightly = rc_nightly_log_match.group(2)
                else:
                    nightly = "ppc64le-latest-"+ nightly_log_match.group(2)
    # Fetch nightly information for upgrade jobs- fetch both ppc64le-initial and ppc64le-latest
            else:
                nightly_initial_log_re = re.compile('(Resolved release ppc64le-initial to (\S+))', re.MULTILINE|re.DOTALL)
                nightly_initial_log_match = nightly_initial_log_re.search(build_log_response.text)
                if nightly_initial_log_match is None:
                    nightly = "Unable to fetch nightly ppc64le-initial information- No match found"
                else:
                    nightly = "ppc64le-initial-"+ nightly_initial_log_match.group(2)
                nightly_latest_log_re = re.compile('(Resolved release ppc64le-latest to (\S+))', re.MULTILINE|re.DOTALL)
                nightly_latest_log_match = nightly_latest_log_re.search(build_log_response.text)
                if nightly_latest_log_match is None:
                    nightly = nightly + " Unable to fetch nightly ppc64le-latest information- No match found"
                else:
                    nightly = nightly + " ppc64le-latest-"+ nightly_latest_log_match.group(2)
            return lease, nightly
        except requests.Timeout:
            return "Request timed out"
        except requests.RequestException:
            return "Error while sending request to url"
    
    elif 's390x' in spy_link:
        build_log_url = PROW_VIEW_URL + spy_link[8:] + "/build-log.txt"
        if job_platform == "libvirt":
            job_platform+="-s390x"

        zone_log_re = re.compile('(Acquired 1 lease\(s\) for {}-quota-slice: \[)([^]]+)(\])'.format(job_platform), re.MULTILINE|re.DOTALL)
        try:
            build_log_response = requests.get(build_log_url, verify=False, timeout=15)
            zone_log_match = zone_log_re.search(build_log_response.text)
            if zone_log_match is None:
                lease = "Failed to fetch lease information"
            else:
                lease = zone_log_match.group(2)
            nightly_log_re = re.compile('(Resolved release s390x-latest to (\S+))', re.MULTILINE|re.DOTALL)
            nightly_log_match = nightly_log_re.search(build_log_response.text)
            if nightly_log_match is None:
                rc_nightly_log_re = re.compile('(Using explicitly provided pull-spec for release s390x-latest \((\S+)\))', re.MULTILINE|re.DOTALL)
                rc_nightly_log_match = rc_nightly_log_re.search(build_log_response.text)
                if rc_nightly_log_match is None:
                    nightly = "Unable to fetch nightly information- No match found"
                else:
                    nightly = rc_nightly_log_match.group(2)
            else:
                nightly = "s390x-latest-"+ nightly_log_match.group(2)
            return lease, nightly
        except requests.Timeout:
            return "Request timed out"
        except requests.RequestException:
            return "Error while sending request to url"
    else:     
        build_log_url = PROW_VIEW_URL + spy_link[8:] + "/build-log.txt"
        try:
            build_log_response = requests.get(build_log_url, verify=False, timeout=15)
            # lease is not applicable for SNO hence checking only for MCE
            if "mce" in spy_link:
                job_platform = "aws" #currently it contains only aws hence hardcoding
                zone_log_re = re.compile('(Acquired 1 lease\(s\) for {}-quota-slice: \[)([^]]+)(\])'.format(job_platform), re.MULTILINE|re.DOTALL)
                zone_log_match = zone_log_re.search(build_log_response.text)
                if zone_log_match is None:
                    lease = "Failed to fetch lease information"
                else:
                    lease = zone_log_match.group(2)
            nightly_log_re = re.compile('(Resolved release multi-latest to (\S+))', re.MULTILINE|re.DOTALL)
            nightly_log_match = nightly_log_re.search(build_log_response.text)
            if nightly_log_match is None:
                nightly = "Failed to fetch nightly image"
            else:
                nightly = "multi-latest-"+ nightly_log_match.group(2)
            return lease, nightly
        except requests.Timeout:
            return "Request timed out"
        except requests.RequestException:
            return "Error while sending request to url"


def job_classifier(spy_link):

    '''
    Extracts the job type and platform information from SpyglassLink.

    Parameter:
        spy_link (string):  SpyglassLink used to filter the job_type and job_platform.

    Returns:
        job_type(string): It is a important keyword used while constructing url to access the artifacts.
        job_platform(string): The infrastructure where the cluster is deployed (ex: libvirt, powervs etc).
    '''

    pattern = r'ocp.*?/'
    if "mce" in spy_link:
        pattern = r'e2e.*?/'
    match = re.search(pattern,spy_link)

    if match:
        job_type = match.group(0)
        job_type = job_type.rstrip('/')
    job_platform = "mce"
    if spy_link.find("powervs") != -1:
        job_platform = "powervs"
    elif spy_link.find("libvirt") != -1:
        job_platform = "libvirt"
    elif spy_link.find("sno") != -1:
        job_platform = "sno"
    return job_type,job_platform


def get_failed_monitor_testcases(spy_link,job_type):

    '''
    Gets failed monitor testcases.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.
        job_type (string):  Keyword used to construct url to access the logs of a job.

    Returns:
        list(dict): List of failed monitor testcases.
    '''

    test_log_junit_dir_url = PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/"

    try:
        response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

        if response.status_code == 200:
            monitor_test_failure_summary_filename_re = re.compile('(test-failures-summary_monitor_2[^.]*\.json)')
            monitor_test_failure_summary_filename_match = monitor_test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
            if monitor_test_failure_summary_filename_match is not None:
                monitor_test_failure_summary_filename_str = monitor_test_failure_summary_filename_match.group(1)
                test_log_url=PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/" + monitor_test_failure_summary_filename_str
                response_2 = requests.get(test_log_url,verify=False, timeout=15)
                if response_2.status_code == 200:
                    data = response_2.json()
                    e2e_failure_list = data['Tests']
                    return e2e_failure_list
                else:
                    return "Failed to get response from e2e-test log file url!"
            else:
                return "Test summary file not found"
        else:
            return "Failed to get response from e2e-test directory url"
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        return "Failed to parse the data from e2e-test log file!"


def get_failed_monitor_testcases_from_xml(spy_link,job_type):

    '''
    Gets failed monitor testcases from conformance testsuite.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.
        job_type (string):  Keyword used to construct url to access logs of a job.

    Returns:
        list(string): List of failed monitor testcases.
    '''

    if "mce" in spy_link:
        test_type = "conformance-tests"
    else:
        test_type = "openshift-e2e-libvirt-test"
    test_log_junit_dir_url = PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/" + test_type + "/artifacts/junit/"
    try:
        response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

        if response.status_code == 200:
            test_failure_summary_filename_re = re.compile('(e2e-monitor-tests__2[^.]*\.xml)')
            test_failure_summary_filename_match = test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
            if test_failure_summary_filename_match is not None:
                test_failure_summary_filename_str = test_failure_summary_filename_match.group(1)
                test_log_url=PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/"+ test_type +"/artifacts/junit/" + test_failure_summary_filename_str
                monitor_failed_testcase=[]
                response = requests.get(test_log_url,verify=False,timeout=15)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    for idx,testcase in enumerate(root.iter('testcase')):
                        if testcase.find('failure') is not None:
                            current_name = testcase.get('name')
                            next_testcase = root[idx+1] if idx+1 < len(root) else None
                            prev_testcase = root[idx-1] if idx-1 >= 0 else None
                            if next_testcase is not None and next_testcase.get('name') != current_name and prev_testcase is not None and prev_testcase.get('name') != current_name:
                                monitor_failed_testcase.append(current_name)
                    return monitor_failed_testcase
            else:
                return "Monitor test file not found"
        else:
            return "Failed to get response from e2e-test directory url" 
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    except ET.ParseError as e:
        return "Failed to parse junit e2e log file!"



def get_testcase_frequency(spylinks, zone=None, tc_name = None):
    """
    To get the testcases failing with its frequency

    Args:
        spylinks (list): list of builds which needs to be checked.
        zone (list): List of the zones/leases that need to checked.
        tc_name (list): list of testcase name.

    Returns:
        dict: Dict with testcase as key and its frequency as value

    """
    frequency = {}
    for spylink in spylinks:
        job_type,_ = job_classifier(spylink)
        lease,_ = get_quota_and_nightly(spylink)
        if zone is not None and lease not in zone :
            continue
        cluster_status=cluster_deploy_status(spylink)
        if cluster_status == 'SUCCESS':
            tc_failures,_ = get_all_failed_tc(spylink,job_type)
            for _,value in tc_failures.items():
                if len(value) !=0:
                    for tc in value:
                        if tc in frequency:
                            frequency[tc]+= 1
                        else:
                            frequency[tc] = 1
    sorted_frequency = dict(sorted(frequency.items(),key = lambda item: item[1], reverse=True))
    frequency = {}
    if tc_name is not None:
        for tc in tc_name:
            if tc in sorted_frequency:
                frequency[tc] = sorted_frequency[tc]
        return frequency

    return sorted_frequency

def get_failed_e2e_testcases(spy_link,job_type):

    '''
    Gets failed testcases from conformance testsuite.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.
        job_type (string):  Keyword used to construct url to access logs of a job.

    Returns:
        list(dict): List of failed conformance testcases.
    '''

    if "mce" in spy_link:
        test_type = "conformance-tests"
    else:
        test_type = "openshift-e2e-libvirt-test"
    test_log_junit_dir_url = PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/" + test_type + "/artifacts/junit/"
    try:
        response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

        if response.status_code == 200:
            test_failure_summary_filename_re = re.compile('(test-failures-summary_2[^.]*\.json)')
            test_failure_summary_filename_match = test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
            if test_failure_summary_filename_match is not None:
                test_failure_summary_filename_str = test_failure_summary_filename_match.group(1)
                test_log_url=PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/"+ test_type +"/artifacts/junit/" + test_failure_summary_filename_str
                response_2 = requests.get(test_log_url,verify=False, timeout=15)
                if response_2.status_code == 200:
                    data = response_2.json()
                    e2e_failure_list = data['Tests']
                    return e2e_failure_list
                else:
                    return "Failed to get response from e2e-test log file url!"
            else:
                return "Test summary file not found"
        else:
            return "Failed to get response from e2e-test directory url" 
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        return "Failed to parse the data from e2e-test log file!"

def get_junit_symptom_detection_testcase_failures(spy_link,job_type):

    '''
    Gets failed symptom detection testcases.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.
        job_type (string):  Keyword used to construct url to access logs of a job.

    Returns:
        list(string): List of failed symptom detection testcases.
    '''

    if "power" in spy_link:
        job_type=job_type+"/gather-extra"
    elif "libvirt" in spy_link:
        job_type=job_type+"/gather-libvirt"

    test_log_junit_dir_url = PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/artifacts/junit/junit_symptoms.xml"
    symptom_detection_failed_testcase = []
    try:
        response = requests.get(test_log_junit_dir_url,verify=False,timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for testcase in root.findall('.//testcase'):
                testcase_name = testcase.get('name')
                if testcase.find('failure') is not None:
                    symptom_detection_failed_testcase.append(testcase_name)
            return symptom_detection_failed_testcase
        else:
            return 'Error fetching junit symptom detection test results'
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    except ET.ParseError as e:
        return "Failed to parse junit e2e log file!"


def get_all_failed_tc(spylink,jobtype):

    '''
    Gets all failed testcases from diffrent test suites and store in a single variable.

    Parameter:
        spylink (string):  SpyglassLink used to generate url to access logs of a job.
        jobtype (string):  Keyword used to construct url to access logs of a job.

    Returns:
        dict: Dictionary of failed testcases of all testsuites.
        int: Count of total failed testcases
    '''

    conformance_failed_tc_count=0
    monitor_failed_tc_count=0
    symptom_failed_tc_count=0

    conformance_tc_failures = get_failed_e2e_testcases(spylink,jobtype)
    conformance=[]
    if isinstance(conformance_tc_failures,list):
        conformance_failed_tc_count = len(conformance_tc_failures)
        for tc in conformance_tc_failures:
            conformance.append(tc["Test"]["Name"])
    elif isinstance(conformance_tc_failures,str):
        conformance_failed_tc_count = -5000
        conformance=[conformance_tc_failures]

    symptom_detection_tc_failures = get_junit_symptom_detection_testcase_failures(spylink,jobtype)
    symptom_detection=[]
    if isinstance(symptom_detection_tc_failures,list):
        symptom_failed_tc_count = len(symptom_detection_tc_failures)
        symptom_detection = symptom_detection_tc_failures
    elif isinstance(symptom_detection_tc_failures,str):    
        symptom_failed_tc_count = -5000
        symptom_detection=[symptom_detection_tc_failures]

    failed_tc = {"conformance": conformance, "symptom_detection": symptom_detection}

    if "4.15" in spylink:
        monitor_tc_failures = get_failed_monitor_testcases(spylink,jobtype)
        monitor=[]
        if isinstance(monitor_tc_failures,list):
            monitor_failed_tc_count = len(monitor_tc_failures)
            for tc in monitor_tc_failures:
                monitor.append(tc["Test"]["Name"])
        elif isinstance(monitor_tc_failures,str):
            monitor_failed_tc_count = -5000
            monitor=[monitor_tc_failures]
        failed_tc = {"conformance": conformance, "monitor": monitor, "symptom_detection": symptom_detection}
    elif "4.14" in spylink or "mce" in spylink:
        monitor=[]
        monitor_tc_failures = get_failed_monitor_testcases_from_xml(spylink,jobtype)
        if isinstance(monitor_tc_failures,list):
            monitor_failed_tc_count = len(monitor_tc_failures)
            monitor=monitor_tc_failures
        elif isinstance(monitor_tc_failures,str):
            monitor_failed_tc_count = -5000
            monitor=[monitor_tc_failures]
        failed_tc = {"conformance": conformance, "monitor": monitor, "symptom_detection": symptom_detection}
    
    failed_tc_count=conformance_failed_tc_count+symptom_failed_tc_count+monitor_failed_tc_count
    return failed_tc,failed_tc_count


def print_all_failed_tc(spylink,jobtype):

    '''
    Prints all the  failed testcases.

    Parameter:
        spylink (string):  SpyglassLink used to generate url to access logs of a job.
        jobtype (string):  Keyword used to construct url to access logs of a job.

    Returns:
        int: Count of total failed testcases
    '''

    tc_failures,failed_tc_count = get_all_failed_tc(spylink,jobtype)
    for key,value in tc_failures.items():
        if len(value) !=0:
            print(key,'testcase failures')
            for tc in value:
                print(tc)
        elif len(value) == 0:
            print('All',key,'testcases passed')
    return failed_tc_count
            

final_job_list=[]

def check_testcase_failure(spylink,job_type,testcase_name):
    """
    Check if a particular testcase is failed in the build.

    Args:
        spylink (string): Build which needs to be checked.
        job_type (string): Keyword used to construct url to access the artifacts.
        testcase_name (string): Name of the testcase.
    Return:
        return True if testcase failed in this particular build else return False.
    """
    failed_tcs,_ = get_all_failed_tc(spylink,job_type)

    for _,values in failed_tcs.items():
        if testcase_name in values:
            return True
    return False


def get_jobs_with_date(prowci_url,start_date,end_date):

    """
    Gets all the jobs/builds run in the given date range.

    Args:
        prowci_url (string): CI url used to fetch the jobs.
        start_date (string): Before date(Future)
        end_date (string): After date(Past)
    Return:
        List(string): List of spylinks of the jobs.
    """


    url = PROW_URL + prowci_url

    try:
        response = requests.get(url, verify=False, timeout=15)


        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            td_element = soup.find_all('td')
            td_element2 = str(td_element)
            next_link_pattern = r'/job[^>"]*'
            next_link_match = re.search(next_link_pattern,td_element2)
            if next_link_match != None:
                next_link = next_link_match.group()

            script_elements = soup.find_all('script')
            selected_script_element = None


            for script_element in script_elements:
                script_content = script_element.string
                if script_content:
                    if 'allBuilds' in script_content:
                        selected_script_element = script_content
                        break
        

            if selected_script_element:
                var_name = 'allBuilds'
                pattern = rf'{var_name}\s*=\s*(.*?);'

                match = re.search(pattern, selected_script_element)
            
                if match:
                    all_jobs=match.group(1)
                    all_jobs_parsed=json.loads(all_jobs)
                    for ele in all_jobs_parsed:
                        job_time=parse_job_date(ele["Started"])
                        
                        if end_date <= job_time <= start_date and ele["Result"] != "PENDING" :
                            job_log_path = ele["SpyglassLink"]
                            final_job_list.append(job_log_path)

                    if next_link_match != None:
                        next_page_spylink=next_link[35:]
                        check=get_next_page_first_build_date(next_page_spylink,end_date)
                    
                        if check == True:
                            get_jobs_with_date(next_page_spylink,start_date,end_date)
                        elif check == 'ERROR':
                            print("Error while fetching the job-links please check the UI")
                    return final_job_list
        else:
            print("Failed to get response from the prowCI link")
            return 'ERROR'
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        print("Failed to extract data from the script tag")
        return "ERROR"

 
def get_next_page_first_build_date(ci_next_page_spylink,end_date):

    """
    Checks if the date of first build run in the next page of CI is older than end_date.

    Args:
        ci_next_page_spylink (string): CI url used to fetch the jobs.
        end_date (string): After Date.
    Return:
        Boolean: Returns True if end_date is older than first build date else returns False.
    """

    ci_next_page_link = PROW_URL + ci_next_page_spylink

    try:
        response = requests.get(ci_next_page_link, verify=False, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            script_elements = soup.find_all('script')
            selected_script_element = None

            for script_element in script_elements:
                script_content = script_element.string
                if script_content:
                    if 'allBuilds' in script_content:
                        selected_script_element = script_content
                        break
        
            if selected_script_element:
                var_name = 'allBuilds'
                pattern = rf'{var_name}\s*=\s*(.*?);'

                match = re.search(pattern, selected_script_element)
                if match:
                    all_jobs=match.group(1)
                    all_jobs_parsed=json.loads(all_jobs)
                    job_date=all_jobs_parsed[0]["Started"]
                    parsed_job_date = parse_job_date(job_date)
                    if end_date <= parsed_job_date:
                        return True
                    elif end_date > parsed_job_date:
                        return False
                    
        else:
            print("Failed to get the prowCI response")
            return 'ERROR'
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        print("Failed to extract the spy-links from spylink please check the UI!")
        return "ERROR"
    
def get_brief_job_info(prow_ci_name,prow_ci_link,start_date=None,end_date=None,zone=None):

    """
    Gets brief information of all the jobs.

    Args:
        prow_ci_name: CI name
        prow_ci_link (string): CI url used to fetch the jobs
        start_date (string, optional): Before date(Future)
        end_date (string, optional): After date(Past)
        zone(string, optional): Cluster deployment zone
    Return:
        List(string): List of jobs with the brief information.
    """    
    
    if start_date is not None and end_date is not None:
        job_list = get_jobs_with_date(prow_ci_link,start_date,end_date)
    else:
        job_list = get_jobs(prow_ci_link)

    if isinstance(job_list,str):
        print(job_list)
        return 1
    summary_list = []   
    if len(job_list) == 0:
        print ("No job runs on {} ".format(prow_ci_name))

    i=0

    pattern_job_id =  r'/(\d+)'

    for job in job_list:
        match = re.search(pattern_job_id, job)
        job_id = match.group(1)
        lease, _ = get_quota_and_nightly(job)
        if zone is not None and lease not in zone :
            continue
        cluster_status=cluster_deploy_status(job)
        i=i+1
        job_dict = {}
        job_dict["Build"] = prow_ci_name
        job_dict["Prow Job ID"] = job_id
        job_dict["Install Status"] = cluster_status
        job_dict["Lease"]=lease
        if cluster_status == 'SUCCESS' and "sno" not in prow_ci_link:
            job_type,_ = job_classifier(job)
            _, e2e_test_result = get_all_failed_tc(job,job_type)
            if e2e_test_result == 0:
                job_dict["Test result"] = "PASS"   
            elif e2e_test_result > 0:
                job_dict["Test result"] = str(e2e_test_result) + " testcases failed"   
            elif e2e_test_result < 0:
                job_dict["Test result"] = "Failed to get Test summary"
        summary_list.append(job_dict)
    return summary_list

def get_detailed_job_info(prow_ci_name,prow_ci_link,start_date=None,end_date=None,zone=None):

    """
    Prints detailed information of all the jobs.

    Args:
        prow_ci_name: CI name
        prow_ci_link (string): CI url used to fetch the jobs
        start_date (string, optional): Start date(Future)
        end_date (string, optional): End date(Past)
        zone(string, optional): Cluster deployment zone
    """    

    if start_date is not None and end_date is not None:
        job_list = get_jobs_with_date(prow_ci_link,start_date,end_date)
    else:
        job_list = get_jobs(prow_ci_link)
    print("--------------------------------------------------------------------------------------------------")
    print(prow_ci_name)

    if isinstance(job_list,str):
        print(job_list)
        return 1
        

    deploy_count = 0
    e2e_count = 0
    i=0

    pattern_job_id =  r'/(\d+)'

    jobs_to_deleted = []
    for job in job_list:
        match = re.search(pattern_job_id, job)
        job_id = match.group(1)
        lease, nightly = get_quota_and_nightly(job)
        if zone is not None and lease not in zone:
            jobs_to_deleted.append(job)
            continue
        i=i+1
        print(i,".","Job ID: ",job_id)
        print("Job link: https://prow.ci.openshift.org/"+job)
        print("Nightly info-", nightly)
        cluster_status=cluster_deploy_status(job)
        if "sno" not in job:
            print("Lease Quota-", lease)    
            node_status = get_node_status(job)
            print(node_status)
        check_node_crash(job)

        if cluster_status == 'SUCCESS':
            deploy_count += 1
            if "sno" not in prow_ci_link:
                job_type,_ = job_classifier(job)
                failed_tc_count=print_all_failed_tc(job,job_type)
                if failed_tc_count==0:
                    e2e_count=e2e_count+1

        elif cluster_status == 'FAILURE':
                print("Cluster Creation Failed")
                cluster_creation_error_analysis(job)

        elif cluster_status == 'ERROR':
            print('Unable to get cluster status please check prowCI UI ')

        print("\n")
        
    job_list = list(set(job_list) - set(jobs_to_deleted))
    if len(job_list) != 0:
        print ("\n{}/{} deploys succeeded".format(deploy_count, len(job_list)))
        print ("{}/{} e2e tests succeeded".format(e2e_count, len(job_list)))
        print("--------------------------------------------------------------------------------------------------")
    else:
        print ("No job runs on {} ".format(prow_ci_name))
