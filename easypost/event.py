class Event(Resource):
    @classmethod
    def receive(self, values):
        return convert_to_easypost_object(json.loads(values), api_key)
