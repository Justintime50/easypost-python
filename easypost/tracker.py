class Tracker(AllResource, CreateResource):
    @classmethod
    def create_list(cls, api_key=None, **params):
        requestor = Requestor(api_key)
        url = "%s/%s" % (cls.class_url(), "create_list")
        response, api_key = requestor.request('post', url, params)
        return True

    @classmethod
    def all_updated(cls, api_key=None, **params):
        requestor = Requestor(api_key)
        url = "%s/%s" % (cls.class_url(), "all_updated")
        response, api_key = requestor.request('get', url, params)
        return convert_to_easypost_object(response["trackers"], api_key), response["has_more"]
