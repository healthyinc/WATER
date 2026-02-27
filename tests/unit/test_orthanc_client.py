"""
Unit tests for the Orthanc REST client.

Uses httpx mock transport to avoid requiring a running Orthanc instance.
"""

from __future__ import annotations

import httpx

from water.dicom.orthanc_client import OrthancClient


def _mock_transport(responses: dict[str, httpx.Response]) -> httpx.MockTransport:
    """Create a mock transport that returns pre-configured responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in responses:
            return responses[path]
        return httpx.Response(404, text="Not Found")

    return httpx.MockTransport(handler)


class TestOrthancClient:
    """Tests for OrthancClient using mocked HTTP responses."""

    def _make_client(self, responses: dict[str, httpx.Response]) -> OrthancClient:
        client = OrthancClient(base_url="http://test-orthanc:8042")
        # Replace the internal httpx client with a mocked one
        client._client = httpx.Client(
            base_url="http://test-orthanc:8042",
            transport=_mock_transport(responses),
        )
        return client

    def test_is_alive_returns_true(self) -> None:
        responses = {
            "/system": httpx.Response(200, json={"Version": "1.12.0", "DicomAet": "ORTHANC"}),
        }
        client = self._make_client(responses)
        assert client.is_alive() is True

    def test_is_alive_returns_false_on_error(self) -> None:
        responses: dict[str, httpx.Response] = {}
        client = self._make_client(responses)
        # /system is not in responses → 404, but is_alive catches errors
        # Actually we need a transport that raises connection error
        client._client = httpx.Client(
            base_url="http://test-orthanc:8042",
            transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(httpx.ConnectError("refused"))),
        )
        assert client.is_alive() is False

    def test_get_system_info(self) -> None:
        expected = {"Version": "1.12.0", "DicomAet": "WATER_ORTHANC"}
        responses = {
            "/system": httpx.Response(200, json=expected),
        }
        client = self._make_client(responses)
        assert client.get_system_info() == expected

    def test_get_statistics(self) -> None:
        expected = {"CountPatients": 10, "CountStudies": 20, "CountSeries": 50, "CountInstances": 500}
        responses = {
            "/statistics": httpx.Response(200, json=expected),
        }
        client = self._make_client(responses)
        assert client.get_statistics() == expected

    def test_upload_dicom(self) -> None:
        expected = {"ID": "abc123", "Status": "Success"}
        responses = {
            "/instances": httpx.Response(200, json=expected),
        }
        client = self._make_client(responses)
        result = client.upload_dicom(b"\x00" * 128)
        assert result["ID"] == "abc123"

    def test_list_patients(self) -> None:
        expected = ["patient-1", "patient-2"]
        responses = {
            "/patients": httpx.Response(200, json=expected),
        }
        client = self._make_client(responses)
        assert client.list_patients() == expected

    def test_list_studies(self) -> None:
        expected = ["study-1"]
        responses = {
            "/studies": httpx.Response(200, json=expected),
        }
        client = self._make_client(responses)
        assert client.list_studies() == expected

    def test_list_series(self) -> None:
        expected = ["series-a", "series-b"]
        responses = {
            "/series": httpx.Response(200, json=expected),
        }
        client = self._make_client(responses)
        assert client.list_series() == expected

    def test_list_instances(self) -> None:
        expected = ["inst-1", "inst-2", "inst-3"]
        responses = {
            "/instances": httpx.Response(200, json=expected),
        }
        # Note: /instances for GET returns list; for POST uploads a file
        # The mock transport doesn't distinguish methods, so we test separately
        client = self._make_client(responses)
        assert client.list_instances() == expected
