class BBoxTooBig(Exception):
    """Exception raised when the bounding box is not valid."""

    def __init__(self, message="Bounding box is not valid. Lower the size of the bounding box."):
        self.message = message
        super().__init__(self.message)

class BBoxTooSmall(Exception):
    """Exception raised when the bounding box is not valid."""

    def __init__(self, message="Bounding box is too small. Increase the size."):
        self.message = message
        super().__init__(self.message)

class NoQueue(Exception):
    """Raised when there is not Queue in the Queue Object defined in `feedbox.py`"""
    def __init__(self, message="No Queue. Database returned no Queue"):
        self.message = message
        super().__init__(self.message)