import datetime
import json
import platform
import re
import six
import ssl
import time
import types
from six.moves.urllib.parse import urlencode, quote_plus, urlparse


"""EasyPost Client Library Imports"""
from .address import Address
from .batch import Batch
from .carrier_account import CarrierAccount
from .customs_info import CustomsInfo
from .customs_item import CustomsItem
from .easypost_object import EasyPostObject, EasyPostObjectEncoder
from .easypost_resource import AllResource, CreateResource, UpdateResource, DeleteResource
from .event import Event
from .insurance import Insurance
from .order import Order
from .parcel import Parcel
from .pickup import Pickup
from .rate import Rate
from .refund import Refund
from .report import Report
from .scanform import ScanForm
from .shipment import Shipment
from .tracker import Tracker
from .user import User
from .version import VERSION, VERSION_INFO
from .webhook import Webhook

__author__ = 'EasyPost <oss@easypost.com>'
__version__ = VERSION
version_info = VERSION_INFO


# use urlfetch as request_lib on google app engine, otherwise use requests
request_lib = None
# use a max timeout equal to that of all customer-facing backend operations
_max_timeout = 90
try:
    from google.appengine.api import urlfetch
    request_lib = 'urlfetch'
    # use the GAE application-wide "deadline" (or its default) if it's less than our existing max timeout
    _max_timeout = min(urlfetch.get_default_fetch_deadline() or 60, _max_timeout)
except ImportError:
    try:
        import requests
        request_lib = 'requests'
        requests_session = requests.Session()
        requests_http_adapter = requests.adapters.HTTPAdapter(max_retries=3)
        requests_session.mount('https://api.easypost.com', requests_http_adapter)
    except ImportError:
        raise ImportError('EasyPost requires an up to date requests library. '
                          'Update requests via "pip install -U requests" or '
                          'contact us at contact@easypost.com.')

    try:
        version = requests.__version__
        major, minor, patch = [int(i) for i in version.split('.')]
    except Exception:
        raise ImportError('EasyPost requires an up to date requests library. '
                          'Update requests via "pip install -U requests" or contact '
                          'us at contact@easypost.com.')
    else:
        if major < 1:
            raise ImportError('EasyPost requires an up to date requests library. Update '
                              'requests via "pip install -U requests" or contact us '
                              'at contact@easypost.com.')

# config
api_key = None
api_base = 'https://api.easypost.com/v2'
# use our default timeout, or our max timeout if that is less
timeout = min(60, _max_timeout)


USER_AGENT = 'EasyPost/v2 PythonClient/{0}'.format(VERSION)


class Error(Exception):
    def __init__(self, message=None, http_status=None, http_body=None, original_exception=None):
        super(Error, self).__init__(message)
        self.message = message
        self.http_status = http_status
        self.http_body = http_body
        self.original_exception = original_exception
        try:
            self.json_body = json.loads(http_body)
        except Exception:
            self.json_body = None

        self.param = None
        try:
            self.param = self.json_body['error'].get('param', None)
        except Exception:
            pass


def convert_to_easypost_object(response, api_key, parent=None, name=None):
    types = {
        'Address': Address,
        'ScanForm': ScanForm,
        'CustomsItem': CustomsItem,
        'CustomsInfo': CustomsInfo,
        'Parcel': Parcel,
        'Shipment': Shipment,
        'Insurance': Insurance,
        'Rate': Rate,
        'Refund': Refund,
        'Batch': Batch,
        'Event': Event,
        'Tracker': Tracker,
        'Pickup': Pickup,
        'Order': Order,
        'PickupRate': PickupRate,
        'PostageLabel': PostageLabel,
        'CarrierAccount': CarrierAccount,
        'User': User,
        'Report': Report,
        'ShipmentReport': Report,
        'PaymentLogReport': Report,
        'TrackerReport': Report,
        'RefundReport': Report,
        'ShipmentInvoiceReport': Report,
        'Webhook': Webhook
    }

    prefixes = {
        'adr': Address,
        'sf': ScanForm,
        'evt': Event,
        'cstitem': CustomsItem,
        'cstinfo': CustomsInfo,
        'prcl': Parcel,
        'shp': Shipment,
        'ins': Insurance,
        'rate': Rate,
        'rfnd': Refund,
        'batch': Batch,
        'trk': Tracker,
        'order': Order,
        'pickup': Pickup,
        'pickuprate': PickupRate,
        'pl': PostageLabel,
        'ca': CarrierAccount,
        'user': User,
        'shprep': Report,
        'plrep': Report,
        'trkrep': Report,
        'refrep': Report,
        'shpinvrep': Report,
        'hook': Webhook
    }

    if isinstance(response, list):
        return [convert_to_easypost_object(r, api_key, parent) for r in response]
    elif isinstance(response, dict):
        response = response.copy()
        cls_name = response.get('object', EasyPostObject)
        cls_id = response.get('id', None)
        if isinstance(cls_name, six.string_types):
            cls = types.get(cls_name, EasyPostObject)
        elif cls_id is not None:
            cls = prefixes.get(cls_id[0:cls_id.find('_')], EasyPostObject)
        else:
            cls = EasyPostObject
        return cls.construct_from(response, api_key, parent, name)
    else:
        return response


class Requestor(object):
    def __init__(self, local_api_key=None):
        self._api_key = local_api_key

    @classmethod
    def api_url(cls, url=None):
        url = url or ''
        return '%s%s' % (api_base, url)

    @classmethod
    def _utf8(cls, value):
        if six.PY2:
            # Python2's urlencode wants bytestrings, not unicode
            if isinstance(value, six.text_type):
                return value.encode('utf-8')
            return value
        elif isinstance(value, six.binary_type):
            # Python3's six.text_type(bytestring) returns "b'bytestring'"
            # So, have to decode it to unicode
            return value.decode('utf-8')
        else:
            # Python3's urlencode can handle unicode
            return value

    @classmethod
    def encode_dict(cls, out, key, dict_value):
        n = {}
        for k, v in sorted(six.iteritems(dict_value)):
            k = cls._utf8(k)
            v = cls._utf8(v)
            n["%s[%s]" % (key, k)] = v
        out.extend(cls._encode_inner(n))

    @classmethod
    def encode_list(cls, out, key, list_value):
        n = {}
        for k, v in enumerate(list_value):
            v = cls._utf8(v)
            n["%s[%s]" % (key, k)] = v
        out.extend(cls._encode_inner(n))

    @classmethod
    def encode_datetime(cls, out, key, dt_value):
        utc_timestamp = int(time.mktime(dt_value.timetuple()))
        out.append((key, utc_timestamp))

    @classmethod
    def encode_none(cls, out, key, value):
        pass  # do not include None-valued params in request

    @classmethod
    def _encode_inner(cls, params):
        # special case value encoding
        ENCODERS = {
            list: cls.encode_list,
            dict: cls.encode_dict,
            datetime.datetime: cls.encode_datetime,
        }
        if six.PY2:
            ENCODERS[types.NoneType] = cls.encode_none
        if six.PY3:
            ENCODERS[type(None)] = cls.encode_none

        out = []
        for key, value in sorted(six.iteritems(params)):
            key = cls._utf8(key)
            try:
                encoder = ENCODERS[value.__class__]
                encoder(out, key, value)
            except KeyError:
                # don't need special encoding
                try:
                    value = six.text_type(value)
                except Exception:
                    pass

                out.append((key, value))
        return out

    @classmethod
    def _objects_to_ids(cls, param):
        if isinstance(param, Resource):
            return {'id': param.id}
        elif isinstance(param, dict):
            out = {}
            for k, v in six.iteritems(param):
                out[k] = cls._objects_to_ids(v)
            return out
        elif isinstance(param, list):
            out = []
            for k, v in enumerate(param):
                out.append(cls._objects_to_ids(v))
            return out
        else:
            return param

    @classmethod
    def encode(cls, params):
        return urlencode(cls._encode_inner(params))

    @classmethod
    def build_url(cls, url, params):
        base_query = urlparse(url).query
        if base_query:
            return '%s&%s' % (url, cls.encode(params))
        else:
            return '%s?%s' % (url, cls.encode(params))

    def request(self, method, url, params=None, apiKeyRequired=True):
        if params is None:
            params = {}
        http_body, http_status, my_api_key = self.request_raw(method, url, params, apiKeyRequired)
        response = self.interpret_response(http_body, http_status)
        return response, my_api_key

    def request_raw(self, method, url, params=None, apiKeyRequired=True):
        if params is None:
            params = {}
        my_api_key = self._api_key or api_key

        if apiKeyRequired and my_api_key is None:
            raise Error(
                'No API key provided. Set an API key via "easypost.api_key = \'APIKEY\'. '
                'Your API keys can be found in your EasyPost dashboard, or you can email us '
                'at contact@easypost.com for assistance.')

        abs_url = self.api_url(url)
        params = self._objects_to_ids(params)

        ua = {
            'client_version': VERSION,
            'lang': 'python',
            'publisher': 'easypost',
            'request_lib': request_lib,
        }
        for attr, func in (('lang_version', platform.python_version),
                           ('platform', platform.platform),
                           ('uname', lambda: ' '.join(platform.uname()))):
            try:
                val = func()
            except Exception as e:
                val = "!! %s" % e
            ua[attr] = val

        if hasattr(ssl, 'OPENSSL_VERSION'):
            ua['openssl_version'] = ssl.OPENSSL_VERSION

        headers = {
            'X-Client-User-Agent': json.dumps(ua),
            'User-Agent': USER_AGENT,
            'Authorization': 'Bearer %s' % my_api_key,
            'Content-type': 'application/x-www-form-urlencoded'
        }

        if timeout > _max_timeout:
            raise Error("`timeout` must not exceed %d; it is %d" % (_max_timeout, timeout))

        if request_lib == 'urlfetch':
            http_body, http_status = self.urlfetch_request(method, abs_url, headers, params)
        elif request_lib == 'requests':
            http_body, http_status = self.requests_request(method, abs_url, headers, params)
        else:
            raise Error("Bug discovered: invalid request_lib: %s. "
                        "Please report to contact@easypost.com." % request_lib)

        return http_body, http_status, my_api_key

    def interpret_response(self, http_body, http_status):
        try:
            response = json.loads(http_body)
        except Exception:
            raise Error("Invalid response body from API: (%d) %s " % (http_status, http_body), http_status, http_body)
        if not (200 <= http_status < 300):
            self.handle_api_error(http_status, http_body, response)
        return response

    def requests_request(self, method, abs_url, headers, params):
        method = method.lower()
        if method == 'get' or method == 'delete':
            if params:
                abs_url = self.build_url(abs_url, params)
            data = None
        elif method == 'post' or method == 'put':
            data = self.encode(params)
        else:
            raise Error("Bug discovered: invalid request method: %s. "
                        "Please report to contact@easypost.com." % method)

        try:
            result = requests_session.request(
                method,
                abs_url,
                headers=headers,
                data=data,
                timeout=timeout,
                verify=True,
            )
            http_body = result.text
            http_status = result.status_code
        except Exception as e:
            raise Error("Unexpected error communicating with EasyPost. If this "
                        "problem persists please let us know at contact@easypost.com.",
                        original_exception=e)
        return http_body, http_status

    def urlfetch_request(self, method, abs_url, headers, params):
        args = {}
        if method == 'post' or method == 'put':
            args['payload'] = self.encode(params)
        elif method == 'get' or method == 'delete':
            abs_url = self.build_url(abs_url, params)
        else:
            raise Error("Bug discovered: invalid request method: %s. Please report "
                        "to contact@easypost.com." % method)

        args['url'] = abs_url
        args['method'] = method
        args['headers'] = headers
        args['validate_certificate'] = False
        args['deadline'] = timeout

        try:
            result = urlfetch.fetch(**args)
        except Exception as e:
            raise Error("Unexpected error communicating with EasyPost. "
                        "If this problem persists, let us know at contact@easypost.com.",
                        original_exception=e)

        return result.content, result.status_code

    def handle_api_error(self, http_status, http_body, response):
        try:
            error = response['error']
        except (KeyError, TypeError):
            raise Error("Invalid response from API: (%d) %r " % (http_status, http_body), http_status, http_body)

        try:
            raise Error(error.get('message', ''), http_status, http_body)
        except AttributeError:
            raise Error(error, http_status, http_body)


class Blob(AllResource, CreateResource):
    @classmethod
    def retrieve(cls, easypost_id, api_key=None, **params):
        try:
            easypost_id = easypost_id['id']
        except (KeyError, TypeError):
            pass

        requestor = Requestor(api_key)
        url = "%s/%s" % (cls.class_url(), easypost_id)
        response, api_key = requestor.request('get', url)
        return response["signed_url"]
