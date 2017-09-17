# from itertools import groupby
# from xml.dom.minidom import Document
# import xml.parsers.expat
# import copy
#
# import xmltodict
from pyexpat import ExpatError
from urllib.parse import urlunsplit

import dicttoxml
import requests
import xmltodict
from lxml import etree


class ChomikRequestMixin:
    VERSION = "2.0.8.1"
    CLIENT = "ChomikBox-" + VERSION
    REQUEST_SCHEME = 'http'
    REQUEST_HOST = 'box.chomikuj.pl'  # Old: main.box.chomikuj.pl, 208.43.223.12
    REQUEST_PORT = 80  # Old: 8083
    REQUEST_PATH = 'services/ChomikBoxService.svc'

    def get_url(self, scheme: str=None, host: str=None, port: int=None, path: str=None) -> str:
        scheme = scheme or self.REQUEST_SCHEME
        netloc = '{host}:{port}'.format(
            host=host or self.REQUEST_HOST, port=port or self.REQUEST_PORT
        )
        path = path or self.REQUEST_PATH
        query = fragment = ''
        return urlunsplit([scheme, netloc, path, query, fragment])

class ChomikSOAP(ChomikRequestMixin):
    CHARSET = 'UTF-8'
    ENCODING = 'http://schemas.xmlsoap.org/soap/encoding/'
    NAMESPACE = 'http://schemas.xmlsoap.org/soap/envelope/'
    XMLNS = 'http://chomikuj.pl/'

    _DEFAULT_HEADERS = {
        'SOAPAction': 'http://chomikuj.pl/IChomikBoxService/{method}',
        'Content-Type': 'text/xml; charset=%s' % CHARSET,
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'identity',
        'Accept-Language': 'pl-PL,en,*',
        'User-Agent': 'Mozilla/5.0',
        'Host': ChomikRequestMixin.REQUEST_HOST,
    }

    def request(self, method: str, request: dict, headers: dict=None):
        headers = headers or {}
        assert isinstance(headers, dict)

        default_headers = self._DEFAULT_HEADERS.copy()
        default_headers['SOAPAction'] = default_headers['SOAPAction'].format(method=method)
        default_headers.update(headers)

        response = requests.post(
            url=self.get_url(), headers=default_headers,
            data=self._request_envelope(method, request)
        )

        try:
            response_content = xmltodict.parse(response.content)
        except ExpatError:
            response_content = response.content.decode()

        return {
            'status': response.status_code,
            'content': response_content,
            'cookies': response.cookies,
        }

    def _request_envelope(self, method: str, request: dict) -> str:
        """
        :return: <Envelope><Body><method>...</method></Body></Envelope>
        """
        # <Envelope>
        envelope = etree.Element('{%s}Envelope' % self.NAMESPACE, nsmap={'s': self.NAMESPACE})
        envelope.attrib['{%s}encodingStyle' % self.NAMESPACE] = self.ENCODING

        # <Body>
        envelope_body = etree.SubElement(envelope, '{%s}Body' % self.NAMESPACE)

        # <method>
        envelope_body_method = etree.fromstring(
            dicttoxml.dicttoxml(request, custom_root=method, attr_type=False)
        )
        envelope_body_method.attrib['xmlns'] = self.XMLNS
        envelope_body.append(envelope_body_method)

        return etree.tostring(envelope, xml_declaration=True, encoding=self.CHARSET).decode()
