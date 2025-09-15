class Skeleton:
    def send(self) -> None:
        raise NotImplementedError("Subclasses must implement this method")
    
    def create_thread(self) -> None:
        raise NotImplementedError("Subclasses must implement this method")
