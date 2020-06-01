import datetime
import json
import platform
import re
import six
import ssl
import time
import types
from six.moves.urllib.parse import urlencode, quote_plus, urlparse


class EasyPostObject(object):
    def __init__(self, easypost_id=None, api_key=None, parent=None, name=None, **params):
        self.__dict__['_values'] = set()
        self.__dict__['_unsaved_values'] = set()
        self.__dict__['_transient_values'] = set()
        # python2.6 doesnt have {} syntax for sets
        self.__dict__['_immutable_values'] = set(['_api_key', 'id'])
        self.__dict__['_retrieve_params'] = params

        self.__dict__['_parent'] = parent
        self.__dict__['_name'] = name

        self.__dict__['_api_key'] = api_key

        if easypost_id:
            self.id = easypost_id

    def __setattr__(self, k, v):
        self.__dict__[k] = v

        if k not in self._immutable_values:
            self._values.add(k)
            self._unsaved_values.add(k)

            cur = self
            cur_parent = self._parent
            while cur_parent:
                if cur._name:
                    cur_parent._unsaved_values.add(cur._name)
                cur = cur_parent
                cur_parent = cur._parent

    def __getattr__(self, k):
        try:
            return self.__dict__[k]
        except KeyError:
            pass
        raise AttributeError("%r object has no attribute %r" % (type(self).__name__, k))

    def __getitem__(self, k):
        return self.__dict__[k]

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
        return default

    def __setitem__(self, k, v):
        setattr(self, k, v)

    def keys(self):
        return self._values.keys()

    def values(self):
        return self._values.keys()

    @classmethod
    def construct_from(cls, values, api_key=None, parent=None, name=None):
        instance = cls(values.get('id'), api_key, parent, name)
        instance.refresh_from(values, api_key)
        return instance

    def refresh_from(self, values, api_key):
        self._api_key = api_key

        for k, v in sorted(six.iteritems(values)):
            if k == 'id' and self.id != v:
                self.id = v

            if k in self._immutable_values:
                continue
            self.__dict__[k] = EasyPostObject.convert_to_easypost_object(v, api_key, self, k)
            self._values.add(k)
            self._transient_values.discard(k)
            self._unsaved_values.discard(k)

    def flatten_unsaved(self):
        values = {}
        for key in self._unsaved_values:
            value = self.get(key)
            values[key] = value

            if type(value) is EasyPostObject:
                values[key] = value.flatten_unsaved()
        return values

    def __repr__(self):
        type_string = ''

        if isinstance(self.get('object'), six.string_types):
            type_string = ' %s' % self.get('object').encode('utf8')

        json_string = json.dumps(self.to_dict(), sort_keys=True,
                                 indent=2, cls=EasyPostObjectEncoder)

        return '<%s%s at %s> JSON: %s' % (type(self).__name__, type_string,
                                          hex(id(self)), json_string)

    def __str__(self):
        return self.to_json(indent=2)

    def to_json(self, indent=None):
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent, cls=EasyPostObjectEncoder)

    def to_dict(self):
        def _serialize(o):
            if isinstance(o, EasyPostObject):
                return o.to_dict()
            if isinstance(o, list):
                return [_serialize(r) for r in o]
            return o

        d = {"id": self.get("id")} if self.get("id") else {}
        for k in sorted(self._values):
            v = getattr(self, k)
            v = _serialize(v)
            d[k] = v
        return d

    def convert_to_easypost_object(self, response, api_key, parent=None, name=None):
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
            return [EasyPostObject.convert_to_easypost_object(r, api_key, parent) for r in response]
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


class EasyPostObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, EasyPostObject):
            return obj.to_dict()
        else:
            return json.JSONEncoder.default(self, obj)
