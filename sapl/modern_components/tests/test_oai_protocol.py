import unittest
from datetime import datetime, timezone

from lxml import etree

from sapl.modern_components.oai_protocol import (
    LEXML_NS,
    OAI_NS,
    OAIProtocolServer,
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

    def test_missing_metadata_returns_only_protocol_error(self):
        provider = FakeProvider([{"record": {"id": "missing-metadata", "deleted": 0}}])
        server = OAIProtocolServer(provider)
        root = etree.fromstring(server.handleRequest({
            "verb": "ListRecords", "metadataPrefix": "oai_lexml"
        }))
        self.assertEqual(root.find(q("error")).get("code"), "unknownError")
        self.assertIsNone(root.find(q("ListRecords")))

    def test_get_record_missing_metadata_returns_only_protocol_error(self):
        provider = FakeProvider([{"record": {"id": "missing-metadata", "deleted": 0}}])
        server = OAIProtocolServer(provider)
        root = etree.fromstring(server.handleRequest({
            "verb": "GetRecord",
            "identifier": "oai:missing-metadata",
            "metadataPrefix": "oai_lexml",
        }))
        self.assertEqual(root.find(q("error")).get("code"), "unknownError")
        self.assertIsNone(root.find(q("GetRecord")))


if __name__ == "__main__":
    unittest.main()
