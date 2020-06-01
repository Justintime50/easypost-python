"""Import EasyPost modules"""
from .easypost_object import EasyPostObject
from .easypost_resource import Requestor, AllResource


class Address(AllResource):
    """Address records"""
    @classmethod
    def create(cls, api_key=None, verify=None, verify_strict=None, **params):
        """Create an address"""
        print(api_key)
        requestor = Requestor(api_key)
        url = cls.class_url()

        # Verify address if applicable
        if verify or verify_strict:
            verify = verify or []
            verify_strict = verify_strict or []
            url += '?' + '&'.join(
                ['verify[]={0}'.format(opt) for opt in verify] +
                ['verify_strict[]={0}'.format(opt) for opt in verify_strict]
            )

        wrapped_params = {cls.class_name(): params}
        response, api_key = requestor.request('post', url, wrapped_params)
        return EasyPostObject.convert_to_easypost_object(response, api_key)

    @classmethod
    def create_and_verify(cls, api_key=None, carrier=None, **params):
        """Create and verify an address in one call"""
        requestor = Requestor(api_key)
        url = "%s/%s" % (cls.class_url(), "create_and_verify")

        wrapped_params = {
            cls.class_name(): params,
            "carrier": carrier
        }
        response, api_key = requestor.request('post', url, wrapped_params)

        response_address = response.get('address', None)
        response_message = response.get('message', None)

        if response_address is not None:
            verified_address = EasyPostObject.convert_to_easypost_object(response_address, api_key)
            if response_message is not None:
                verified_address.message = response_message
                verified_address._immutable_values.update('message')
            return verified_address
        else:
            return EasyPostObject.convert_to_easypost_object(response, api_key)

    def verify(self, carrier=None):
        """Verify an address"""
        requestor = Requestor(self._api_key)
        url = "%s/%s" % (self.instance_url(), "verify")
        if carrier:
            url += "?carrier=%s" % carrier
        response, api_key = requestor.request('get', url)

        response_address = response.get('address', None)
        response_message = response.get('message', None)

        if response_address is not None:
            verified_address = EasyPostObject.convert_to_easypost_object(response_address, api_key)
            if response_message is not None:
                verified_address.message = response_message
                verified_address._immutable_values.update('message')
            return verified_address
        else:
            return EasyPostObject.convert_to_easypost_object(response, api_key)
