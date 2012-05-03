class NgmgBaseLogDatum(object):
    def __init__(self, lines):
        self.lines = lines
        self._dict_representations = None
        self._excess_lines = None
        self.get_dict_representations()

    @property
    def dict_representations(self):
        return self._dict_representations

    @property
    def excess_lines(self):
        return self._excess_lines
