# parent resource classes
class AllResource(Resource):
    @classmethod
    def all(cls, api_key=None, **params):
        requestor = Requestor(api_key)
        url = cls.class_url()
        response, api_key = requestor.request('get', url, params)
        return convert_to_easypost_object(response, api_key)


class CreateResource(Resource):
    @classmethod
    def create(cls, api_key=None, **params):
        requestor = Requestor(api_key)
        url = cls.class_url()
        wrapped_params = {cls.class_name(): params}
        response, api_key = requestor.request('post', url, wrapped_params)
        return convert_to_easypost_object(response, api_key)


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
