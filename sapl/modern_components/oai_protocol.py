"""Small project-owned OAI-PMH 2.0 response layer backed by lxml.

The application supplies the query methods; this module validates requests,
produces XML, and keeps paging tokens independent of pyoai.
"""
import base64
import binascii
import json
import re
from datetime import datetime, timezone

from lxml import etree


OAI_NS = "http://www.openarchives.org/OAI/2.0/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
OAI_SCHEMA = "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"
OAI_PREFIX = "oai_lexml"
LEXML_NS = "http://www.lexml.gov.br/oai_lexml"
LEXML_SCHEMA = "http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd"

_Q = lambda name: "{{{}}}{}".format(OAI_NS, name)
_XSI_SCHEMA_LOCATION = "{{{}}}schemaLocation".format(XSI_NS)


class OAIProtocolError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class OAIServiceError(Exception):
    """Internal failure returned as HTTP 503, not an invented protocol code."""


class OAIProtocolServer:
    """Adapter matching the former handleRequest(dict) interface."""

    def __init__(self, provider, metadata_namespace=LEXML_NS, schema=LEXML_SCHEMA):
        self.provider = provider
        self.config = provider.config
        self.metadata_namespace = metadata_namespace
        self.schema = schema
        self.batch_size = max(1, int(self.config.get("batch_size", 10)))

    def handleRequest(self, request_kw):
        params = {}
        try:
            params = self._normalize(request_kw)
            root = self._envelope(params)
            self._dispatch(root, params)
        except OAIProtocolError as error:
            # Errors replace any partially built verb response. Invalid request
            # arguments and verbs must not be echoed as XML attributes.
            echo = {} if error.code in ("badArgument", "badVerb") else params
            root = self._envelope(echo)
            self._append_error(root, error.code, error.message)
        except OAIServiceError:
            raise
        except Exception as error:
            raise OAIServiceError("The OAI service could not complete the request.") from error
        return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)

    def _normalize(self, request_kw):
        params = {}
        for key, value in dict(request_kw or {}).items():
            if isinstance(value, (list, tuple)):
                if len(value) != 1:
                    raise OAIProtocolError("badArgument", "An argument occurs more than once.")
                value = value[0] if value else ""
            if isinstance(value, bytes):
                value = value.decode("utf-8", "replace")
            key, value = str(key), str(value)
            if key not in {"verb", "identifier", "metadataPrefix", "from", "until", "set", "resumptionToken"}:
                raise OAIProtocolError("badArgument", "The request contains an unexpected argument.")
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", value):
                raise OAIProtocolError("badArgument", "An argument contains invalid XML characters.")
            params[key] = value
        return params

    def _envelope(self, params):
        root = etree.Element(
            _Q("OAI-PMH"),
            nsmap={None: OAI_NS, "xsi": XSI_NS},
        )
        root.set(_XSI_SCHEMA_LOCATION, "{} {}".format(OAI_NS, OAI_SCHEMA))
        etree.SubElement(root, _Q("responseDate")).text = self._format_date(
            datetime.now(timezone.utc)
        )
        request = etree.SubElement(root, _Q("request"))
        for name, value in sorted(params.items()):
            request.set(name, value)
        request.text = self.config.get("base_url", "")
        return root

    @staticmethod
    def _append_error(root, code, message):
        etree.SubElement(root, _Q("error"), code=code).text = message

    @staticmethod
    def _format_date(value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _parse_date(value, inclusive=False):
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                parsed = datetime.strptime(value, "%Y-%m-%d")
                return parsed.replace(hour=23, minute=59, second=59) if inclusive else parsed
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
        raise OAIProtocolError("badArgument", "The datestamp has an invalid format.")

    def _dispatch(self, root, params):
        verb = params.get("verb")
        if not verb:
            raise OAIProtocolError("badVerb", "The verb argument is required.")
        allowed = {
            "Identify": set(),
            "ListMetadataFormats": {"identifier"},
            "ListSets": set(),
            "GetRecord": {"identifier", "metadataPrefix"},
            "ListRecords": {"metadataPrefix", "from", "until", "set", "resumptionToken"},
            "ListIdentifiers": {"metadataPrefix", "from", "until", "set", "resumptionToken"},
        }
        if verb not in allowed:
            raise OAIProtocolError("badVerb", "The value of the verb argument is not valid.")
        unknown = set(params) - ({"verb"} | allowed[verb])
        if unknown:
            raise OAIProtocolError("badArgument", "The request contains an unexpected argument.")
        if verb == "Identify":
            self._identify(root)
        elif verb == "ListMetadataFormats":
            self._list_metadata_formats(root, params)
        elif verb == "ListSets":
            raise OAIProtocolError("noSetHierarchy", "This repository does not support sets.")
        elif verb == "GetRecord":
            self._get_record(root, params)
        else:
            self._list(root, params, verb)

    def _identify(self, root):
        identify = etree.SubElement(root, _Q("Identify"))
        fields = (
            ("repositoryName", self.config.get("titulo", "")),
            ("baseURL", self.config.get("base_url", "")),
            ("protocolVersion", "2.0"),
        )
        for name, value in fields:
            etree.SubElement(identify, _Q(name)).text = str(value or "")
        for email in self.config.get("email", []):
            etree.SubElement(identify, _Q("adminEmail")).text = str(email)
        etree.SubElement(identify, _Q("earliestDatestamp")).text = "2001-01-01T10:00:00Z"
        etree.SubElement(identify, _Q("deletedRecord")).text = "transient"
        etree.SubElement(identify, _Q("granularity")).text = "YYYY-MM-DDThh:mm:ssZ"
        etree.SubElement(identify, _Q("compression")).text = "identity"
        description = self.config.get("descricao")
        if description:
            try:
                node = self._parse_xml(description)
                wrapper = etree.SubElement(identify, _Q("description"))
                wrapper.append(node)
            except (TypeError, ValueError, etree.XMLSyntaxError):
                raise OAIServiceError("Repository description is invalid XML.")

    def _list_metadata_formats(self, root, params):
        identifier = params.get("identifier")
        if identifier and self._get_provider_record(identifier) is None:
            raise OAIProtocolError("idDoesNotExist", "The identifier does not exist.")
        node = etree.SubElement(root, _Q("ListMetadataFormats"))
        fmt = etree.SubElement(node, _Q("metadataFormat"))
        etree.SubElement(fmt, _Q("metadataPrefix")).text = OAI_PREFIX
        etree.SubElement(fmt, _Q("schema")).text = self.schema
        etree.SubElement(fmt, _Q("metadataNamespace")).text = self.metadata_namespace

    def _token_args(self, token, verb):
        try:
            if len(token) > 4096:
                raise ValueError("oversized token")
            raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
            payload = json.loads(raw.decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or payload.get("v") != 1
                or payload.get("verb") != verb
                or type(payload.get("offset")) is not int
                or not 0 <= payload["offset"] <= 2**63 - 1
                or payload.get("prefix") != OAI_PREFIX
            ):
                raise ValueError("invalid token fields")
            from_value = payload.get("from")
            until_value = payload.get("until")
            return {
                "offset": payload["offset"],
                "prefix": OAI_PREFIX,
                "from": self._parse_date(from_value) if from_value else None,
                "until": self._parse_date(until_value, inclusive=True) if until_value else None,
            }
        except OAIProtocolError:
            raise OAIProtocolError("badResumptionToken", "The resumption token is invalid.")
        except (ValueError, TypeError, UnicodeDecodeError, binascii.Error):
            raise OAIProtocolError("badResumptionToken", "The resumption token is invalid.")

    def _list(self, root, params, verb):
        token = params.get("resumptionToken")
        if "resumptionToken" in params:
            if not token:
                raise OAIProtocolError("badResumptionToken", "The resumption token is empty.")
            if set(params) != {"verb", "resumptionToken"}:
                raise OAIProtocolError("badArgument", "A resumption token cannot be combined with other arguments.")
            state = self._token_args(token, verb)
            offset, prefix = state["offset"], state["prefix"]
            from_value, until_value = state["from"], state["until"]
        else:
            prefix = params.get("metadataPrefix")
            if not prefix:
                raise OAIProtocolError("badArgument", "The metadataPrefix argument is required.")
            if prefix != OAI_PREFIX or prefix not in self.config.get("metadata_prefixes", []):
                raise OAIProtocolError("cannotDisseminateFormat", "The metadata format is not supported.")
            offset = 0
            if "from" in params and "until" in params and len(params["from"]) != len(params["until"]):
                raise OAIProtocolError("badArgument", "The from and until arguments have different granularities.")
            from_value = self._parse_date(params["from"]) if "from" in params else None
            until_value = self._parse_date(params["until"], inclusive=True) if "until" in params else None
            if from_value and until_value and from_value > until_value:
                raise OAIProtocolError("badArgument", "The from datestamp is later than until.")
            if params.get("set"):
                raise OAIProtocolError("noRecordsMatch", "The requested set is not supported.")

        records = list(self.provider.oai_query(
            offset=offset,
            batch_size=self.batch_size + 1,
            from_=from_value,
            until=until_value,
            identifier=None,
        ))
        if not records:
            raise OAIProtocolError("noRecordsMatch", "No records match the request.")
        page = records[:self.batch_size]
        next_token = None
        if len(records) > self.batch_size:
            payload = {
                "v": 1,
                "verb": verb,
                "prefix": prefix,
                "from": from_value.strftime("%Y-%m-%dT%H:%M:%SZ") if from_value else None,
                "until": until_value.strftime("%Y-%m-%dT%H:%M:%SZ") if until_value else None,
                "offset": offset + self.batch_size,
            }
            next_token = base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ).decode("ascii").rstrip("=")

        metadata_pages = {}
        if verb == "ListRecords":
            for index, item in enumerate(page):
                if not item.get("record", {}).get("deleted"):
                    metadata_pages[index] = self._metadata_xml(item)

        container = etree.SubElement(root, _Q(verb))
        for index, item in enumerate(page):
            header = self._append_header(container, item, with_record=verb == "ListRecords")
            if verb == "ListRecords" and not item.get("record", {}).get("deleted"):
                record = header.getparent()
                metadata = etree.SubElement(record, _Q("metadata"))
                metadata_xml = metadata_pages[index]
                if metadata_xml is not None:
                    metadata.append(metadata_xml)
        token_node = etree.SubElement(
            container,
            _Q("resumptionToken"),
            cursor=str(offset),
        )
        if next_token:
            token_node.text = next_token

    def _get_record(self, root, params):
        if not params.get("identifier") or not params.get("metadataPrefix"):
            raise OAIProtocolError("badArgument", "GetRecord requires identifier and metadataPrefix.")
        if set(params) != {"verb", "identifier", "metadataPrefix"}:
            raise OAIProtocolError("badArgument", "GetRecord has an unexpected argument.")
        if params["metadataPrefix"] != OAI_PREFIX or params["metadataPrefix"] not in self.config.get("metadata_prefixes", []):
            raise OAIProtocolError("cannotDisseminateFormat", "The metadata format is not supported.")
        item = self._get_provider_record(params["identifier"])
        if item is None:
            raise OAIProtocolError("idDoesNotExist", "The identifier does not exist.")
        metadata_node = None
        deleted = item.get("record", {}).get("deleted")
        if not deleted:
            metadata_node = self._metadata_xml(item)
        container = etree.SubElement(root, _Q("GetRecord"))
        header = self._append_header(container, item)
        if not deleted:
            record = header.getparent()
            metadata = etree.SubElement(record, _Q("metadata"))
            if metadata_node is not None:
                metadata.append(metadata_node)

    def _get_provider_record(self, identifier):
        lookup = getattr(self.provider, "get_oai_record", None)
        return lookup(identifier) if lookup else None

    def _append_header(self, parent, item, with_record=True):
        record = etree.SubElement(parent, _Q("record")) if with_record else parent
        payload = item.get("record", item)
        header_attrs = {"status": "deleted"} if payload.get("deleted") else {}
        header = etree.SubElement(record, _Q("header"), **header_attrs)
        internal_id = payload.get("id")
        identifier = internal_id if str(internal_id).startswith("oai:") else "oai:{}".format(internal_id)
        etree.SubElement(header, _Q("identifier")).text = str(identifier)
        timestamp = payload.get("when_modified") or datetime.now(timezone.utc)
        etree.SubElement(header, _Q("datestamp")).text = self._format_date(timestamp)
        return header

    @staticmethod
    def _metadata_xml(item):
        payload = item.get("record", item)
        metadata = item.get("metadata") or payload.get("tx_metadado_xml")
        if isinstance(metadata, str):
            metadata = metadata.encode("utf-8")
        if not metadata:
            # Match the legacy OAI endpoint: records remain listable even when
            # no LexML publisher is configured, with an empty metadata element.
            return None
        try:
            return OAIProtocolServer._parse_xml(metadata)
        except (TypeError, ValueError, etree.XMLSyntaxError):
            raise OAIServiceError("The record metadata is invalid XML.")

    @staticmethod
    def _parse_xml(value):
        if isinstance(value, str):
            value = value.encode("utf-8")
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        node = etree.fromstring(value, parser=parser)
        # OAI replies must be standalone XML and cannot depend on a DTD or
        # unresolved entity declarations carried by stored provider metadata.
        if node.getroottree().docinfo.doctype or any(isinstance(item, etree._Entity) for item in node.iter()):
            raise OAIServiceError("DTD and entity declarations are not supported in OAI XML.")
        return node
