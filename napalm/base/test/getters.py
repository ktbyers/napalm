"""Testing framework."""

import functools
from itertools import zip_longest
import inspect
import json

import pytest
from pydantic import TypeAdapter, ValidationError

from napalm.base import models
from napalm.base import NetworkDriver
from napalm.base.test import conftest


def _validate_contract(method_name, data):
    """Validate ``data`` against ``NetworkDriver.<method_name>``'s return annotation.

    Pydantic recurses through ``Dict[str, Model]`` / ``List[Model]`` /
    ``RootModel`` so a single call replaces the historical per-element walk.
    """
    annotation = models.getter_model(method_name)
    try:
        TypeAdapter(annotation).validate_python(data)
    except ValidationError as exc:
        raise AssertionError(
            f"{method_name} returned data that does not match the NAPALM "
            f"contract ({annotation}):\n{exc}"
        ) from exc
    return True


def list_dicts_diff(prv, nxt):
    """Compare two lists of dicts."""
    result = []
    for prv_element, nxt_element in zip_longest(prv, nxt, fillvalue={}):
        intermediate_result = dict_diff(prv_element, nxt_element)
        if intermediate_result:
            result.append(intermediate_result)
    return result


def dict_diff(prv, nxt):
    """Return a dict of keys that differ with another config object."""
    keys = set(list(prv.keys()) + list(nxt.keys()))
    result = {}

    for k in keys:
        if isinstance(prv.get(k), dict):
            if isinstance(nxt.get(k), dict):
                "If both are dicts we do a recursive call."
                diff = dict_diff(prv.get(k), nxt.get(k))
                if diff:
                    result[k] = diff
            else:
                "If only one is a dict they are clearly different"
                result[k] = {"result": prv.get(k), "expected": nxt.get(k)}
        else:
            "Ellipsis is a wildcard."
            if prv.get(k) != nxt.get(k) and nxt.get(k) != "...":
                result[k] = {"result": prv.get(k), "expected": nxt.get(k)}
    return result


def wrap_test_cases(func):
    """Wrap test cases."""
    func.__dict__["build_test_cases"] = True

    @functools.wraps(func)
    def mock_wrapper(cls, test_case):
        for patched_attr in cls.device.patched_attrs:
            attr = getattr(cls.device, patched_attr)
            attr.current_test = func.__name__
            attr.current_test_case = test_case

        try:
            # This is an ugly, ugly, ugly hack because some python objects don't load
            # as expected. For example, dicts where integers are strings
            result = json.loads(json.dumps(func(cls, test_case)))
        except IOError:
            if test_case == "no_test_case_found":
                pytest.fail("No test case for '{}' found".format(func.__name__))
            else:
                raise
        except NotImplementedError:
            pytest.skip("Method not implemented")
            return

        # This is an ugly, ugly, ugly hack because some python objects don't load
        # as expected. For example, dicts where integers are strings

        try:
            expected_result = attr.expected_result
        except IOError as e:
            raise Exception("{}. Actual result was: {}".format(e, json.dumps(result)))
        if isinstance(result, list):
            diff = list_dicts_diff(result, expected_result)
        else:
            diff = dict_diff(result, expected_result)
        if diff:
            print("Resulting JSON object was: {}".format(json.dumps(result)))
            raise AssertionError("Expected result varies on some keys {}".format(json.dumps(diff)))

        for patched_attr in cls.device.patched_attrs:
            attr = getattr(cls.device, patched_attr)
            attr.current_test = ""  # Empty them to avoid side effects
            attr.current_test_case = ""  # Empty them to avoid side effects

        return None

    @functools.wraps(func)
    def real_wrapper(cls, test_case):
        try:
            return func(cls, test_case)
        except NotImplementedError:
            pytest.skip("Method not implemented")
            return

    if conftest.NAPALM_TEST_MOCK:
        return mock_wrapper
    else:
        return real_wrapper


class BaseTestGetters(object):
    """Base class for testing drivers."""

    def test_method_signatures(self):
        """
        Test that all methods have the same signature.

        The type hint annotations are ignored here because the import paths might differ.
        """
        errors = {}
        cls = self.driver
        # Create fictional driver instance (py3 needs bound methods)
        tmp_obj = cls(hostname="test", username="admin", password="pwd")
        attrs = [m for m, v in inspect.getmembers(tmp_obj)]
        for attr in attrs:
            func = getattr(tmp_obj, attr)
            if attr.startswith("_") or not inspect.ismethod(func):
                continue
            try:
                orig = getattr(NetworkDriver, attr)
                orig_spec = inspect.getfullargspec(inspect.unwrap(orig))[:4]
            except AttributeError:
                orig_spec = "Method does not exist in napalm.base"
            func_spec = inspect.getfullargspec(inspect.unwrap(func))[:4]
            if orig_spec != func_spec:
                errors[attr] = (orig_spec, func_spec)

        EXTRA_METHODS = ["__init__"]
        for method in EXTRA_METHODS:
            orig_spec = inspect.getfullargspec(getattr(NetworkDriver, method))[:4]
            func_spec = inspect.getfullargspec(getattr(cls, method))[:4]
            if orig_spec != func_spec:
                errors[attr] = (orig_spec, func_spec)

        assert not errors, "Some methods vary. \n{}".format(errors.keys())

    @wrap_test_cases
    def test_is_alive(self, test_case):
        """Test is_alive method."""
        alive = self.device.is_alive()
        assert _validate_contract("is_alive", alive)
        return alive

    @wrap_test_cases
    def test_get_facts(self, test_case):
        """Test get_facts method."""
        facts = self.device.get_facts()
        assert _validate_contract("get_facts", facts)
        return facts

    @wrap_test_cases
    def test_get_interfaces(self, test_case):
        """Test get_interfaces."""
        get_interfaces = self.device.get_interfaces()
        assert len(get_interfaces) > 0
        assert _validate_contract("get_interfaces", get_interfaces)
        return get_interfaces

    @wrap_test_cases
    def test_get_lldp_neighbors(self, test_case):
        """Test get_lldp_neighbors."""
        get_lldp_neighbors = self.device.get_lldp_neighbors()
        assert len(get_lldp_neighbors) > 0
        assert _validate_contract("get_lldp_neighbors", get_lldp_neighbors)
        return get_lldp_neighbors

    @wrap_test_cases
    def test_get_interfaces_counters(self, test_case):
        """Test get_interfaces_counters."""
        get_interfaces_counters = self.device.get_interfaces_counters()
        assert len(get_interfaces_counters) > 0
        assert _validate_contract("get_interfaces_counters", get_interfaces_counters)
        return get_interfaces_counters

    @wrap_test_cases
    def test_get_environment(self, test_case):
        """Test get_environment."""
        environment = self.device.get_environment()
        assert len(environment) > 0
        assert _validate_contract("get_environment", environment)
        return environment

    @wrap_test_cases
    def test_get_bgp_neighbors(self, test_case):
        """Test get_bgp_neighbors."""
        get_bgp_neighbors = self.device.get_bgp_neighbors()
        if len(get_bgp_neighbors) > 0:
            assert "global" in get_bgp_neighbors.keys()
        assert _validate_contract("get_bgp_neighbors", get_bgp_neighbors)
        return get_bgp_neighbors

    @wrap_test_cases
    def test_get_lldp_neighbors_detail(self, test_case):
        """Test get_lldp_neighbors_detail."""
        get_lldp_neighbors_detail = self.device.get_lldp_neighbors_detail()
        assert len(get_lldp_neighbors_detail) > 0
        assert _validate_contract("get_lldp_neighbors_detail", get_lldp_neighbors_detail)
        return get_lldp_neighbors_detail

    @wrap_test_cases
    def test_get_bgp_config(self, test_case):
        """Test get_bgp_config."""
        get_bgp_config = self.device.get_bgp_config()
        assert get_bgp_config == {} or len(get_bgp_config) > 0
        assert _validate_contract("get_bgp_config", get_bgp_config)
        return get_bgp_config

    @wrap_test_cases
    def test_get_bgp_neighbors_detail(self, test_case):
        """Test get_bgp_neighbors_detail.

        ``get_bgp_neighbors_detail`` return type is
        ``Dict[str, Dict[int, List[PeerDetailsDict]]]`` -- Pydantic recurses
        into the inner dict, so a single contract call is sufficient.
        """
        get_bgp_neighbors_detail = self.device.get_bgp_neighbors_detail()
        assert len(get_bgp_neighbors_detail) > 0
        assert _validate_contract("get_bgp_neighbors_detail", get_bgp_neighbors_detail)
        return get_bgp_neighbors_detail

    @wrap_test_cases
    def test_get_arp_table(self, test_case):
        """Test get_arp_table."""
        get_arp_table = self.device.get_arp_table()
        assert len(get_arp_table) > 0
        assert _validate_contract("get_arp_table", get_arp_table)
        return get_arp_table

    @wrap_test_cases
    def test_get_arp_table_with_vrf(self, test_case):
        """Test get_arp_table."""
        get_arp_table = self.device.get_arp_table(vrf="TEST")
        assert len(get_arp_table) > 0
        assert _validate_contract("get_arp_table", get_arp_table)
        return get_arp_table

    @wrap_test_cases
    def test_get_ipv6_neighbors_table(self, test_case):
        """Test get_ipv6_neighbors_table."""
        get_ipv6_neighbors_table = self.device.get_ipv6_neighbors_table()
        assert _validate_contract("get_ipv6_neighbors_table", get_ipv6_neighbors_table)
        return get_ipv6_neighbors_table

    @wrap_test_cases
    def test_get_ntp_peers(self, test_case):
        """Test get_ntp_peers.

        ``NTPPeerDict`` is an open-ended model (all fields optional) so
        validation is essentially type-checking the per-peer value is a dict.
        """
        get_ntp_peers = self.device.get_ntp_peers()
        assert len(get_ntp_peers) > 0
        for peer in get_ntp_peers:
            assert isinstance(peer, str)
        assert _validate_contract("get_ntp_peers", get_ntp_peers)
        return get_ntp_peers

    @wrap_test_cases
    def test_get_ntp_servers(self, test_case):
        """Test get_ntp_servers."""
        get_ntp_servers = self.device.get_ntp_servers()
        assert len(get_ntp_servers) > 0
        for server in get_ntp_servers:
            assert isinstance(server, str)
        assert _validate_contract("get_ntp_servers", get_ntp_servers)
        return get_ntp_servers

    @wrap_test_cases
    def test_get_ntp_stats(self, test_case):
        """Test get_ntp_stats."""
        get_ntp_stats = self.device.get_ntp_stats()
        assert len(get_ntp_stats) > 0
        assert _validate_contract("get_ntp_stats", get_ntp_stats)
        return get_ntp_stats

    @wrap_test_cases
    def test_get_interfaces_ip(self, test_case):
        """Test get_interfaces_ip."""
        get_interfaces_ip = self.device.get_interfaces_ip()
        assert len(get_interfaces_ip) > 0
        assert _validate_contract("get_interfaces_ip", get_interfaces_ip)
        return get_interfaces_ip

    @wrap_test_cases
    def test_get_mac_address_table(self, test_case):
        """Test get_mac_address_table."""
        get_mac_address_table = self.device.get_mac_address_table()
        assert len(get_mac_address_table) > 0
        assert _validate_contract("get_mac_address_table", get_mac_address_table)
        return get_mac_address_table

    @wrap_test_cases
    def test_get_route_to(self, test_case):
        """Test get_route_to."""
        destination = "1.0.4.0/24"
        protocol = "bgp"
        get_route_to = self.device.get_route_to(destination=destination, protocol=protocol)
        assert len(get_route_to) > 0
        assert _validate_contract("get_route_to", get_route_to)
        return get_route_to

    @wrap_test_cases
    def test_get_route_to_longer(self, test_case):
        """Test get_route_to with longer=True"""
        destination = "1.0.4.0/24"
        protocol = "bgp"

        get_route_to = self.device.get_route_to(
            destination=destination, protocol=protocol, longer=True
        )
        assert len(get_route_to) > 0
        assert _validate_contract("get_route_to", get_route_to)
        return get_route_to

    @wrap_test_cases
    def test_get_snmp_information(self, test_case):
        """Test get_snmp_information."""
        get_snmp_information = self.device.get_snmp_information()
        assert len(get_snmp_information) > 0
        assert _validate_contract("get_snmp_information", get_snmp_information)
        return get_snmp_information

    @wrap_test_cases
    def test_get_probes_config(self, test_case):
        """Test get_probes_config."""
        get_probes_config = self.device.get_probes_config()
        assert len(get_probes_config) > 0
        assert _validate_contract("get_probes_config", get_probes_config)
        return get_probes_config

    @wrap_test_cases
    def test_get_probes_results(self, test_case):
        """Test get_probes_results."""
        get_probes_results = self.device.get_probes_results()
        assert len(get_probes_results) > 0
        assert _validate_contract("get_probes_results", get_probes_results)
        return get_probes_results

    @wrap_test_cases
    def test_ping(self, test_case):
        """Test ping."""
        destination = "8.8.8.8"
        get_ping = self.device.ping(destination)
        assert isinstance(get_ping.get("success"), dict)
        assert _validate_contract("ping", get_ping)
        return get_ping

    @wrap_test_cases
    def test_traceroute(self, test_case):
        """Test traceroute."""
        destination = "8.8.8.8"
        get_traceroute = self.device.traceroute(destination)
        assert isinstance(get_traceroute.get("success"), dict)
        assert _validate_contract("traceroute", get_traceroute)
        return get_traceroute

    @wrap_test_cases
    def test_get_users(self, test_case):
        """Test get_users."""
        get_users = self.device.get_users()
        assert len(get_users)
        assert _validate_contract("get_users", get_users)
        # Semantic check: privilege level is 0..15 or sentinel 20.
        for user_details in get_users.values():
            level = user_details.get("level")
            assert (0 <= level <= 15) or level == 20
        return get_users

    @wrap_test_cases
    def test_get_optics(self, test_case):
        """Test get_optics."""
        get_optics = self.device.get_optics()
        assert isinstance(get_optics, dict)
        assert _validate_contract("get_optics", get_optics)
        return get_optics

    @wrap_test_cases
    def test_get_config(self, test_case):
        """Test get_config method."""
        get_config = self.device.get_config()

        assert isinstance(get_config, dict)
        assert _validate_contract("get_config", get_config)

        return get_config

    @wrap_test_cases
    def test_get_config_filtered(self, test_case):
        """Test get_config method."""
        if self.device.platform == "iosxr_netconf":
            pytest.skip("This test is not implemented on {self.device.platform}")
        for config in ["running", "startup", "candidate"]:
            get_config = self.device.get_config(retrieve=config)

            assert get_config["candidate"] == "" if config != "candidate" else True
            assert get_config["startup"] == "" if config != "startup" else True
            assert get_config["running"] == "" if config != "running" else True

        return get_config

    @wrap_test_cases
    def test_get_config_sanitized(self, test_case):
        """Test get_config method."""
        get_config = self.device.get_config(sanitized=True)

        assert isinstance(get_config, dict)
        assert _validate_contract("get_config", get_config)

        return get_config

    @wrap_test_cases
    def test_get_config_sanitized_filtered(self, test_case):
        """Test get_config with both sanitized=True and retrieve parameter."""
        return_config = {}
        get_config = self.device.get_config(retrieve="running", sanitized=True)
        assert isinstance(get_config, dict)
        assert _validate_contract("get_config", get_config)
        assert get_config["startup"] == ""
        assert get_config["candidate"] == ""
        assert get_config["running"] != ""
        return_config["running"] = get_config["running"]

        get_config = self.device.get_config(retrieve="startup", sanitized=True)
        assert isinstance(get_config, dict)
        assert _validate_contract("get_config", get_config)
        assert get_config["running"] == ""
        assert get_config["candidate"] == ""

        return_config["startup"] = get_config["startup"]

        return_config["candidate"] = ""

        return return_config

    @wrap_test_cases
    def test_get_network_instances(self, test_case):
        """Test get_network_instances method."""
        get_network_instances = self.device.get_network_instances()
        assert isinstance(get_network_instances, dict)
        assert _validate_contract("get_network_instances", get_network_instances)
        return get_network_instances

    @wrap_test_cases
    def test_get_firewall_policies(self, test_case):
        """Test get_firewall_policies method."""
        get_firewall_policies = self.device.get_firewall_policies()
        assert len(get_firewall_policies) > 0
        assert _validate_contract("get_firewall_policies", get_firewall_policies)
        return get_firewall_policies

    @wrap_test_cases
    def test_get_vlans(self, test_case):
        """Test get_vlans."""
        get_vlans = self.device.get_vlans()
        assert len(get_vlans) > 0
        assert _validate_contract("get_vlans", get_vlans)
        return get_vlans
