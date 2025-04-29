class InvalidBBox(Exception):
    """Exception raised when the bounding box is not valid."""

    def __init__(self, message="Bounding box is not valid. Lower the size of the bounding box."):
        self.message = message
        super().__init__(self.message)