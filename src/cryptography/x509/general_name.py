# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import abc
import ipaddress
import warnings
from email.utils import parseaddr

import idna

import six

from six.moves import urllib_parse

from cryptography import utils
from cryptography.x509.name import Name
from cryptography.x509.oid import ObjectIdentifier


_GENERAL_NAMES = {
    0: "otherName",
    1: "rfc822Name",
    2: "dNSName",
    3: "x400Address",
    4: "directoryName",
    5: "ediPartyName",
    6: "uniformResourceIdentifier",
    7: "iPAddress",
    8: "registeredID",
}


class UnsupportedGeneralNameType(Exception):
    def __init__(self, msg, type):
        super(UnsupportedGeneralNameType, self).__init__(msg)
        self.type = type


@six.add_metaclass(abc.ABCMeta)
class GeneralName(object):
    @abc.abstractproperty
    def value(self):
        """
        Return the value of the object
        """


@utils.register_interface(GeneralName)
class RFC822Name(object):
    def __init__(self, value):
        if not isinstance(value, six.text_type):
            raise TypeError("value must be a unicode string")

        name, address = parseaddr(value)
        parts = address.split(u"@")
        if name or not address:
            # parseaddr has found a name (e.g. Name <email>) or the entire
            # value is an empty string.
            raise ValueError("Invalid rfc822name value")
        elif len(parts) == 1:
            # Single label email name. This is valid for local delivery.
            # No IDNA encoding needed since there is no domain component.
            encoded = address.encode("ascii")
        else:
            # A normal email of the form user@domain.com. Let's attempt to
            # encode the domain component and reconstruct the address.
            encoded = parts[0].encode("ascii") + b"@" + idna.encode(parts[1])

        self._value = value
        self._encoded = encoded

    value = utils.read_only_property("_value")

    def __repr__(self):
        return "<RFC822Name(value={0})>".format(self.value)

    def __eq__(self, other):
        if not isinstance(other, RFC822Name):
            return NotImplemented

        return self.value == other.value

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.value)


def _idna_encode(value):
    # Retain prefixes '*.' for common/alt names and '.' for name constraints
    for prefix in ['*.', '.']:
        if value.startswith(prefix):
            value = value[len(prefix):]
            return prefix.encode('ascii') + idna.encode(value)
    return idna.encode(value)


@utils.register_interface(GeneralName)
class DNSName(object):
    def __init__(self, value):
        if isinstance(value, six.text_type):
            try:
                value = value.encode("ascii")
            except UnicodeEncodeError:
                value = _idna_encode(value)
                warnings.warn(
                    "DNSName values should be passed as idna-encoded bytes, "
                    "not strings. Support for passing unicode strings will be "
                    "removed in a future version.",
                    utils.DeprecatedIn21,
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    "DNSName values should be passed as bytes, not strings. "
                    "Support for passing unicode strings will be removed in a "
                    "future version.",
                    utils.DeprecatedIn21,
                    stacklevel=2,
                )
        elif not isinstance(value, bytes):
            raise TypeError("value must be bytes")

        self._bytes_value = value

    bytes_value = utils.read_only_property("_bytes_value")

    @property
    def value(self):
        warnings.warn(
            "DNSName.bytes_value should be used instead of DNSName.value; it "
            "contains the DNS name as raw bytes, instead of as an idna-decoded"
            " unicode string. DNSName.value will be removed in a future "
            "version.",
            utils.DeprecatedIn21,
            stacklevel=2
        )
        data = self._bytes_value
        if not data:
            decoded = u""
        elif data.startswith(b"*."):
            # This is a wildcard name. We need to remove the leading wildcard,
            # IDNA decode, then re-add the wildcard. Wildcard characters should
            # always be left-most (RFC 2595 section 2.4).
            decoded = u"*." + idna.decode(data[2:])
        else:
            # Not a wildcard, decode away. If the string has a * in it anywhere
            # invalid this will raise an InvalidCodePoint
            decoded = idna.decode(data)
            if data.startswith(b"."):
                # idna strips leading periods. Name constraints can have that
                # so we need to re-add it. Sigh.
                decoded = u"." + decoded
        return decoded

    def __repr__(self):
        return "<DNSName(bytes_value={0!r})>".format(self.bytes_value)

    def __eq__(self, other):
        if not isinstance(other, DNSName):
            return NotImplemented

        return self.bytes_value == other.bytes_value

    def __ne__(self, other):
        return not self == other


@utils.register_interface(GeneralName)
class UniformResourceIdentifier(object):
    def __init__(self, value):
        if not isinstance(value, six.text_type):
            raise TypeError("value must be a unicode string")

        parsed = urllib_parse.urlparse(value)
        if not parsed.hostname:
            netloc = ""
        elif parsed.port:
            netloc = (
                idna.encode(parsed.hostname) +
                ":{0}".format(parsed.port).encode("ascii")
            ).decode("ascii")
        else:
            netloc = idna.encode(parsed.hostname).decode("ascii")

        # Note that building a URL in this fashion means it should be
        # semantically indistinguishable from the original but is not
        # guaranteed to be exactly the same.
        uri = urllib_parse.urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        )).encode("ascii")

        self._value = value
        self._encoded = uri

    value = utils.read_only_property("_value")

    def __repr__(self):
        return "<UniformResourceIdentifier(value={0})>".format(self.value)

    def __eq__(self, other):
        if not isinstance(other, UniformResourceIdentifier):
            return NotImplemented

        return self.value == other.value

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.value)


@utils.register_interface(GeneralName)
class DirectoryName(object):
    def __init__(self, value):
        if not isinstance(value, Name):
            raise TypeError("value must be a Name")

        self._value = value

    value = utils.read_only_property("_value")

    def __repr__(self):
        return "<DirectoryName(value={0})>".format(self.value)

    def __eq__(self, other):
        if not isinstance(other, DirectoryName):
            return NotImplemented

        return self.value == other.value

    def __ne__(self, other):
        return not self == other


@utils.register_interface(GeneralName)
class RegisteredID(object):
    def __init__(self, value):
        if not isinstance(value, ObjectIdentifier):
            raise TypeError("value must be an ObjectIdentifier")

        self._value = value

    value = utils.read_only_property("_value")

    def __repr__(self):
        return "<RegisteredID(value={0})>".format(self.value)

    def __eq__(self, other):
        if not isinstance(other, RegisteredID):
            return NotImplemented

        return self.value == other.value

    def __ne__(self, other):
        return not self == other


@utils.register_interface(GeneralName)
class IPAddress(object):
    def __init__(self, value):
        if not isinstance(
            value,
            (
                ipaddress.IPv4Address,
                ipaddress.IPv6Address,
                ipaddress.IPv4Network,
                ipaddress.IPv6Network
            )
        ):
            raise TypeError(
                "value must be an instance of ipaddress.IPv4Address, "
                "ipaddress.IPv6Address, ipaddress.IPv4Network, or "
                "ipaddress.IPv6Network"
            )

        self._value = value

    value = utils.read_only_property("_value")

    def __repr__(self):
        return "<IPAddress(value={0})>".format(self.value)

    def __eq__(self, other):
        if not isinstance(other, IPAddress):
            return NotImplemented

        return self.value == other.value

    def __ne__(self, other):
        return not self == other


@utils.register_interface(GeneralName)
class OtherName(object):
    def __init__(self, type_id, value):
        if not isinstance(type_id, ObjectIdentifier):
            raise TypeError("type_id must be an ObjectIdentifier")
        if not isinstance(value, bytes):
            raise TypeError("value must be a binary string")

        self._type_id = type_id
        self._value = value

    type_id = utils.read_only_property("_type_id")
    value = utils.read_only_property("_value")

    def __repr__(self):
        return "<OtherName(type_id={0}, value={1!r})>".format(
            self.type_id, self.value)

    def __eq__(self, other):
        if not isinstance(other, OtherName):
            return NotImplemented

        return self.type_id == other.type_id and self.value == other.value

    def __ne__(self, other):
        return not self == other
