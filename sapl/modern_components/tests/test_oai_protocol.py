import base64
import json
import unittest
from datetime import datetime, timezone

from lxml import etree

from sapl.modern_components.oai_protocol import (
    LEXML_NS,
    OAI_NS,
    OAIProtocolServer,
    OAIServiceError,
)


def q(name):
    return "{%s}%s" % (OAI_NS, name)


class FakeProvider:
    def __init__(self, records, batch_size=2):
        self.config = {
            "titulo": "Repositório de teste",
            "base_url": "https://example.invalid/oai",
            "email": ["oai@example.invalid"],
            "descricao": None,
            "metadata_prefixes": ["oai_lexml"],
            "batch_size": batch_size,
        }
        self.records = records

    def oai_query(self, offset=0, batch_size=10, from_=None, until=None, identifier=None):
        return self.records[offset:offset + batch_size]

    def get_oai_record(self, identifier):
        for record in self.records:
            internal = record["record"]["id"]
            expected = internal if internal.startswith("oai:") else "oai:" + internal
            if expected == identifier:
                return record
        return None


def sample_records(count=3):
    rows = []
    for index in range(1, count + 1):
        internal_id = "camara.gov.br:sapl/lei;2024;%d" % index
        metadata = (
            '<LexML xmlns="%s"><Identificacao>%d</Identificacao></LexML>'
            % (LEXML_NS, index)
        )
        rows.append({
            "record": {
                "id": internal_id,
                "when_modified": datetime(2024, 3, index, tzinfo=timezone.utc),
                "deleted": 0,
            },
            "metadata": metadata,
        })
    return rows


class OAIProtocolTests(unittest.TestCase):
    def setUp(self):
        self.server = OAIProtocolServer(FakeProvider(sample_records()))

    def parse(self, params):
        payload = self.server.handleRequest(params)
        root = etree.fromstring(payload)
        self.assertEqual(root.tag, q("OAI-PMH"))
        self.assertIsNotNone(root.find(q("responseDate")))
        self.assertIsNotNone(root.find(q("request")))
        return root

    def test_identify_returns_protocol_metadata(self):
        root = self.parse({"verb": "Identify"})
        node = root.find(q("Identify"))
        self.assertEqual(node.findtext(q("protocolVersion")), "2.0")
        self.assertEqual(node.findtext(q("deletedRecord")), "transient")
        self.assertEqual(node.findtext(q("granularity")), "YYYY-MM-DDThh:mm:ssZ")
        self.assertEqual(node.findtext(q("adminEmail")), "oai@example.invalid")

    def test_identifiers_have_direct_headers_including_deleted_records(self):
        rows = sample_records(2)
        rows[1]["record"]["deleted"] = True
        self.server = OAIProtocolServer(FakeProvider(rows))
        root = self.parse({"verb": "ListIdentifiers", "metadataPrefix": "oai_lexml"})
        node = root.find(q("ListIdentifiers"))
        headers = node.findall(q("header"))
        self.assertEqual(len(headers), 2)
        self.assertEqual(headers[1].get("status"), "deleted")
        self.assertEqual(node.findall(q("record")), [])
        self.assertEqual(node.findall(q("metadata")), [])

    def test_list_metadata_formats(self):
        root = self.parse({"verb": "ListMetadataFormats"})
        self.assertEqual(root.findtext(".//" + q("metadataPrefix")), "oai_lexml")
        self.assertEqual(root.findtext(".//" + q("metadataNamespace")), LEXML_NS)

    def test_get_record_has_header_and_lexml_metadata(self):
        root = self.parse({
            "verb": "GetRecord",
            "identifier": "oai:camara.gov.br:sapl/lei;2024;2",
            "metadataPrefix": "oai_lexml",
        })
        self.assertEqual(root.findtext(".//" + q("identifier")), "oai:camara.gov.br:sapl/lei;2024;2")
        self.assertIsNotNone(root.find(".//" + q("metadata") + "/*"))

    def test_lists_produce_valid_pages_and_resumption_token(self):
        root = self.parse({"verb": "ListRecords", "metadataPrefix": "oai_lexml"})
        records = root.findall(".//" + q("record"))
        self.assertEqual(len(records), 2)
        self.assertIsNotNone(records[0].find(q("metadata") + "/*"))
        token = root.findtext(".//" + q("resumptionToken"))
        self.assertTrue(token)

        next_page = self.parse({"verb": "ListRecords", "resumptionToken": token})
        self.assertEqual(len(next_page.findall(".//" + q("record"))), 1)
        self.assertIn(next_page.findtext(".//" + q("resumptionToken")), (None, ""))

    def test_list_identifiers_emits_headers_only(self):
        root = self.parse({"verb": "ListIdentifiers", "metadataPrefix": "oai_lexml"})
        self.assertEqual(len(root.findall(".//" + q("header"))), 2)
        self.assertEqual(root.findall(".//" + q("metadata")), [])

    def test_bad_verb_argument_token_and_empty_set_are_protocol_errors(self):
        cases = [
            ({"verb": "NotARequest"}, "badVerb"),
            ({"verb": "GetRecord"}, "badArgument"),
            ({"verb": "ListRecords", "metadataPrefix": "unknown"}, "cannotDisseminateFormat"),
            ({"verb": "ListRecords", "resumptionToken": "not-a-token"}, "badResumptionToken"),
            ({"verb": "ListSets"}, "noSetHierarchy"),
        ]
        for params, code in cases:
            with self.subTest(params=params):
                root = self.parse(params)
                self.assertEqual(root.find(q("error")).get("code"), code)

    def test_invalid_repeated_query_argument_is_reported_as_xml(self):
        root = self.parse({"verb": ["Identify", "ListRecords"]})
        self.assertEqual(root.find(q("error")).get("code"), "badArgument")

    def test_malformed_metadata_is_a_service_failure(self):
        provider = FakeProvider([{
            "record": {"id": "broken-metadata", "deleted": 0},
            "metadata": b"<LexML>",
        }])
        with self.assertRaises(OAIServiceError):
            OAIProtocolServer(provider).handleRequest({
                "verb": "ListRecords", "metadataPrefix": "oai_lexml"
            })

    def test_malformed_description_is_a_service_failure(self):
        self.server.config["descricao"] = "<broken>"
        with self.assertRaises(OAIServiceError):
            self.server.handleRequest({"verb": "Identify"})

    def test_dtd_and_entities_are_rejected_without_expansion(self):
        values = [
            '<!DOCTYPE x [<!ENTITY e "internal">]><x>&e;</x>',
            '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///dev/null">]><x>&e;</x>',
            '<!DOCTYPE x SYSTEM "https://example.invalid/external.dtd"><x/>',
        ]
        for value in values:
            with self.subTest(value=value):
                self.server.config["descricao"] = value
                with self.assertRaises(OAIServiceError):
                    self.server.handleRequest({"verb": "Identify"})
                provider = FakeProvider([{
                    "record": {"id": "entity-metadata", "deleted": 0},
                    "metadata": value,
                }])
                with self.assertRaises(OAIServiceError):
                    OAIProtocolServer(provider).handleRequest({
                        "verb": "ListRecords", "metadataPrefix": "oai_lexml"
                    })

    def test_invalid_xml_arguments_return_clean_protocol_errors(self):
        cases = [
            {"verb": "Identify", "invalid name": "value"},
            {"verb": "Identify", "identifier": "nul\x00value"},
            {"verb": "Identify", "identifier": "surrogate\ud800"},
            {"verb": "unknown"},
            {"verb": "ListRecords", "metadataPrefix": "oai_lexml", "from": ""},
            {"verb": "ListRecords", "metadataPrefix": "oai_lexml", "until": ""},
        ]
        for params in cases:
            with self.subTest(params=params):
                root = self.parse(params)
                self.assertEqual(root.find(q("request")).attrib, {})
                self.assertEqual([etree.QName(node).localname for node in root],
                                 ["responseDate", "request", "error"])
                self.assertIn(root.find(q("error")).get("code"), ("badArgument", "badVerb"))

    def test_mixed_datestamp_granularity_is_rejected(self):
        for from_value, until_value in [
            ("2024-03-01", "2024-03-02T00:00:00Z"),
            ("2024-03-01T00:00:00Z", "2024-03-02"),
        ]:
            root = self.parse({
                "verb": "ListRecords", "metadataPrefix": "oai_lexml",
                "from": from_value, "until": until_value,
            })
            self.assertEqual(root.find(q("error")).get("code"), "badArgument")
            self.assertIsNone(root.find(q("ListRecords")))

    def test_until_date_includes_the_whole_day_across_pages(self):
        rows = sample_records(4)
        for row, timestamp in zip(rows, [
            datetime(2024, 3, 1, 0, 0, 0), datetime(2024, 3, 1, 12, 0, 0),
            datetime(2024, 3, 1, 23, 59, 59), datetime(2024, 3, 2, 0, 0, 0),
        ]):
            row["record"]["when_modified"] = timestamp

        class FilteringProvider(FakeProvider):
            def __init__(self, records):
                super().__init__(records, batch_size=1)
                self.bounds = []

            def oai_query(self, offset=0, batch_size=10, from_=None, until=None, identifier=None):
                self.bounds.append((from_, until))
                selected = [row for row in self.records if
                            (from_ is None or row["record"]["when_modified"] >= from_) and
                            (until is None or row["record"]["when_modified"] <= until)]
                return selected[offset:offset + batch_size]

        provider = FilteringProvider(rows)
        server = OAIProtocolServer(provider)
        params = {"verb": "ListRecords", "metadataPrefix": "oai_lexml",
                  "from": "2024-03-01", "until": "2024-03-01"}
        identifiers = []
        while True:
            root = etree.fromstring(server.handleRequest(params))
            self.assertIsNone(root.find(q("error")))
            identifiers.extend(node.text for node in root.findall(".//" + q("identifier")))
            token = root.findtext(".//" + q("resumptionToken"))
            if not token:
                break
            params = {"verb": "ListRecords", "resumptionToken": token}
        self.assertEqual(len(identifiers), 3)
        self.assertEqual(provider.bounds, [(datetime(2024, 3, 1), datetime(2024, 3, 1, 23, 59, 59))] * 3)

    def test_non_object_and_malformed_tokens_are_bad_resumption_tokens(self):
        for payload in ([], None, "text", 42, {}, {"v": 1, "offset": True}):
            token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            root = self.parse({"verb": "ListIdentifiers", "resumptionToken": token})
            self.assertEqual(root.find(q("error")).get("code"), "badResumptionToken")
            self.assertIsNone(root.find(q("ListIdentifiers")))

    def test_missing_metadata_returns_only_protocol_error(self):
        provider = FakeProvider([{"record": {"id": "missing-metadata", "deleted": 0}}])
        server = OAIProtocolServer(provider)
        root = etree.fromstring(server.handleRequest({
            "verb": "ListRecords", "metadataPrefix": "oai_lexml"
        }))
        self.assertIsNone(root.find(q("error")))
        records = root.findall(".//" + q("record"))
        self.assertEqual(len(records), 1)
        self.assertIsNotNone(records[0].find(q("metadata")))
        self.assertEqual(len(records[0].find(q("metadata"))), 0)

    def test_get_record_missing_metadata_returns_empty_metadata_element(self):
        provider = FakeProvider([{"record": {"id": "missing-metadata", "deleted": 0}}])
        server = OAIProtocolServer(provider)
        root = etree.fromstring(server.handleRequest({
            "verb": "GetRecord",
            "identifier": "oai:missing-metadata",
            "metadataPrefix": "oai_lexml",
        }))
        self.assertIsNone(root.find(q("error")))
        records = root.findall(".//" + q("record"))
        self.assertEqual(len(records), 1)
        self.assertIsNotNone(records[0].find(q("metadata")))
        self.assertEqual(len(records[0].find(q("metadata"))), 0)


if __name__ == "__main__":
    unittest.main()
