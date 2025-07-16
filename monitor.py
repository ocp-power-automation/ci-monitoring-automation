import json
import re
import sys
from bs4 import BeautifulSoup
import urllib3
import requests
from datetime import datetime , timedelta
import xml.etree.ElementTree as ET
import constants

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
PROW_URL = ""
final_job_list=[]


def fetch_release_date(release):
    '''
    Returns the created date of release
    '''

    try:
        url = constants.STABLE_RELEASE_URL + release
        response = requests.get(url, verify=False, timeout=15)
        if response.status_code == 404:
            url = constants.DEV_PREVIEW_RELEASE_URL + release
            response = requests.get(url, verify=False, timeout=15)
            if response.status_code == 404:
                print(f"Failed to get the release page.  {response.text}")
                sys.exit(1)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            p_elements = soup.find_all("p")
            for p in p_elements:
                p_ele = p.string
                if p_ele:
                    if "Created:" in p_ele:
                        start_date = p_ele.split(" ")[1]+" "+p_ele.split(" ")[2]
                        break
                    else:
                        prefix, number = release.rsplit(".", 1)
                        prev_version = prefix + "." + str(int(number) - 1)
                        changelog_url = f"https://ppc64le.ocp.releases.ci.openshift.org/changelog?from={prev_version}&to={release}"
                        changelog_resp = requests.get(changelog_url, verify=False, timeout=15)
                        if changelog_resp.status_code == 200:
                            lines = changelog_resp.text.splitlines()
                            for line in lines:
                                if "Created:" in line:
                                    start_date = line.split(" ")[1]+" "+line.split(" ")[2]
                                    return start_date
                    
            return start_date
        else: 
            print(f"Failed to get the release page.  {response.text}")
            sys.exit(1)
    except requests.Timeout as e:
        return "Request timed out"
    except requests.RequestException as e:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        return "Failed to extract the spy-links"
    
def fetch_build_time(url):
    '''
    Returns the created time (HH:MM) and date (YYYY-MM-DD) of the release in IST
    '''
    response = requests.get(url, verify=False, timeout=15)
    response.raise_for_status()
    buildtime = json.loads(response.text)
    timestamp_str = buildtime["metadata"]["creationTimestamp"]    
    # Convert timestamp to datetime object (UTC)
    utc_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
    # Convert UTC to IST (UTC +5:30)
    ist_time = utc_time + timedelta(hours=5, minutes=30)    
    ist_date = ist_time.strftime("%Y-%m-%d")  # YYYY-MM-DD
    ist_time_formatted = ist_time.strftime("%H:%M")  # HH:MM (without seconds)
    timestamp=ist_date+" "+ist_time_formatted 
    return timestamp

def set_prow_url(ci_job_type: str)->str:
    '''
    Returns PROW_URL value based on command line argument job_type

    Parameter:
        ci_job_type(string): value of command line argument job_type
    
    Returns:
        string: Value of PROW_URL
    '''
    if ci_job_type == 'p' or ci_job_type == 'z':
        return constants.JOB_LINK_URL+"job-history/gs/origin-ci-test/logs/"
    elif ci_job_type == 'pa':
        return constants.JOB_LINK_URL+"job-history/gs/test-platform-results/logs/"

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
    return datetime.now()

def parse_job_date(date):

    '''
    Converts string to Date datatype.

    Parameter:
        date: string.

    Returns:
        Date
    '''
    
    parse_date=datetime.strptime(date,"%Y-%m-%dT%H:%M:%SZ")
    return parse_date


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
                    current_date=get_current_date().date()
                    jobs_run_today = []
                    for ele in all_jobs_parsed:
                        job_time=parse_job_date(ele["Started"]).date()
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


def check_job_status(spy_link):
    '''
    Gets the status of the job if it was a success or failure
    
    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.

    Returns:
        string: Job run Status 
    '''
    job_status_url = constants.PROW_VIEW_URL + spy_link[8:] + '/finished.json'
    try:
        response = requests.get(job_status_url, verify=False, timeout=15)
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
        return 'Error while parsing finished.json'

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
        mce_install_log_url = constants.PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/hypershift-mce-install/finished.json'

        try:
            response = requests.get(mce_install_log_url, verify=False, timeout=15)
            if response.status_code == 200:                
                cluster_status = json.loads(response.text)
                cluster_result = "MCE-INSTALL "+ cluster_status["result"]
                if cluster_status["result"] == "SUCCESS":
                        # check mce-power-create status also
                    mce_power_log_url = constants.PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/hypershift-mce-power-create-nodepool/finished.json'
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
        pattern=r"(\d+\.\d+)"
        match=re.search(pattern,spy_link[8:])
        version=float(match.group(0))
        if "upgrade" in spy_link:
            version=version-0.01 

        job_log_url = constants.PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/ipi-install-' + job_platform +'-install/finished.json'
        if "sno" in spy_link:
            job_log_url = constants.PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/upi-install-powervs-sno/finished.json'
        #Only 4.17 and above libvirt uses upi-installation.
        if version>=4.16 and job_platform != "powervs":
            job_log_url = constants.PROW_VIEW_URL + spy_link[8:] + '/artifacts/' + job_type + '/upi-install-' + job_platform +'/finished.json'

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
    job_log_url = constants.PROW_VIEW_URL + spylink[8:] + '/artifacts/' + job_type + '/ipi-install-' + job_platform +'-install/build-log.txt'
    
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

#This is a temporary fix to check node details for older jobs.
def check_if_gather_libvirt_dir_exists(spy_link,job_type):
    
    base_artifacts_dir_url = constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type

    try:
        response = requests.get(base_artifacts_dir_url, verify=False, timeout=15)
        gather_libvirt_dir_re = re.compile('gather-libvirt')
        gather_libvirt_dir_re_match = gather_libvirt_dir_re.search(response.text, re.MULTILINE|re.DOTALL)
        
        if gather_libvirt_dir_re_match is not None:
            return True
        else:
            return False
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    
#This is to check for hypervisor error
def check_hypervisor_error(spy_link):
    build_log_url = constants.PROW_VIEW_URL + spy_link[8:] + '/build-log.txt'
    try:
        response = requests.get(build_log_url, verify=False, timeout=15)
        hypervisor_re = re.compile(constants.HYPERVISOR_CONNECTION_ERROR)
        hypervisor_re_match = hypervisor_re.search(response.text)
        if hypervisor_re_match is not None:
            return True
        else:
            return False
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"


#This is a fix to check for sensitive information expose error.
def check_if_sensitive_info_exposed(spy_link):
    
    build_log_url = constants.PROW_VIEW_URL + spy_link[8:] + '/build-log.txt'
    try:
        response = requests.get(build_log_url, verify=False, timeout=15)
        senstive_info_re = re.compile('This file contained potentially sensitive information and has been removed.')
        senstive_info_re_match = senstive_info_re.search(response.text)
        if senstive_info_re_match is not None:
            return True
        else:
            return False
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
    
    check_for_gather_libvirt_dir = check_if_gather_libvirt_dir_exists(spy_link,job_type)
    
    if check_for_gather_libvirt_dir == True:
        job_type += "/gather-libvirt"
    else:
        job_type += "/gather-extra"
    
    node_log_url = constants.PROW_VIEW_URL + spy_link[8:] + \
        "/artifacts/" + job_type +"/artifacts/oc_cmds/nodes"
    
    pattern=r"(\d+\.\d+)"
    match=re.search(pattern,spy_link[8:])
    version=float(match.group(1))
    if "upgrade" in spy_link:
        version=version-0.01
    
 
    try:
        node_log_response = requests.get(node_log_url, verify=False, timeout=15)
        if "NAME" in node_log_response.text:
            if version > 4.15 and job_platform == "libvirt":
                workers="compute-"   
            else:
                workers="worker-"
    
            response_str=node_log_response.text
            if "NotReady" in response_str:
                return "Some Nodes are in NotReady state"
            elif response_str.count("control-plane,master") != 3:
                return "Not all master nodes are up and running"
            elif ((job_platform == "mce" or "compact" in node_log_url ) and response_str.count("worker") != 3) or ((job_platform != "mce" and "compact" not in node_log_url) and response_str.count(workers) != 2):
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
        crash_log_url = constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" +job_type + "/ipi-conf-debug-kdump-gather-logs/artifacts/"
        
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

def get_lease(build_log_response,job_platform):

    '''
    Gets lease/region where cluster is deployed.
    parameter:
       build_log_response: build log response.
       job_platform(string):The infrastructure where the cluster is deployed.
    Returns:
        lease(string): Acquired lease/region
    '''

    lease = ""
    zone_log_re = re.compile('(Acquired 1 lease\(s\) for {}-quota-slice: \[)([^]]+)(\])'.format(job_platform), re.MULTILINE|re.DOTALL)
    zone_log_match = zone_log_re.search(build_log_response.text)
    if zone_log_match is None:
        lease = "Failed to fetch lease information"
    else:
        lease = zone_log_match.group(2)
    return lease

def get_nightly(build_log_url,build_log_response, job_platform):

    '''
    Gets nightly image used.
    parameter:
       build_log_url(string): link to access the logs of the job.
       build_log_response: build log response.
       job_platform(string): Architecture (ppc64le or s390x or multi).
    Returns:
        string : Nightly image used.
    '''
    phases = ["initial", "latest"] if "upgrade" in build_log_url else ["latest"]
    results = []

    for phase in phases:
        patterns = [
            rf"Resolved release {job_platform}-{phase} to (\S+)",
            rf"Using explicitly provided pull-spec for release {job_platform}-{phase} \((\S+)\)"] if job_platform != "multi" else[
            rf"Resolved release {phase} to (\S+)",
            rf"Using explicitly provided pull-spec for release {phase} \((\S+)\)"
        ]

        found = False
        for pattern in patterns:
            match = re.search(pattern, build_log_response.text, re.MULTILINE | re.DOTALL)
            if match:
                results.append(match.group(1))
                found = True
                break

        if not found:
            results.append(f"Unable to fetch nightly {job_platform}-{phase} information - No match found")

    return "\n".join(results)

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
    build_log_url = constants.PROW_VIEW_URL + spy_link[8:] + "/build-log.txt"
    try:
        build_log_response = requests.get(build_log_url, verify=False, timeout=15)
        if 'ppc64le' in spy_link:      
            if job_platform == "libvirt":
                job_platform+="-ppc64le-s2s"
            elif job_platform == "powervs":
                job_platform+="-[1-9]"
            lease = get_lease(build_log_response,job_platform)
            nightly = get_nightly(build_log_url,build_log_response, 'ppc64le')

        elif 's390x' in spy_link:     
            job_platform+="-s390x"
            lease = get_lease(build_log_response,job_platform )
            nightly = get_nightly(build_log_url,build_log_response, 's390x')
        elif "multi" in spy_link:
            if "powervs" in spy_link:
                job_platform = "powervs"
                job_platform+="-[1-9]"
                lease=get_lease(build_log_response,job_platform)
            else:
                job_platform="multi"
                lease=get_lease(build_log_response,'libvirt-ppc64le-s2s')
            nightly = get_nightly(build_log_url,build_log_response, "multi") 

        elif "mce" in spy_link:
            job_platform = "aws"
            lease = get_lease(build_log_response,job_platform )
            nightly = get_nightly(build_log_url,build_log_response, "multi")
        else:
            # lease is not applicable for SNO
            nightly = get_nightly(build_log_url,build_log_response, "multi")    
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
    #Artifact link for libvirt: test-platform-results/logs/periodic-ci-openshift-multiarch-master-nightly-4.17-ocp-e2e-ovn-remote-libvirt-ppc64le/1847061335720857600/artifacts/ocp-e2e-ovn-remote-libvirt-ppc64le/
    #Artifact link for powervs: test-platform-results/logs/periodic-ci-openshift-multiarch-master-nightly-4.17-ocp-e2e-ovn-ppc64le-powervs-capi/1820746900182142976/artifacts/ocp-e2e-ovn-ppc64le-powervs-capi/
    #Artifact link for upgrade: test-platform-results/logs/periodic-ci-openshift-multiarch-master-nightly-4.17-upgrade-from-nightly-4.16-ocp-ovn-remote-libvirt-multi-p-p/1846295088968241152/artifacts/ocp-ovn-remote-libvirt-multi-p-p/
    #Artifact link for heavybuild: test-platform-results/logs/periodic-ci-openshift-multiarch-master-nightly-4.16-ocp-heavy-build-ovn-remote-libvirt-ppc64le/1846642613847855104/artifacts/ocp-heavy-build-ovn-remote-libvirt-ppc64le/
    #Artifact directory for all libvirt,powervs,heavybuild and upgrade jobs starts with "ocp", so to identify the job_type used the regex 'ocp.*?/'
    pattern = r'ocp.*?/'

    #Artifact link for mce /test-platform-results/logs/periodic-ci-openshift-hypershift-release-4.14-periodics-mce-e2e-mce-power-conformance/1847155042210025472/artifacts/e2e-mce-power-conformance/
    #mce jobs artifact directory is e2e-mce-power-conformance, so to identify the job_type used the regex 'e2e.*?/'
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
        list: List of failed monitor testcases.
        str: Message if any error occured.
    '''

    monitor_tc_failures = []
    test_log_junit_dir_url = constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/"

    try:
        response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

        if response.status_code == 200:
            monitor_test_failure_summary_filename_re = re.compile('(test-failures-summary_monitor_2[^.]*\.json)')
            monitor_test_failure_summary_filename_match = monitor_test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
            if monitor_test_failure_summary_filename_match is not None:
                monitor_test_failure_summary_filename_str = monitor_test_failure_summary_filename_match.group(1)
                test_log_url=constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/openshift-e2e-libvirt-test/artifacts/junit/" + monitor_test_failure_summary_filename_str
                response_2 = requests.get(test_log_url,verify=False, timeout=15)
                if response_2.status_code == 200:
                    data = response_2.json()
                    for tc in data['Tests']:
                        monitor_tc_failures.append(tc["Test"]["Name"])
                    return monitor_tc_failures, None
                else:
                    return monitor_tc_failures, "Failed to get response from e2e-test log file url!"
            else:
                return monitor_tc_failures, "Test summary file not found"
        else:
            return monitor_tc_failures, "Failed to get response from e2e-test directory url"
    except requests.Timeout:
        return monitor_tc_failures, "Request timed out"
    except requests.RequestException:
        return monitor_tc_failures, "Error while sending request to url"
    except json.JSONDecodeError as e:
        return monitor_tc_failures, "Failed to parse the data from e2e-test log file!"


def get_failed_monitor_testcases_from_xml(spy_link,job_type):

    '''
    Gets failed monitor testcases from conformance testsuite.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.
        job_type (string):  Keyword used to construct url to access logs of a job.

    Returns:
        list: List of failed monitor testcases.
        str: Message if any error occured.
    '''

    monitor_failed_testcase=[]
    if "mce" in spy_link:
        test_type = "conformance-tests"
    else:
        test_type = "openshift-e2e-libvirt-test"
    test_log_junit_dir_url = constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/" + test_type + "/artifacts/junit/"
    try:
        response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

        if response.status_code == 200:
            test_failure_summary_filename_re = re.compile('(e2e-monitor-tests__2[^.]*\.xml)')
            test_failure_summary_filename_match = test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
            if test_failure_summary_filename_match is not None:
                test_failure_summary_filename_str = test_failure_summary_filename_match.group(1)
                test_log_url=constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/"+ test_type +"/artifacts/junit/" + test_failure_summary_filename_str
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
                    return monitor_failed_testcase, None
            else:
                return monitor_failed_testcase, "Monitor test file not found"
        else:
            return monitor_failed_testcase, "Failed to get response from e2e-test directory url" 
    except requests.Timeout:
        return monitor_failed_testcase, "Request timed out"
    except requests.RequestException:
        return monitor_failed_testcase, "Error while sending request to url"
    except ET.ParseError as e:
        return monitor_failed_testcase, "Failed to parse junit e2e log file!"


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
            tc_failures,_,_ = get_all_failed_tc(spylink,job_type)
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
        list: List of failed conformance testcases.
        str: Message if any error occured. 

    '''

    conformance_tc_failures=[]
    if "mce" in spy_link:
        test_type = "conformance-tests"
    else:
        test_type = "openshift-e2e-libvirt-test"
    test_log_junit_dir_url = constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/" + test_type + "/artifacts/junit/"
    try:
        response = requests.get(test_log_junit_dir_url, verify=False, timeout=15)

        if response.status_code == 200:
            test_failure_summary_filename_re = re.compile('(test-failures-summary_2[^.]*\.json)')
            test_failure_summary_filename_match = test_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
        
            if test_failure_summary_filename_match is not None:
                test_failure_summary_filename_str = test_failure_summary_filename_match.group(1)
                test_log_url=constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/"+ test_type +"/artifacts/junit/" + test_failure_summary_filename_str
                response_2 = requests.get(test_log_url,verify=False, timeout=15)
                if response_2.status_code == 200:
                    data = response_2.json()
                    for tc in data['Tests']:
                        conformance_tc_failures.append(tc["Test"]["Name"])
                    return conformance_tc_failures, None
                else:
                    return conformance_tc_failures, "Failed to get response from e2e-test log file url!"
            else:
                return conformance_tc_failures, "Test summary file not found"
        else:
            return conformance_tc_failures, "Failed to get response from e2e-test directory url" 
    except requests.Timeout:
        return conformance_tc_failures, "Request timed out"
    except requests.RequestException:
        return conformance_tc_failures, "Error while sending request to url"
    except json.JSONDecodeError as e:
        return conformance_tc_failures, "Failed to parse the data from e2e-test log file!"


def get_junit_symptom_detection_testcase_failures(spy_link,job_type):

    '''
    Gets failed symptom detection testcases.

    Parameter:
        spy_link (string):  SpyglassLink used to generate url to access logs of a job.
        job_type (string):  Keyword used to construct url to access logs of a job.

    Returns:
        list: List of failed symptom detection testcases.
        str: Message if any error occured.
    '''

    symptom_detection_failed_testcase = []

    check_for_gather_libvirt_dir = check_if_gather_libvirt_dir_exists(spy_link,job_type)
    
    if check_for_gather_libvirt_dir == True:
        job_type += "/gather-libvirt"
    else:
        job_type += "/gather-extra"

    test_log_junit_dir_url = constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/artifacts/junit/"
    symptom_detection_failed_testcase = []
    try:
        response = requests.get(test_log_junit_dir_url,verify=False,timeout=15)
        if response.status_code == 200:
            junit_failure_summary_filename_re = re.compile('junit_symptoms.xml')
            junit_failure_summary_filename_match = junit_failure_summary_filename_re.search(response.text, re.MULTILINE|re.DOTALL)
            if junit_failure_summary_filename_match is not None:
                test_log_junit_url = constants.PROW_VIEW_URL + spy_link[8:] + "/artifacts/" + job_type + "/artifacts/junit/junit_symptoms.xml"
                response_2 = requests.get(test_log_junit_url,verify=False,timeout=15)
                root = ET.fromstring(response_2.content)
                for testcase in root.findall('.//testcase'):
                    testcase_name = testcase.get('name')
                    if testcase.find('failure') is not None:
                        symptom_detection_failed_testcase.append(testcase_name)
                return symptom_detection_failed_testcase, None
            else:
                return symptom_detection_failed_testcase, "Junit test summary file not found"
        else:
            return symptom_detection_failed_testcase, 'Error fetching junit symptom detection test results'
    except requests.Timeout:
        return symptom_detection_failed_testcase, "Request timed out"
    except requests.RequestException:
        return symptom_detection_failed_testcase, "Error while sending request to url"
    except ET.ParseError as e:
        return symptom_detection_failed_testcase, "Failed to parse symptom detection e2e log file!"


def get_all_failed_tc(spylink,jobtype):

    '''
    Gets all failed testcases from diffrent test suites and store in a single variable.

    Parameter:
        spylink (string):  SpyglassLink used to generate url to access logs of a job.
        jobtype (string):  Keyword used to construct url to access logs of a job.

    Returns:
        dict: Dictionary of failed testcases of all testsuites.
        dict: Error messages encountered while getting test summary files.
        int: Count of total failed testcases
    '''
    conformance_failed_tc_count = 0
    monitor_failed_tc_count = 0
    symptom_failed_tc_count = 0
    failed_tc_count = 0
    monitor_err_obj = None
    error_object = {}
    conformance, conformance_error_obj = get_failed_e2e_testcases(spylink,jobtype)

    symptom_detection, symptom_error_obj = get_junit_symptom_detection_testcase_failures(spylink,jobtype)

    failed_tc = {"conformance": conformance, "symptom_detection": symptom_detection}

    conformance_failed_tc_count = len(failed_tc["conformance"])
    symptom_failed_tc_count = len(failed_tc["symptom_detection"])

    #  Monitor test failure details are fetched from the "junit_e2e__*.xml" file for 4.14,4.13 and mce job runs.
    #  For other job runs monitor test failure details are fetched from "test-failures-summary_monitor_*.json" file.
    if ("4.14" not in spylink and  "4.13" not in spylink) and (not "mce" in spylink):
        monitor, monitor_err_obj=get_failed_monitor_testcases(spylink,jobtype)
        failed_tc = {"conformance": conformance, "monitor": monitor, "symptom_detection": symptom_detection}
        monitor_failed_tc_count = len(failed_tc["monitor"])
    elif "4.14" in spylink or "mce" in spylink or "4.13" in spylink:
        monitor, monitor_err_obj = get_failed_monitor_testcases_from_xml(spylink,jobtype)
        failed_tc = {"conformance": conformance, "monitor": monitor, "symptom_detection": symptom_detection}
        monitor_failed_tc_count = len(failed_tc["monitor"])

    failed_tc_count=conformance_failed_tc_count+symptom_failed_tc_count+monitor_failed_tc_count
    error_object = {"conformance": conformance_error_obj, "monitor": monitor_err_obj, "symptom_detection": symptom_error_obj}

    return failed_tc,failed_tc_count,error_object

def check_ts_exe_status(spylink,jobtype):

    '''
    Checks conformance Test suite execution status.

    Parameter:
        spylink (string):  SpyglassLink used to generate url to access logs of a job.
        jobtype (string):  Keyword used to construct url to access logs of a job.

    Returns:
        str: Status of test suite execution
    '''

    if "mce" in spylink:
        test_type = "conformance-tests"
    else:
        test_type = "openshift-e2e-libvirt-test"
    test_exe_status_url = constants.PROW_VIEW_URL + spylink[8:] + "/artifacts/" + jobtype + "/" + test_type + "/finished.json"
    try:
        response = requests.get(test_exe_status_url, verify=False, timeout=15)
        if response.status_code == 200:
            cluster_status = json.loads(response.text)
            return cluster_status["result"]
        else:
            return "Error"
    except requests.Timeout:
        return "Request timed out"
    except requests.RequestException:
        return "Error while sending request to url"
    except json.JSONDecodeError as e:
        return 'ERROR'


def print_all_failed_tc(spylink,jobtype):

    '''
    Prints all the  failed testcases.

    Parameter:
        spylink (string):  SpyglassLink used to generate url to access logs of a job.
        jobtype (string):  Keyword used to construct url to access logs of a job.

    Returns:
        str: Status of test suite execution
    '''

    test_exe_status = check_ts_exe_status(spylink,jobtype)

    if test_exe_status == "FAILURE":
        tc_failures, fail_count, error_object = get_all_failed_tc(spylink,jobtype)
        if 0 < fail_count <= 5:
            for key,value in tc_failures.items():
                i = 1
                if len(value) > 0:
                    print('Failed',key,'testcases: ')
                    for tc in value:
                        print(str(i)+'.',tc)
                        i=i+1
                elif len(value) == 0:
                    print('All',key,'testcases passed')
        elif fail_count > 5:
            print(fail_count,"testcases have failed, please refer to the job link for more information")

        if error_object:
            for key,value in error_object.items():
                if value:
                    print(key,'test suite error message: ')
                    print(value)
        return "FAILURE"
    
    elif test_exe_status == "SUCCESS":
        sym,sym_error_object = get_junit_symptom_detection_testcase_failures(spylink,jobtype)
        if not sym_error_object:
            symcount = len(sym)
            if symcount > 0:
                print("Symptom Detection Test failures:")
                for i in sym:
                    print(i)
                return "FAILURE"
            elif symcount == 0:
                print("All the Testcases have passed")
                return "SUCCESS"
        else:
            print(sym_error_object)
            return "FAILURE"
    elif test_exe_status == "ABORTED":
        sym,sym_error_object = get_junit_symptom_detection_testcase_failures(spylink,jobtype)
        if not sym_error_object:
            symcount = len(sym)
            if symcount > 0:
                print("Symptom Detection Test failures:")
                for i in sym:
                    print(i)
        else:
            print(sym_error_object)
        
        print("Test suite execution has been aborted")
        return "ABORTED"
    else:
        print("ERROR")
        return "ERROR"
        

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
    failed_tcs,_,_ = get_all_failed_tc(spylink,job_type)

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
            next_link = ''
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

                    #build match extracts the next page spylink
                    build_regex = r"/([^/?]+)\?.+"
                    build_match = re.search(build_regex,next_link)
                    if build_match != None:
                        next_page_spylink=build_match.group()
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
    
def get_brief_job_info(build_list,prow_ci_name,zone=None):

    """
    Gets brief information of all the jobs

    Args:
        build_list: list of builds
        prow_ci_name: CI name
        zone(string, optional): Cluster deployment zone
    Return:
        List(string): List of jobs with the brief information.
    """    
    
    if isinstance(build_list,str):
        print(build_list)
        return []
    summary_list = []   
    
    i=0

    pattern_build_id =  r'/(\d+)'

    for build in build_list:
        match = re.search(pattern_build_id, build)
        build_id = match.group(1)
        try:
            url = constants.PROW_VIEW_URL + build[8:] + '/prowjob.json'
            time=fetch_build_time(url)
        except:
            time=None
        lease, _ = get_quota_and_nightly(build)
        if zone is not None and lease not in zone :
            continue
        build_status = check_job_status(build)
        cluster_status=cluster_deploy_status(build)
        sensitive_info_expose_status=check_if_sensitive_info_exposed(build)
        i=i+1
        job_dict = {}
        job_dict["Job"] = prow_ci_name
        job_dict["Prow Build ID"] = build_id
        if time:
            job_dict["Time"]=time[11:]
        else:
            job_dict["Time"]="Failed to fetch time"
        job_dict["Install Status"] = cluster_status
        if sensitive_info_expose_status == True:
            job_dict["Lease"]="Build log removed"
        else:
            job_dict["Lease"]=lease
        if build_status == 'SUCCESS' and "sno" not in prow_ci_name:
            job_dict["Test result"] = "PASS"
        elif build_status == 'FAILURE' and "sno" not in prow_ci_name:
            if cluster_status == 'SUCCESS':
                job_type,_ = job_classifier(build)
                _, e2e_fail_test_count, error_object = get_all_failed_tc(build,job_type)
                if all(value == None for value in error_object.values()):
                    if e2e_fail_test_count == 0:
                        job_dict["Test result"] = "PASS"   
                    elif e2e_fail_test_count > 0:
                        job_dict["Test result"] = str(e2e_fail_test_count) + " testcases failed"   
                else:
                    job_dict["Test result"] = "Failed to get Test summary"
            else:
                hypervisor_error_status = check_hypervisor_error(build)
                if hypervisor_error_status:
                    job_dict["Test result"] = constants.HYPERVISOR_CONNECTION_ERROR
        summary_list.append(job_dict)
    return summary_list

def get_detailed_job_info(build_list,prow_ci_name,zone=None):

    """
    Prints detailed information of all the jobs.

    Args:
        build_list: list of builds
        prow_ci_name: CI name
        zone(string, optional): Cluster deployment zone
    """    

    if isinstance(build_list,str):
        print(build_list)
        return 1
    
    if len(build_list) > 0: 
        print("--------------------------------------------------------------------------------------------------")
        print(prow_ci_name)
        
    deploy_count = 0
    e2e_count = 0
    i=0

    builds_to_deleted = []
    for build in build_list:
        lease, nightly = get_quota_and_nightly(build)
        if zone is not None and lease not in zone:
            builds_to_deleted.append(build)
            continue
        i=i+1
        print(i,"Job link:"+constants.JOB_LINK_URL+build)
        try:
            url = constants.PROW_VIEW_URL + build[8:] + '/prowjob.json'
            time=fetch_build_time(url)
            print("Build start time:", time)
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            print("Error fetching build time:", e)
        build_status = check_job_status(build)
        sensitive_info_expose_status=check_if_sensitive_info_exposed(build)
        
        if sensitive_info_expose_status == True:
            print("*********************************")
            print("Build log removed")
            print("*********************************")

        print("Nightly info-", nightly)
        
        if build_status == 'SUCCESS':
            deploy_count += 1
            e2e_count=e2e_count+1
            if "sno" not in build:
                print("Lease Quota-", lease)
            check_node_crash(build)
            print("Build Passed")
        elif build_status == 'FAILURE':
            cluster_status=cluster_deploy_status(build)
            if "sno" not in build:
                print("Lease Quota-", lease)    
                node_status = get_node_status(build)
                print(node_status)
            hypervisor_error_status = check_hypervisor_error(build)
            if hypervisor_error_status:
                print("Cluster Creation Failed."+constants.HYPERVISOR_CONNECTION_ERROR)
            else :
                check_node_crash(build)

            if cluster_status == 'SUCCESS':
                deploy_count += 1
                if "sno" not in prow_ci_name:
                    job_type,_ = job_classifier(build)
                    tc_exe_status=print_all_failed_tc(build,job_type)
                    if tc_exe_status=="SUCCESS":
                        e2e_count=e2e_count+1

            elif cluster_status == 'FAILURE':
                print("Cluster Creation Failed")
                

            elif cluster_status == 'ERROR' and not hypervisor_error_status :
                print('Unable to get cluster status please check prowCI UI ')
        else:
            print(build_status)

        print("\n")
        
    build_list = list(set(build_list) - set(builds_to_deleted))
    if len(build_list) != 0:
        print ("\n{}/{} deploys succeeded".format(deploy_count, len(build_list)))
        print ("{}/{} e2e tests succeeded".format(e2e_count, len(build_list)))
        print("--------------------------------------------------------------------------------------------------")
