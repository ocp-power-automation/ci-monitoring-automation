# monitor_compat.py
"""
Compatibility wrapper for the monitor module that raises exceptions.
This wrapper converts exceptions into legacy string/tuple return values so older
callers don't need to be changed.
"""

from typing import Tuple, List, Dict, Any
import monitor

PROW_URL = None
final_job_list = None

def _sync_module_attrs():
    global PROW_URL, final_job_list
    try:
        PROW_URL = monitor.PROW_URL
    except Exception:
        PROW_URL = None
    try:
        final_job_list = monitor.final_job_list
    except Exception:
        final_job_list = []

# initialize
_sync_module_attrs()

# error mapping helpers
def _err_str_from_exc(exc) -> str:
    # Map typed exceptions to legacy strings (best-effort)
    if isinstance(exc, monitor.ProwTimeoutError):
        return "Request timed out"
    if isinstance(exc, monitor.ProwFetchError):
        # many places previously used this message for network errors
        return "Error while sending request to url"
    if isinstance(exc, monitor.ProwParseError):
        # generic parse/error sentinel used in original file
        return "ERROR"
    # default fallback
    return "ERROR"

# Wrapped functions ---------------------------------------------------------

def fetch_release_date(release: str) -> str:
    try:
        return monitor.fetch_release_date(release)
    except Exception as e:
        return _err_str_from_exc(e)

def fetch_build_time(url: str) -> str:
    try:
        return monitor.fetch_build_time(url)
    except Exception as e:
        # original returned "Request timed out" or "Error while sending request to url"
        return _err_str_from_exc(e)

def set_prow_url(ci_job_type: str) -> str:
    return monitor.set_prow_url(ci_job_type)

def load_config(config_file: str) -> dict:
    # load_config raised on error before; original code exited on error,
    # but we will re-raise to keep behavior obvious
    return monitor.load_config(config_file)

def get_current_date():
    return monitor.get_current_date()

def parse_job_date(date: str):
    return monitor.parse_job_date(date)

def get_jobs(prow_link: str):
    try:
        return monitor.get_jobs(prow_link)
    except Exception as e:
        return _err_str_from_exc(e)

def get_n_recent_jobs(prow_link: str, n: int):
    try:
        return monitor.get_n_recent_jobs(prow_link, n)
    except Exception as e:
        return _err_str_from_exc(e)

def check_job_status(spy_link: str):
    try:
        return monitor.check_job_status(spy_link)
    except Exception as e:
        return _err_str_from_exc(e)

def cluster_deploy_status(spy_link: str):
    try:
        return monitor.cluster_deploy_status(spy_link)
    except Exception as e:
        return _err_str_from_exc(e)

def cluster_creation_error_analysis(spylink: str):
    try:
        return monitor.cluster_creation_error_analysis(spylink)
    except Exception as e:
        return _err_str_from_exc(e)

def check_if_gather_libvirt_dir_exists(spy_link: str, job_type: str):
    try:
        return monitor.check_if_gather_libvirt_dir_exists(spy_link, job_type)
    except Exception as e:
        return _err_str_from_exc(e)

def check_hypervisor_error(spy_link: str):
    try:
        return monitor.check_hypervisor_error(spy_link)
    except Exception as e:
        return _err_str_from_exc(e)

def check_if_sensitive_info_exposed(spy_link: str):
    try:
        return monitor.check_if_sensitive_info_exposed(spy_link)
    except Exception as e:
        # original function raised RuntimeError on underlying errors in strict variant;
        # in legacy it returned booleans or raised. We'll return False and preserve message by raising RuntimeError
        raise RuntimeError(f"Error in check_if_sensitive_info_exposed: {_err_str_from_exc(e)}")

def get_node_status(spy_link: str):
    try:
        return monitor.get_node_status(spy_link)
    except Exception as e:
        return _err_str_from_exc(e)

def check_node_crash(spy_link: str):
    try:
        return monitor.check_node_crash(spy_link)
    except Exception as e:
        return _err_str_from_exc(e)

def get_lease(build_log_response, job_platform: str):
    try:
        return monitor.get_lease(build_log_response, job_platform)
    except Exception as e:
        return "Failed to fetch lease information"

def get_nightly(build_log_url: str, build_log_response, job_platform: str):
    try:
        return monitor.get_nightly(build_log_url, build_log_response, job_platform)
    except Exception as e:
        return f"Unable to fetch nightly {job_platform} information - No match found"

def get_quota_and_nightly(spy_link: str):
    try:
        return monitor.get_quota_and_nightly(spy_link)
    except monitor.ProwTimeoutError as e:
        # original returned error strings but caller expects (lease, nightly) normally
        return ("Request timed out", None)
    except monitor.ProwFetchError as e:
        return ("Error while sending request to url", None)
    except Exception:
        return ("Failed to fetch lease information", None)

def job_classifier(spy_link: str):
    # stateless; just forward
    return monitor.job_classifier(spy_link)

def get_failed_monitor_testcases(spy_link: str, job_type: str) -> Tuple[List[str], str]:
    try:
        tcs = monitor.get_failed_monitor_testcases(spy_link, job_type)
        # strict variant returns list (or raises) — original returned (list, None) on success
        if isinstance(tcs, tuple):
            # if strict variant already returned (list,msg)
            return tcs
        return tcs, None
    except monitor.ProwTimeoutError as e:
        return [], "Request timed out"
    except monitor.ProwFetchError as e:
        return [], "Failed to get response from e2e-test directory url"
    except monitor.ProwParseError as e:
        return [], "Failed to parse the data from e2e-test log file!"
    except Exception:
        return [], "Failed to parse the data from e2e-test log file!"

def get_failed_monitor_testcases_from_xml(spy_link: str, job_type: str) -> Tuple[List[str], str]:
    try:
        tcs = monitor.get_failed_monitor_testcases_from_xml(spy_link, job_type)
        return tcs, None
    except monitor.ProwTimeoutError:
        return [], "Request timed out"
    except monitor.ProwFetchError:
        return [], "Failed to get response from e2e-test directory url"
    except monitor.ProwParseError:
        return [], "Failed to parse junit e2e log file!"
    except Exception:
        return [], "Monitor test file not found"

def get_testcase_frequency(spylinks, zone=None, tc_name=None):
    try:
        return monitor.get_testcase_frequency(spylinks, zone, tc_name)
    except Exception:
        return {}

def get_failed_e2e_testcases(spy_link: str, job_type: str) -> Tuple[List[str], str]:
    try:
        tcs = monitor.get_failed_e2e_testcases(spy_link, job_type)
        # strict version returns list; original returned (list, None)
        return tcs, None
    except monitor.ProwTimeoutError:
        return [], "Request timed out"
    except monitor.ProwFetchError:
        return [], "Failed to get response from e2e-test directory url"
    except monitor.ProwParseError:
        return [], "Failed to parse the data from e2e-test log file!"
    except Exception:
        return [], "Test summary file not found"

def get_junit_symptom_detection_testcase_failures(spy_link: str, job_type: str) -> Tuple[List[str], str]:
    try:
        tcs = monitor.get_junit_symptom_detection_testcase_failures(spy_link, job_type)
        return tcs, None
    except monitor.ProwTimeoutError:
        return [], "Request timed out"
    except monitor.ProwFetchError:
        return [], "Error while sending request to url"
    except monitor.ProwParseError:
        return [], "Failed to parse symptom detection e2e log file!"
    except Exception:
        return [], "Junit test summary file not found"

def get_all_failed_tc(spylink: str, jobtype: str):
    """
    Return triple as original: (failed_tc_dict, failed_tc_count, error_object)
    original returned (failed_tc, failed_tc_count, error_object)
    """
    try:
        failed_tc = monitor.get_all_failed_tc(spylink, jobtype)
        # strict version returns dict; original returned (dict, count, errors)
        if isinstance(failed_tc, tuple) and len(failed_tc) == 3:
            return failed_tc
        # if strict returns dict, compute counts and empty error object (best-effort)
        failed_tc_dict = failed_tc
        conformance = failed_tc_dict.get("conformance", [])
        monitor_list = failed_tc_dict.get("monitor", [])
        symptom = failed_tc_dict.get("symptom_detection", [])
        failed_tc_count = len(conformance) + len(monitor_list) + len(symptom)
        error_object = {"conformance": None, "monitor": None, "symptom_detection": None}
        return failed_tc_dict, failed_tc_count, error_object
    except monitor.ProwTimeoutError:
        return {}, 0, {"conformance": "Request timed out", "monitor": "Request timed out", "symptom_detection": "Request timed out"}
    except monitor.ProwFetchError:
        return {}, 0, {"conformance": "Error while sending request to url", "monitor": "Error while sending request to url", "symptom_detection": "Error while sending request to url"}
    except monitor.ProwParseError:
        return {}, 0, {"conformance": "Failed to parse the data from e2e-test log file!", "monitor": "Failed to parse the data from e2e-test log file!", "symptom_detection": "Failed to parse the data from e2e-test log file!"}
    except Exception:
        return {}, 0, {"conformance": "Test summary file not found", "monitor": "Test summary file not found", "symptom_detection": "Test summary file not found"}

def check_ts_exe_status(spylink: str, jobtype: str):
    try:
        return monitor.check_ts_exe_status(spylink, jobtype)
    except monitor.ProwTimeoutError:
        return "Request timed out"
    except monitor.ProwFetchError:
        return "Error while sending request to url"
    except monitor.ProwParseError:
        return "ERROR"
    except Exception:
        return "ERROR"

def print_all_failed_tc(spylink: str, jobtype: str):
    try:
        return monitor.print_all_failed_tc(spylink, jobtype)
    except monitor.ProwTimeoutError:
        return "Request timed out"
    except monitor.ProwFetchError:
        return "Error while sending request to url"
    except monitor.ProwParseError:
        return "ERROR"
    except Exception:
        return "ERROR"

def check_testcase_failure(spylink: str, job_type: str, testcase_name: str) -> bool:
    try:
        return monitor.check_testcase_failure(spylink, job_type, testcase_name)
    except Exception:
        # safe fallback: False (test not found / error)
        return False

def get_jobs_with_date(prowci_url: str, start_date, end_date):
    try:
        return monitor.get_jobs_with_date(prowci_url, start_date, end_date)
    except monitor.ProwTimeoutError:
        return "Request timed out"
    except monitor.ProwFetchError:
        return "Error while sending request to url"
    except monitor.ProwParseError:
        return "ERROR"
    except Exception:
        return "ERROR"

def get_next_page_first_build_date(ci_next_page_spylink: str, end_date):
    try:
        return monitor.get_next_page_first_build_date(ci_next_page_spylink, end_date)
    except monitor.ProwTimeoutError:
        return "Request timed out"
    except monitor.ProwFetchError:
        return "Error while sending request to url"
    except monitor.ProwParseError:
        return "ERROR"
    except Exception:
        return "ERROR"

def get_brief_job_info(build_list, prow_ci_name, zone=None):
    try:
        return monitor.get_brief_job_info(build_list, prow_ci_name, zone=zone)
    except monitor.ProwTimeoutError:
        # original returned printed message and empty list
        return []
    except monitor.ProwFetchError:
        return []
    except monitor.ProwParseError:
        return []
    except Exception:
        return []

def get_detailed_job_info(build_list, prow_ci_name, zone=None):
    try:
        return monitor.get_detailed_job_info(build_list, prow_ci_name, zone=zone)
    except monitor.ProwTimeoutError:
        return 1
    except monitor.ProwFetchError:
        return 1
    except monitor.ProwParseError:
        return 1
    except Exception:
        return 1

# Allow attribute access fallback to underlying strict module for constants etc.
def __getattr__(name):
    return getattr(monitor, name)
