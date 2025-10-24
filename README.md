# CI-Monitoring-Automation



### Overview

The ci-monitoring-automation Repository is a collection of Python scripts designed to automate monitoring of Continuous Integration (CI) system workflows. These scripts facilitate the retrieval and analysis of information related to coreOS CI builds, offering developers the flexibility to gather data of builds run for the current day or within a specified date range.


### Prerequisites

```
Python3
pip
```


### Installation

```
git clone https://github.com/ocp-power-automation/ci-monitoring-automation.git
cd ci-monitoring-automation
Create a virtualenv if required and install required packages using "pip install -r requirements.txt"
```

### Config files

1. **p_periodic.json:** The p_periodic.json file will have ci name and ci links of ppc64le architecture periodic jobs in the key value pair where value of ci link will be prow periodic job name.The new CI's can be easily integrated by adding the ci name and ci link in the config.json file.


2. **z_periodic.json:** The z_periodic.json file will have ci name and ci links of s390x architecture periodic jobs in the key value pair where value of ci link will be prow periodic job name.The new CI's can be easily integrated by adding the ci name and ci link in the config.json file.

3. **p_auxillary.json:** The p_auxillary.json file will have ci name and ci links of ppc64le architecture auxilliary jobs in the key value pair where value of ci link will be prow ecosystem, jenkins, fips serial and compact job name.The new CI's can be easily integrated by adding the ci name and ci link in the p_auxillary.json file.
 

### Usage

1. **CI_DailyBuildUpdate.py:** The CI_DailyBuildUpdates.py script will fetch and display information of the all builds that ran on the CI system for the current day.  

    1. Brief Information: The CI_DailyBuildUpdates.py script when invoked with command line argument info_type as "brief" it will display Build type, job id, cluster deployment status, Lease and total number of failed testcases.

        ```python3 CI_DailyBuildUpdates.py --info_type brief```
        
    2. The CI_DailyBuildUpdates.py script when invoked with command line arguments info_type as "brief" and zone, it will display the builds details in the provided zone.
        
        ```python3 CI_DailyBuildUpdates.py --info_type brief --zone syd04```

    3. Detailed Information: The CI_DailyBuildUpdates.py script when invoked with command line argument info_type as "detailed" it will display the Job id, job link, cluster deployment error message if it occured, Nightly image used, Node status, Checks for Node crash and lists all the failed testcases.  

        ```python3 CI_DailyBuildUpdates.py --info_type detailed```

    4. The CI_DailyBuildUpdates.py script when invoked with command line arguments info_type as "detailed" and zone, it will display the builds details in the provided zone.

        ```python3 CI_DailyBuildUpdates.py --info_type detailed --zone syd04```
    
    5. The CI_DailyBuildUpdates.py script when invoked with command line arguments info_type as "detailed" and --job_type as "pa", it will display the builds details in the given job type.

        Supported value [p','z','pa'] 

        pa - ppc64le architecture auxilliary jobs

        p - ppc64le architecture periodic jobs
        
        z - s390x architecture periodic jobs
         
         ```python3 CI_DailyBuildUpdates.py --info_type detailed --job_type pa```



2. **CI_JobHistory.py:** The CI_JobHistory.py is a script which allows user to query a specific information from all builds that ran on the CI system within a given date range.  
    
    ```python3 CI_JobHistory.py```

    ```python3 CI_Jobhistory.py --zone ```     This command line allows user to fetch query based on zone type.

    ```python3 CI_Jobhistory.py --job_type ``` This command line allows user to fetch query based on job type.
             
    ```python3 CI_Jobhistory.py --filter ```   This command line allows user to fetch query based on search filter.
        Specify the filter string to fetch jobs (Example 'heavy build' / libvirt / powervs / upgrade /multi / 4.14 / 4.15 / 4.16 / 4.17/ 4.18 )'



    1. Interactive Execution: The CI_JobHistory.py can be executed in a interactive mode by setting JENKINS variable as False in config.ini file.

    2. Non-Interactive Execution: The CI_JobHistory.py can be executed in a non-interactive mode by setting JENKINS variable as True in config.ini file, along with the JENKINS variable user needs to provide values for the following variables:
        ```
        selected_ci: CI's from where to fetch the jobs.
        query_option: Query code to fetch information from builds.
            •	Check Node Crash: Detects if a node crashed during execution.
	        •	Brief Job Information: Provides a summary of job execution.
	        •	Detailed Job Information: Provides in-depth details of jobs based on job_filter.
                job_filter: 'all' (default), 'success', or 'failure'
                - 'success' → show only cluster installs that succeeded
                - 'failure' → show only cluster installs that failed or errored
	        •	Failed Test Cases: Provides a list of test cases that are failed in the CI run.
	        •	Get Builds with Test Case Failures: Identifies builds where given test cases failed.
	        •	Test Case Failure Frequency: Analyzes how often test cases fail.
	        •	Get Build Based on Release: Retrieves builds corresponding to a specific release
                    release: release that needs to be checked
                    next release: next release or latest                    
        before_date: End date.
        after_date: Start date.
        tc_name: Testcase name which will be used in quering the failure frequency.
        ```


3. **tracker.py:** The tracker.py script helps user to get the testcases failing at a high frequency in the latest run CI builds. This script accepts the following command line arguments:

    ```python3 tracker.py --builds 10 --frequency 3```

    1. builds: This argument accepts int value, which will query for failed testcases in "n" latest build run in the CI, default value set is 10.
    2. frequency: This argument accepts int value, which specifies the frequency threshold and report the testcases which are failing above the frequency, default value set is 3.


4. **aggregate.py:** The aggregate.py script gets detailed information of all the builds which have run using the provided nightly image. 

    ```python3 aggregate.py``` This script requires the following input

    1. selected_ci: Jobs from where to fetch the builds.
    2. nightly: Name of the Release image.
