class CarrierAccount(AllResource, CreateResource, UpdateResource, DeleteResource):
    @classmethod
    def types(cls, api_key=None):
        requestor = Requestor(api_key)
        response, api_key = requestor.request('get', "/carrier_types")
        return convert_to_easypost_object(response, api_key)
