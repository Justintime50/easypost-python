import datetime
import json
import platform
import re
import six
import ssl
import time
import types
from six.moves.urllib.parse import urlencode, quote_plus, urlparse


from .easypost_object import EasyPostObject
from .version import VERSION, VERSION_INFO
from .error import Error


class Requestor(object):
    def __init__(self, local_api_key=None):
        self._api_key = local_api_key

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

    @classmethod
    def api_url(cls, url=None):
        url = url or ''
        return '%s%s' % (Requestor.api_base, url)

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
        my_api_key = self._api_key or Requestor.api_key

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


# parent resource classes
class Resource(EasyPostObject):
    def _ident(self):
        return [self.get('id')]

    @classmethod
    def retrieve(cls, easypost_id, api_key=None, **params):
        try:
            easypost_id = easypost_id['id']
        except (KeyError, TypeError):
            pass

        instance = cls(easypost_id, api_key, **params)
        instance.refresh()
        return instance

    def refresh(self):
        requestor = Requestor(self._api_key)
        url = self.instance_url()
        response, api_key = requestor.request('get', url, self._retrieve_params)
        self.refresh_from(response, api_key)
        return self

    @classmethod
    def class_name(cls):
        if cls == Resource:
            raise NotImplementedError('Resource is an abstract class. '
                                      'You should perform actions on its subclasses.')

        cls_name = six.text_type(cls.__name__)
        cls_name = cls_name[0:1] + re.sub(r'([A-Z])', r'_\1', cls_name[1:])
        return "%s" % cls_name.lower()

    @classmethod
    def class_url(cls):
        cls_name = cls.class_name()
        if cls_name[-1:] == "s" or cls_name[-1:] == "h":
            return "/%ses" % cls_name
        else:
            return "/%ss" % cls_name

    def instance_url(self):
        easypost_id = self.get('id')
        if not easypost_id:
            raise Error('%s instance has invalid ID: %r' % (type(self).__name__, easypost_id))
        easypost_id = Requestor._utf8(easypost_id)
        base = self.class_url()
        param = quote_plus(easypost_id)
        return "{base}/{param}".format(base=base, param=param)


class AllResource(Resource):
    @classmethod
    def all(cls, api_key=None, **params):
        requestor = Requestor(api_key)
        url = cls.class_url()
        response, api_key = requestor.request('get', url, params)
        return EasyPostObject.convert_to_easypost_object(response, api_key)


class CreateResource(Resource):
    @classmethod
    def create(cls, api_key=None, **params):
        requestor = Requestor(api_key)
        url = cls.class_url()
        wrapped_params = {cls.class_name(): params}
        response, api_key = requestor.request('post', url, wrapped_params)
        return EasyPostObject.convert_to_easypost_object(response, api_key)


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


class UpdateResource(Resource):
    def save(self):
        if self._unsaved_values:
            requestor = Requestor(self._api_key)
            params = {}
            for k in self._unsaved_values:
                params[k] = getattr(self, k)
                if type(params[k]) is EasyPostObject:
                    params[k] = params[k].flatten_unsaved()
            params = {self.class_name(): params}
            url = self.instance_url()
            response, api_key = requestor.request('put', url, params)
            self.refresh_from(response, api_key)

        return self


class DeleteResource(Resource):
    def delete(self, **params):
        requestor = Requestor(self._api_key)
        url = self.instance_url()
        response, api_key = requestor.request('delete', url, params)
        self.refresh_from(response, api_key)
        return self
