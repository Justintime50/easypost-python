class Shipment(AllResource, CreateResource):
    @classmethod
    def track_with_code(cls, api_key=None, **params):
        requestor = Requestor(api_key)
        url = "%s/%s" % (cls.class_url(), "track")
        response, api_key = requestor.request('get', url, params)
        return response

    def get_rates(self):
        requestor = Requestor(self._api_key)
        url = "%s/%s" % (self.instance_url(), "rates")
        response, api_key = requestor.request('get', url)
        self.refresh_from(response, api_key)
        return self

    def buy(self, **params):
        requestor = Requestor(self._api_key)
        url = "%s/%s" % (self.instance_url(), "buy")
        response, api_key = requestor.request('post', url, params)
        self.refresh_from(response, api_key)
        return self

    def refund(self, **params):
        requestor = Requestor(self._api_key)
        url = "%s/%s" % (self.instance_url(), "refund")

        response, api_key = requestor.request('post', url, params)
        self.refresh_from(response, api_key)
        return self

    def insure(self, **params):
        requestor = Requestor(self._api_key)
        url = "%s/%s" % (self.instance_url(), "insure")

        response, api_key = requestor.request('post', url, params)
        self.refresh_from(response, api_key)
        return self

    def label(self, **params):
        requestor = Requestor(self._api_key)
        url = "%s/%s" % (self.instance_url(), "label")

        response, api_key = requestor.request('get', url, params)
        self.refresh_from(response, api_key)
        return self

    def lowest_rate(self, carriers=None, services=None):
        carriers = carriers or []
        services = services or []

        lowest_rate = None

        try:
            carriers = carriers.split(',')
        except AttributeError:
            pass
        carriers = [c.lower() for c in carriers]

        try:
            services = services.split(',')
        except AttributeError:
            pass
        services = [service.lower() for service in services]

        for rate in self.rates:
            rate_carrier = rate.carrier.lower()
            if len(carriers) > 0 and rate_carrier not in carriers:
                continue

            rate_service = rate.service.lower()
            if len(services) > 0 and rate_service not in services:
                continue

            if lowest_rate is None or float(rate.rate) < float(lowest_rate.rate):
                lowest_rate = rate

        if lowest_rate is None:
            raise Error('No rates found.')

        return lowest_rate


class PostageLabel(AllResource, CreateResource):
    pass
