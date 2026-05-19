"""Pydantic models for the NAPALM getter / driver contract.

Every model historically defined as ``TypedDict`` here is now a Pydantic v2
``BaseModel``. The class names are preserved (e.g. ``FactsDict``,
``InterfaceDict``) so existing imports such as ``napalm.base.models.FactsDict``
continue to work as type annotations on driver methods.

Defaults:
    * ``extra="forbid"`` — unknown keys raise a validation error.
    * ``populate_by_name=True`` — fields with aliases (e.g. ``%usage``) can be
      populated either by the alias or by the Python attribute name.

Validation is *not* enforced on driver return values yet; that wiring lives in
Phase 2 (``napalm/base/base.py`` + ``NAPALM_STRICT_MODELS``).
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel
from pydantic import ConfigDict as _PydanticConfig
from pydantic import Field, RootModel

# ---------------------------------------------------------------------------
# Constrained primitives
# ---------------------------------------------------------------------------

# Canonical MAC-address regex (xx:xx:xx:xx:xx:xx). Drivers normalise via
# ``napalm.base.helpers.mac`` so this form is what we expect on the wire.
MACAddress = Annotated[str, Field(pattern=r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")]

# IP addresses are kept as plain strings for now; switching to ``IPvAnyAddress``
# is tracked in the migration plan (Phase 1 / Phase 4 fallout).
IPAddress = str
IPv6Address = str

# Interface MTU. Drivers may report ``0`` (sub-interfaces / loopbacks) or
# ``-1`` as a sentinel for "not available"; we therefore keep this loose for
# now and leave a real bound for a future cleanup pass.
MTU = int

# Linux/IOS-style privilege levels: 0..15 are standard, ``20`` is used by some
# drivers as a sentinel for "unknown / not applicable".
UserLevel = Annotated[int, Field(ge=0, le=20)]


# ---------------------------------------------------------------------------
# Base class with shared config
# ---------------------------------------------------------------------------


class _Model(BaseModel):
    """Common configuration for every NAPALM model."""

    model_config = _PydanticConfig(
        extra="forbid",
        populate_by_name=True,
        frozen=False,
    )


# ---------------------------------------------------------------------------
# Connectivity / facts / interfaces
# ---------------------------------------------------------------------------


class AliveDict(_Model):
    is_alive: bool


class FactsDict(_Model):
    os_version: str
    uptime: float
    interface_list: list[str]
    vendor: str
    serial_number: str
    model: str
    hostname: str
    fqdn: str


class InterfaceDict(_Model):
    is_up: bool
    is_enabled: bool
    description: str
    last_flapped: float
    mtu: MTU
    speed: float
    mac_address: str  # may be empty for L3 sub-interfaces; not enforced as MAC


class InterfaceCounterDict(_Model):
    tx_errors: int
    rx_errors: int
    tx_discards: int
    rx_discards: int
    tx_octets: int
    rx_octets: int
    tx_unicast_packets: int
    rx_unicast_packets: int
    tx_multicast_packets: int
    rx_multicast_packets: int
    tx_broadcast_packets: int
    rx_broadcast_packets: int


# ---------------------------------------------------------------------------
# LLDP
# ---------------------------------------------------------------------------


class LLDPNeighborDict(_Model):
    hostname: str
    port: str


class LLDPNeighborDetailDict(_Model):
    parent_interface: str
    remote_port: str
    remote_chassis_id: str
    remote_port_description: str
    remote_system_name: str
    remote_system_description: str
    remote_system_capab: list[str]
    remote_system_enable_capab: list[str]


class LLDPNeighborsDetailDict(RootModel[dict[str, list[LLDPNeighborDetailDict]]]):
    """``{interface_name: [LLDPNeighborDetailDict, ...]}``."""


# ---------------------------------------------------------------------------
# Environment / health
# ---------------------------------------------------------------------------


class TemperatureDict(_Model):
    is_alert: bool
    is_critical: bool
    temperature: float


class PowerDict(_Model):
    status: bool
    output: float
    capacity: float


class MemoryDict(_Model):
    used_ram: int
    available_ram: int


class FanDict(_Model):
    status: bool


class CPUDict(_Model):
    # The on-wire key is literally ``%usage``; expose it as ``usage`` in Python
    # but keep ``%usage`` as the alias (and the dump key) for back-compat.
    usage: float = Field(alias="%usage", serialization_alias="%usage")


class EnvironmentDict(_Model):
    fans: dict[str, FanDict]
    temperature: dict[str, TemperatureDict]
    power: dict[str, PowerDict]
    cpu: dict[int, CPUDict]
    memory: MemoryDict


# ---------------------------------------------------------------------------
# BGP
# ---------------------------------------------------------------------------


class AFDict(_Model):
    sent_prefixes: int
    accepted_prefixes: int
    received_prefixes: int


class PeerDict(_Model):
    is_enabled: bool
    uptime: int
    remote_as: int
    description: str
    remote_id: str
    local_as: int
    is_up: bool
    address_family: dict[str, AFDict]


class PeerDetailsDict(_Model):
    up: bool
    local_as: int
    remote_as: int
    router_id: str
    local_address: str
    routing_table: str
    local_address_configured: bool
    local_port: int
    remote_address: str
    remote_port: int
    multihop: bool
    multipath: bool
    remove_private_as: bool
    import_policy: str
    export_policy: str
    input_messages: int
    output_messages: int
    input_updates: int
    output_updates: int
    messages_queued_out: int
    connection_state: str
    previous_connection_state: str
    last_event: str
    suppress_4byte_as: bool
    local_as_prepend: bool
    holdtime: int
    configured_holdtime: int
    keepalive: int
    configured_keepalive: int
    active_prefix_count: int
    received_prefix_count: int
    accepted_prefix_count: int
    suppressed_prefix_count: int
    advertised_prefix_count: int
    flap_count: int


class BGPConfigGroupDict(_Model):
    type: str
    description: str
    apply_groups: list[str]
    multihop_ttl: int
    multipath: bool
    local_address: str
    local_as: int
    remote_as: int
    import_policy: str
    export_policy: str
    remove_private_as: bool
    # ``prefix_limit`` is a free-form nested dict keyed by AFI/SAFI; keeping it
    # loose for now (tightening is tracked in the migration plan).
    prefix_limit: dict[str, Any]
    neighbors: dict[str, Any]


class BGPConfigNeighborDict(_Model):
    description: str
    import_policy: str
    export_policy: str
    local_address: str
    authentication_key: str
    nhs: bool
    route_reflector_client: bool
    local_as: int
    remote_as: int
    prefix_limit: dict[str, Any]


class BGPStateAddressFamilyDict(_Model):
    received_prefixes: int
    accepted_prefixes: int
    sent_prefixes: int


class BGPStateNeighborDict(_Model):
    local_as: int
    remote_as: int
    remote_id: str
    is_up: bool
    is_enabled: bool
    description: str
    uptime: int
    address_family: dict[str, BGPStateAddressFamilyDict]


class BGPStateNeighborsPerVRFDict(_Model):
    router_id: str
    peers: dict[str, BGPStateNeighborDict]


# ---------------------------------------------------------------------------
# ARP / IPv6 ND / NTP / users
# ---------------------------------------------------------------------------


class ARPTableDict(_Model):
    interface: str
    mac: str
    ip: str
    age: float


class IPV6NeighborDict(_Model):
    interface: str
    mac: str
    ip: str
    age: float
    state: str


class NTPPeerDict(_Model):
    """``get_ntp_peers`` returns ``{peer: {}}`` — an empty per-peer dict."""

    # All fields optional / extra forbidden → matches the historical
    # ``TypedDict(..., total=False)`` with no declared keys.


class NTPServerDict(_Model):
    address: str | None = None
    port: int | None = None
    version: int | None = None
    association_type: str | None = None
    iburst: bool | None = None
    prefer: bool | None = None
    network_instance: str | None = None
    source_address: str | None = None
    key_id: int | None = None


class NTPStats(_Model):
    remote: str
    referenceid: str
    synchronized: bool
    stratum: int
    type: str
    when: str
    hostpoll: int
    reachability: int
    delay: float
    offset: float
    jitter: float


class UsersDict(_Model):
    level: UserLevel
    password: str
    sshkeys: list[str]


# ---------------------------------------------------------------------------
# Interface IP addresses
# ---------------------------------------------------------------------------


class InterfacesIPDictEntry(_Model):
    prefix_length: int | None = None


class InterfacesIPDict(_Model):
    ipv4: dict[str, InterfacesIPDictEntry] | None = None
    ipv6: dict[str, InterfacesIPDictEntry] | None = None


# ---------------------------------------------------------------------------
# MAC table / routing / SNMP
# ---------------------------------------------------------------------------


class MACAdressTable(_Model):
    """Historical misspelling preserved for back-compat (``MACAdress``)."""

    mac: str
    interface: str
    vlan: int
    static: bool
    active: bool
    moves: int
    last_move: float


class RouteDict(_Model):
    protocol: str
    current_active: bool
    last_active: bool
    age: int
    next_hop: str
    outgoing_interface: str
    selected_next_hop: bool
    preference: int
    inactive_reason: str
    routing_table: str
    protocol_attributes: dict[str, Any]


class SNMPCommunityDict(_Model):
    acl: str
    mode: str


class SNMPDict(_Model):
    chassis_id: str
    community: dict[str, SNMPCommunityDict]
    contact: str
    location: str


# ---------------------------------------------------------------------------
# RPM / probes
# ---------------------------------------------------------------------------


class ProbeTestDict(_Model):
    probe_type: str
    target: str
    source: str
    probe_count: int
    test_interval: int


class ProbeTestResultDict(_Model):
    target: str
    source: str
    probe_type: str
    probe_count: int
    rtt: float
    round_trip_jitter: float
    last_test_loss: int
    current_test_min_delay: float
    current_test_max_delay: float
    current_test_avg_delay: float
    last_test_min_delay: float
    last_test_max_delay: float
    last_test_avg_delay: float
    global_test_min_delay: float
    global_test_max_delay: float
    global_test_avg_delay: float


# ---------------------------------------------------------------------------
# Ping / traceroute
# ---------------------------------------------------------------------------


class PingResultDictEntry(_Model):
    ip_address: str
    rtt: float


class PingDict(_Model):
    probes_sent: int
    packet_loss: int
    rtt_min: float
    rtt_max: float
    rtt_avg: float
    rtt_stddev: float
    results: list[PingResultDictEntry]


class PingResultDict(_Model):
    """Either ``success`` or ``error`` is populated, never both.

    Modelled as two optional fields rather than a discriminated union because
    the discriminator is the key itself rather than an internal tag.
    """

    success: PingDict | None = None
    error: str | None = None


class TracerouteDict(_Model):
    rtt: float
    ip_address: str
    host_name: str


class TracerouteResultDictEntry(_Model):
    probes: dict[int, TracerouteDict] | None = None


class TracerouteResultDict(_Model):
    success: dict[int, TracerouteResultDictEntry] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Optics
# ---------------------------------------------------------------------------


class OpticsStateDict(_Model):
    instant: float
    avg: float
    min: float
    max: float


class OpticsStatePerChannelDict(_Model):
    input_power: OpticsStateDict
    output_power: OpticsStateDict
    laser_bias_current: OpticsStateDict


class OpticsPerChannelDict(_Model):
    index: int
    state: OpticsStatePerChannelDict


class OpticsPhysicalChannelsDict(_Model):
    # NOTE: historical TypedDict typed this as a single ``OpticsPerChannelDict``
    # but every driver actually returns a *list* of channels. The migration plan
    # calls out fixing this; the list form is the de-facto contract.
    channel: list[OpticsPerChannelDict]


class OpticsDict(_Model):
    physical_channels: OpticsPhysicalChannelsDict


# ---------------------------------------------------------------------------
# Configuration / network instances / firewall / VLANs
# ---------------------------------------------------------------------------


class ConfigDict(_Model):
    running: str
    startup: str
    candidate: str


# ``ConfigurationDict`` was a near-duplicate of ``ConfigDict`` (same fields,
# different key order). Keep the name as an alias for back-compat.
ConfigurationDict = ConfigDict


class NetworkInstanceStateDict(_Model):
    route_distinguisher: str


class NetworkInstanceInterfacesDict(_Model):
    interface: dict[str, Any]


class NetworkInstanceDict(_Model):
    name: str
    type: str
    state: NetworkInstanceStateDict
    interfaces: NetworkInstanceInterfacesDict


class FirewallPolicyDict(_Model):
    position: int
    packet_hits: int
    byte_hits: int
    id: str
    enabled: bool
    schedule: str
    log: str
    l3_src: str
    l3_dst: str
    service: str
    src_zone: str
    dst_zone: str
    action: str


class VlanDict(_Model):
    name: str
    interfaces: list[str]


# ---------------------------------------------------------------------------
# Validation result models
# ---------------------------------------------------------------------------


class DictValidationResult(_Model):
    complies: bool
    present: dict[str, Any]
    missing: list[Any]
    extra: list[Any]


class ListValidationResult(_Model):
    complies: bool
    present: list[Any]
    missing: list[Any]
    extra: list[Any]


class ReportResult(_Model):
    complies: bool
    skipped: list[Any]


# ---------------------------------------------------------------------------
# Registry — useful for schema export and the test framework
# ---------------------------------------------------------------------------


def getter_model(method_name: str) -> Any:
    """Return the declared return annotation of ``NetworkDriver.<method_name>``.

    The annotation is the full typing expression (e.g. ``FactsDict`` or
    ``Dict[str, InterfaceDict]``) and is suitable as input to
    :class:`pydantic.TypeAdapter` for validation.

    Raises ``AttributeError`` if no such method exists, ``KeyError`` if the
    method has no return annotation.
    """
    import typing

    # Imported lazily to avoid a circular import at module load time.
    from napalm.base.base import NetworkDriver

    method = getattr(NetworkDriver, method_name)
    hints = typing.get_type_hints(method)
    try:
        return hints["return"]
    except KeyError as exc:
        raise KeyError(f"NetworkDriver.{method_name} has no return annotation") from exc


ALL_MODELS: dict[str, type[BaseModel]] = {
    name: obj
    for name, obj in list(globals().items())
    if (
        isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj.__module__ == __name__
        and obj is not _Model
    )
}
