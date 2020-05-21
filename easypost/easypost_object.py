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
            self.__dict__[k] = convert_to_easypost_object(v, api_key, self, k)
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


class EasyPostObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, EasyPostObject):
            return obj.to_dict()
        else:
            return json.JSONEncoder.default(self, obj)


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
